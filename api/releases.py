"""Pull release data from GitHub into the Release table and enrich it for metrics.

For each release this stores what `stats` computes on the fly:
- tickets and the failed-deployment flag, parsed from the release notes, and
- lead time: from the oldest commit since the previous release to the release.

Lead time costs one GitHub compare call per release, so it is computed once and
kept (`enriched_at`).
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from api.models import Project, Release, SyncRun, utcnow
from services import github_api as gh
from services.github import GitHubService

log = logging.getLogger("tiamat.releases")
# One sync at a time.
_sync_lock = threading.Lock()
# A "running" sync older than this was interrupted (e.g. the app restarted).
STALE_SYNC = timedelta(minutes=30)


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt and dt.tzinfo is None else dt


def release_time(release: Release) -> datetime:
    """The timestamp metrics use (matches `stats`: GitHub's created_at)."""
    return _aware(release.created_at or release.published_at)


def sort_key(release: Release):
    """Deterministic chronological order, even for tags created in the same second."""
    return (release_time(release), _aware(release.published_at), release.id or 0)


def _upsert(session: Session, project_id: int, releases: list[dict]) -> int:
    existing = {
        r.tag: r for r in session.exec(select(Release).where(Release.project_id == project_id))
    }
    added = 0
    for data in releases:
        tag = data.get("tag_name")
        created = gh.parse_time(data.get("created_at"))
        published = gh.parse_time(data.get("published_at")) or created
        if not tag or not published:
            continue
        release = existing.get(tag)
        if release is None:
            release = Release(project_id=project_id, tag=tag, published_at=published)
            existing[tag] = release
            added += 1
        body = data.get("body") or ""
        release.name = data.get("name") or tag
        release.url = data.get("html_url")
        release.published_at = published
        new_created = created or published
        if release.created_at is not None and _aware(release.created_at) != new_created:
            # Re-created tag: its lead time (and pairing) must be recomputed.
            release.enriched_at = None
            release.lead_time_hours = None
        release.created_at = new_created
        release.tickets = GitHubService.extract_tickets(body)
        release.is_failed = GitHubService.is_failed_deployment(body)
        session.add(release)
    return added


def _fetch(repo: str, since: datetime):
    try:
        return gh.list_releases_since(repo, since), None
    except Exception as exc:  # noqa: BLE001 - one bad repo must not fail the whole sync
        return [], str(exc)


def _lead_time_jobs(
    session: Session, synced: list[tuple[int, str]]
) -> list[tuple[int, str, str, str]]:
    """(release_id, repo, previous_tag, tag) for releases whose lead time is not known yet."""
    jobs = []
    for project_id, repo in synced:
        releases = sorted(
            session.exec(select(Release).where(Release.project_id == project_id)),
            key=sort_key,
        )
        for previous, current in pairwise(releases):
            if current.enriched_at is None:
                jobs.append((current.id, repo, previous.tag, current.tag))
        # The oldest stored release has no previous one, so it gets no lead time; if an
        # older release is fetched later (a longer window) it is computed then.
    return jobs


def _compute_lead_time(job):
    release_id, repo, previous_tag, tag = job
    try:
        return release_id, gh.oldest_commit_date(repo, previous_tag, tag), None
    except Exception as exc:  # noqa: BLE001
        return release_id, None, str(exc)


_start_lock = threading.Lock()


def start_run(session: Session, months: int) -> tuple[SyncRun, bool]:
    """Create a "running" SyncRun, or return the one already running. -> (run, created)"""
    with _start_lock:
        current = latest_run(session)
        if is_running(current):
            return current, False
        run = SyncRun(kind="releases", details={"months": months})
        session.add(run)
        session.commit()
        session.refresh(run)
        return run, True


def sync_releases(
    session: Session, projects: list[Project], months: int = 6, run: SyncRun | None = None
) -> SyncRun:
    """Fetch releases from the last `months` months for `projects` and enrich them."""
    targets = [(p.id, p.repo) for p in projects]  # plain values for worker threads
    since = utcnow() - timedelta(days=months * 31)
    with _sync_lock:
        if run is None:
            run = SyncRun(kind="releases", details={"months": months})
            session.add(run)
            session.commit()
        try:
            details = _sync(session, targets, since)
            repo_errors = details["errors"]
            if repo_errors and len(repo_errors) >= len(targets):
                run.status = "error"
            elif repo_errors or details["lead_time_errors"]:
                run.status = "partial"
            else:
                run.status = "success"
        except Exception as exc:
            log.exception("Release sync failed")
            session.rollback()
            details = {"errors": {"sync": str(exc)}, "lead_time_errors": 0}
            run.status = "error"
        run.finished_at = utcnow()
        run.details = {"months": months, "projects": len(targets), **details}
        session.add(run)
        session.commit()
        session.refresh(run)
        return run


def _sync(session: Session, targets: list[tuple[int, str]], since: datetime) -> dict:
    with ThreadPoolExecutor(max_workers=8) as pool:
        fetched = list(pool.map(lambda t: (t, *_fetch(t[1], since)), targets))

    added, errors, synced = 0, {}, []
    for (project_id, repo), releases, error in fetched:
        if error:
            errors[repo] = error
            continue
        try:
            added += _upsert(session, project_id, releases)
            session.commit()
            synced.append((project_id, repo))
        except IntegrityError as exc:
            session.rollback()
            errors[repo] = f"Could not save releases: {exc.orig}"

    jobs = _lead_time_jobs(session, synced)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_compute_lead_time, jobs))

    rows = (
        {
            r.id: r
            for r in session.exec(select(Release).where(col(Release.id).in_([j[0] for j in jobs])))
        }
        if jobs
        else {}
    )
    enriched, lead_errors, first_error = 0, 0, None
    for n, (release_id, oldest, error) in enumerate(results, 1):
        release = rows.get(release_id)
        if release is None:
            continue  # deleted during the sync
        if error:
            # Leave enriched_at empty so the next sync retries.
            lead_errors += 1
            first_error = first_error or error
            continue
        if oldest is not None:
            release.lead_time_hours = round(
                (release_time(release) - _aware(oldest)).total_seconds() / 3600, 2
            )
        release.enriched_at = utcnow()
        session.add(release)
        enriched += 1
        if n % 50 == 0:
            session.commit()  # keep progress if the process stops mid-way
    session.commit()
    if lead_errors:
        errors["lead times"] = f"{lead_errors} could not be computed (will retry): {first_error}"
    return {
        "added": added,
        "lead_times": enriched,
        "lead_time_errors": lead_errors,
        "errors": errors,
    }


def latest_run(session: Session) -> SyncRun | None:
    """The newest release sync; a "running" one that went stale is closed as interrupted."""
    run = session.exec(
        select(SyncRun).where(SyncRun.kind == "releases").order_by(col(SyncRun.id).desc())
    ).first()
    if run and run.status == "running" and not is_running(run):
        fail_run(session, run, "Interrupted (Tiamat stopped during the sync)")
    return run


def fail_run(session: Session, run: SyncRun, message: str) -> None:
    run.status = "error"
    run.finished_at = utcnow()
    run.details = {**(run.details or {}), "errors": {"sync": message}}
    session.add(run)
    session.commit()
    session.refresh(run)


def close_interrupted_runs(session: Session) -> None:
    """On startup nothing can be running yet: close leftovers from a previous process."""
    for run in session.exec(select(SyncRun).where(SyncRun.status == "running")):
        fail_run(session, run, "Interrupted (Tiamat restarted during the sync)")


def is_running(run: SyncRun | None) -> bool:
    return bool(run and run.status == "running" and utcnow() - _aware(run.started_at) < STALE_SYNC)

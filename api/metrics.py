"""DORA-style metrics computed from stored releases (same definitions as `stats`).

- Deployment frequency: releases per month (a release is a deploy).
- Lead time for changes: days from the oldest commit since the previous release.
- Change failure rate: share of releases whose notes carry a failure marker
  ([hotfix], [rollback], [revert], ...).
- Tickets: unique [ABC-123] references in release notes.

A project in several teams counts toward each of them.
"""

from datetime import UTC, datetime, timedelta
from statistics import median

from sqlmodel import Session, select

from api.models import Project, Release, utcnow
from api.releases import release_time, sort_key


def month_starts(months: int, now: datetime) -> list[datetime]:
    """First instant of each of the last `months` calendar months, oldest first."""
    year, month = now.year, now.month
    starts = []
    for _ in range(months):
        starts.append(datetime(year, month, 1, tzinfo=UTC))
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    return starts[::-1]


def elapsed_months(starts: list[datetime], now: datetime) -> float:
    """Months actually covered: the full months plus the elapsed part of the current one."""
    current = starts[-1]
    nxt = datetime(current.year + (current.month == 12), current.month % 12 + 1, 1, tzinfo=UTC)
    return (len(starts) - 1) + (now - current) / (nxt - current)


def summarize(releases: list[Release], months: float) -> dict:
    deploys = len(releases)
    failures = sum(1 for r in releases if r.is_failed)
    tickets = sum(len(r.tickets) for r in releases)
    lead_days = [r.lead_time_hours / 24 for r in releases if r.lead_time_hours is not None]
    return {
        "deploys": deploys,
        "deploys_per_month": round(deploys / months, 2) if months else 0,
        "tickets": tickets,
        "tickets_per_month": round(tickets / months, 2) if months else 0,
        "failures": failures,
        "change_failure_rate": round(failures / deploys * 100, 1) if deploys else None,
        "avg_lead_time_days": round(sum(lead_days) / len(lead_days), 2) if lead_days else None,
        "median_lead_time_days": round(median(lead_days), 2) if lead_days else None,
        "lead_time_samples": len(lead_days),
    }


def compute(session: Session, months: int = 6, team: str | None = None) -> dict:
    now = utcnow()
    starts = month_starts(months, now)
    window_start = starts[0]

    projects = session.exec(select(Project).where(Project.archived.is_(False))).all()
    teams_of = {p.id: sorted(t.name for t in p.teams) for p in projects}
    if team:
        projects = [p for p in projects if team in teams_of[p.id]]
    ids = {p.id for p in projects}

    releases = (
        [
            r
            for r in session.exec(select(Release).where(Release.project_id.in_(ids))).all()
            if release_time(r) >= window_start
        ]
        if ids
        else []
    )

    def in_month(r: Release, i: int) -> bool:
        end = starts[i + 1] if i + 1 < len(starts) else None
        t = release_time(r)
        return t >= starts[i] and (end is None or t < end)

    monthly = []
    for i, start in enumerate(starts):
        bucket = [r for r in releases if in_month(r, i)]
        row = summarize(bucket, 1)
        monthly.append(
            {
                "month": start.strftime("%Y-%m"),
                "partial": i == len(starts) - 1,
                **{
                    k: row[k]
                    for k in (
                        "deploys",
                        "tickets",
                        "failures",
                        "change_failure_rate",
                        "avg_lead_time_days",
                        "median_lead_time_days",
                    )
                },
            }
        )

    span = elapsed_months(starts, now)
    last_30 = [r for r in releases if release_time(r) >= now - timedelta(days=30)]
    summary = summarize(releases, span) | {
        "deploys_last_30_days": len(last_30),
        "tickets_last_30_days": sum(len(r.tickets) for r in last_30),
    }

    by_project = []
    for p in sorted(projects, key=lambda p: (not p.starred, p.name)):
        mine = [r for r in releases if r.project_id == p.id]
        by_project.append(
            {
                "project_id": p.id,
                "name": p.name,
                "repo": p.repo,
                "teams": teams_of[p.id],
                "starred": p.starred,
            }
            | summarize(mine, span)
        )

    by_team = []
    if not team:
        names = sorted({t for ts in teams_of.values() for t in ts})
        for name in names:
            member_ids = {pid for pid, ts in teams_of.items() if name in ts}
            mine = [r for r in releases if r.project_id in member_ids]
            by_team.append({"team": name, "projects": len(member_ids)} | summarize(mine, span))

    return {
        "months": months,
        "team": team,
        "window_start": window_start,
        "elapsed_months": round(span, 2),
        "generated_at": now,
        "projects": len(projects),
        "summary": summary,
        "monthly": monthly,
        "teams": by_team,
        "by_project": by_project,
    }


def release_rows(session: Session, months: int, team: str | None, limit: int) -> list[dict]:
    window_start = month_starts(months, utcnow())[0]
    projects = {p.id: p for p in session.exec(select(Project).where(Project.archived.is_(False)))}
    if team:
        projects = {pid: p for pid, p in projects.items() if team in {t.name for t in p.teams}}
    rows = (
        [
            r
            for r in session.exec(select(Release).where(Release.project_id.in_(list(projects))))
            if release_time(r) >= window_start
        ]
        if projects
        else []
    )
    rows.sort(key=sort_key, reverse=True)
    return [
        {
            "id": r.id,
            "project_id": r.project_id,
            "project_name": projects[r.project_id].name,
            "tag": r.tag,
            "name": r.name,
            "url": r.url,
            "released_at": release_time(r),
            "lead_time_days": round(r.lead_time_hours / 24, 2)
            if r.lead_time_hours is not None
            else None,
            "is_failed": r.is_failed,
            "tickets": r.tickets,
        }
        for r in rows[:limit]
    ]

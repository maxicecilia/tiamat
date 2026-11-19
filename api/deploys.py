"""Deploy orchestration: resolve a preset, dispatch the workflow, track the run.

Lifecycle of a Deployment.status:
  dispatching   row saved, dispatch request about to be / being sent
  dispatched    GitHub accepted (or may have accepted) the dispatch; waiting to find the run
  queued, in_progress, waiting, ...   the GitHub run's status
  success, failure, cancelled, ...    the GitHub run's conclusion
  error         GitHub definitely rejected the dispatch (nothing ran)
  unknown       Tiamat lost track (run never found, run gone, interrupted); check GitHub
  dismissed     a user cleared a stuck deployment by hand

Every active state has a way out, so an environment can never stay blocked.
"""

import logging
import threading
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, select

from api.models import Deployment, Project, WorkflowPreset, utcnow
from services import github_api as gh

log = logging.getLogger("tiamat.deploys")

ACTIVE_STATUSES = {
    "dispatching",
    "dispatched",
    "queued",
    "in_progress",
    "waiting",
    "requested",
    "pending",
}
# How long to keep looking for the run GitHub started after a dispatch without a run id.
RUN_LOOKUP_TIMEOUT = timedelta(minutes=10)
# A dispatch request takes seconds; a row still "dispatching" after this was interrupted.
DISPATCH_STALE_AFTER = timedelta(minutes=2)
# Give up on runs GitHub stops answering about (deleted run, lost access, ...).
ACTIVE_GIVE_UP_AFTER = timedelta(hours=24)
# Allow for clock skew between this machine and GitHub when matching runs.
CLOCK_SKEW = timedelta(seconds=10)

# The app runs as a single process; this makes "check nothing is running, then insert" atomic.
_dispatch_lock = threading.Lock()


class DeployError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _aware(dt: datetime | None) -> datetime | None:
    # SQLite drops tzinfo; everything we store is UTC.
    return dt.replace(tzinfo=UTC) if dt and dt.tzinfo is None else dt


def env_sort_key(env: str):
    order = {"dev": 0, "staging": 1, "demo": 2, "prod": 3}
    return (order.get(env, 1.5), env)


def project_environments(session: Session, project: Project) -> list[WorkflowPreset]:
    presets = session.exec(
        select(WorkflowPreset).where(WorkflowPreset.version == project.workflow_version)
    ).all()
    if project.deploy_environments is not None:
        presets = [p for p in presets if p.environment in project.deploy_environments]
    return sorted(presets, key=lambda p: env_sort_key(p.environment))


def default_branch(project: Project, preset: WorkflowPreset) -> str:
    return preset.branch or project.base_branch


def is_active(dep: Deployment) -> bool:
    return dep.status in ACTIVE_STATUSES


def _finish(dep: Deployment, status: str, error: str | None = None) -> None:
    dep.status = status
    dep.error = error
    dep.finished_at = utcnow()


def create_deployment(
    session: Session, project: Project, environment: str, branch: str | None, triggered_by: str
) -> Deployment:
    preset = next(
        (p for p in project_environments(session, project) if p.environment == environment), None
    )
    if not preset:
        raise DeployError(
            f"{project.name} has no '{environment}' environment "
            f"for workflow {project.workflow_version}",
            404,
        )
    if project.archived:
        raise DeployError(f"{project.name} is archived", 409)
    if not gh.is_configured():
        raise DeployError("GITHUB_TOKEN is not set, so Tiamat cannot trigger workflows", 503)

    locked_branch = default_branch(project, preset)
    requested = (branch or "").strip() or locked_branch
    if preset.lock_branch and requested != locked_branch:
        raise DeployError(
            f"{environment} deploys are locked to '{locked_branch}'. "
            "Unlock the preset in Settings → Workflows to deploy another branch.",
            409,
        )

    with _dispatch_lock:
        running = session.exec(
            select(Deployment).where(
                Deployment.project_id == project.id,
                Deployment.environment == environment,
                col(Deployment.status).in_(ACTIVE_STATUSES),
            )
        ).first()
        if running:
            raise DeployError(
                f"A deploy of {project.name} to {environment} is already {running.status}", 409
            )
        dep = Deployment(
            project_id=project.id,
            environment=environment,
            workflow_file=preset.workflow_file,
            branch=requested,
            inputs=dict(preset.inputs),
            triggered_by=triggered_by,
        )
        session.add(dep)
        session.commit()
        session.refresh(dep)

    _dispatch(session, project, dep)
    if dep.status == "dispatched":
        refresh_deployment(session, dep)
    return dep


def _dispatch(session: Session, project: Project, dep: Deployment) -> None:
    try:
        dep.workflow_id = gh.resolve_workflow_id(project.repo, dep.workflow_file)
        dep.dispatched_at = utcnow()
        session.add(dep)
        session.commit()
        dep.run_id = gh.dispatch_workflow(project.repo, dep.workflow_id, dep.branch, dep.inputs)
        dep.status = "dispatched"
    except gh.GitHubUncertain as exc:
        if dep.dispatched_at is None:
            _finish(dep, "error", str(exc))  # failed while resolving, before dispatching
        else:
            # The dispatch may have gone through: keep looking for the run instead of
            # inviting a second deploy.
            dep.status = "dispatched"
            dep.error = f"GitHub did not confirm the dispatch ({exc}); looking for the run"
    except gh.GitHubError as exc:
        _finish(dep, "error", str(exc))
    except Exception as exc:
        log.exception("Unexpected error dispatching deployment %s", dep.id)
        if dep.dispatched_at is None:
            _finish(dep, "error", f"Unexpected error: {exc}")
        else:
            dep.status = "dispatched"
            dep.error = f"Unexpected error after dispatch ({exc}); looking for the run"
    session.add(dep)
    session.commit()
    session.refresh(dep)


def _find_run(session: Session, project: Project, dep: Deployment) -> dict | None:
    """Match a dispatch to its run: the earliest unclaimed workflow_dispatch run on the same
    workflow and branch created after the dispatch, started by the same GitHub user."""
    since = _aware(dep.dispatched_at) - CLOCK_SKEW
    runs = gh.list_dispatch_runs(project.repo, dep.workflow_id, dep.branch, since)
    claimed = set(
        session.exec(
            select(Deployment.run_id).where(
                Deployment.id != dep.id, col(Deployment.run_id).is_not(None)
            )
        ).all()
    )
    login = gh.token_login(project.repo)

    def started_by_us(run: dict) -> bool:
        if not login:
            return True
        actor = (run.get("triggering_actor") or run.get("actor") or {}).get("login")
        return actor is None or actor == login

    candidates = [
        r
        for r in runs
        if r["id"] not in claimed and gh.parse_time(r["created_at"]) >= since and started_by_us(r)
    ]
    return min(candidates, key=lambda r: r["created_at"]) if candidates else None


def refresh_deployment(session: Session, dep: Deployment) -> Deployment:
    """Update one deployment from GitHub. Transient errors leave it for the next poll."""
    if not is_active(dep):
        return dep
    now = utcnow()

    if dep.status == "dispatching":
        # Only reachable if the process died mid-dispatch.
        if now - _aware(dep.created_at) > DISPATCH_STALE_AFTER:
            if dep.dispatched_at and dep.workflow_id:
                dep.status = "dispatched"
                dep.error = "Tiamat was interrupted while dispatching; looking for the run"
            else:
                _finish(dep, "unknown", "Interrupted while dispatching; check GitHub")
            session.add(dep)
            session.commit()
        return dep

    project = session.get(Project, dep.project_id)
    try:
        if dep.run_id is None:
            run = (
                _find_run(session, project, dep) if dep.workflow_id and dep.dispatched_at else None
            )
            if run is None:
                if now - _aware(dep.dispatched_at or dep.created_at) > RUN_LOOKUP_TIMEOUT:
                    _finish(dep, "unknown", "GitHub never reported a run for this dispatch")
                    session.add(dep)
                    session.commit()
                return dep
        else:
            run = gh.get_run(project.repo, dep.run_id)
    except gh.GitHubError as exc:
        if (
            exc.status == 404
            or now - _aware(dep.checked_at or dep.created_at) > ACTIVE_GIVE_UP_AFTER
        ):
            _finish(dep, "unknown", f"Lost track of the run: {exc}")
            session.add(dep)
            session.commit()
        return dep

    dep.run_id = run["id"]
    dep.run_url = run.get("html_url")
    dep.checked_at = now
    dep.started_at = gh.parse_time(run.get("run_started_at")) or dep.started_at
    if run.get("status") == "completed":
        dep.status = run.get("conclusion") or "completed"
        dep.finished_at = gh.parse_time(run.get("updated_at")) or now
    else:
        dep.status = run.get("status") or dep.status
    session.add(dep)
    session.commit()
    session.refresh(dep)
    return dep


def dismiss_deployment(session: Session, dep: Deployment) -> Deployment:
    """Let a user clear a deployment Tiamat is still tracking (e.g. they checked GitHub)."""
    if is_active(dep):
        _finish(dep, "dismissed", "Dismissed in the dashboard; check GitHub for the real outcome")
        session.add(dep)
        session.commit()
        session.refresh(dep)
    return dep


def poll_active(session: Session) -> int:
    """Refresh every in-flight deployment. Returns how many were checked."""
    active = session.exec(
        select(Deployment).where(col(Deployment.status).in_(ACTIVE_STATUSES))
    ).all()
    for dep in active:
        try:
            refresh_deployment(session, dep)
        except Exception:
            log.exception("Failed to refresh deployment %s", dep.id)
            session.rollback()
    return len(active)

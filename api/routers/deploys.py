from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlmodel import Session, col, select

from api import deploys, releases
from api.db import SessionDep, engine
from api.models import Deployment, Project, Release, SyncRun
from api.releases import sync_releases
from api.schemas import (
    DeploymentCreate,
    DeploymentRead,
    DeployOverviewRow,
    DeployTarget,
    ProjectRead,
    ReleaseRead,
    SyncRunRead,
)
from services import github_api as gh
from services.slack import SlackService

router = APIRouter(tags=["deploys"])


def _read(dep: Deployment, project: Project) -> DeploymentRead:
    return DeploymentRead.model_validate(
        dep.model_dump() | {"project_name": project.name, "repo": project.repo}
    )


def _get_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("/status")
def integration_status():
    return {"github": gh.is_configured(), "slack": SlackService.is_configured()}


@router.get("/deploys/overview", response_model=list[DeployOverviewRow])
def overview(session: SessionDep):
    projects = session.exec(
        select(Project)
        .where(Project.archived.is_(False))
        .order_by(Project.starred.desc(), Project.name)
    ).all()
    # Latest deployment per (project, environment) and latest release per project.
    last: dict[tuple[int, str], Deployment] = {}
    for dep in session.exec(select(Deployment).order_by(col(Deployment.created_at).desc())):
        last.setdefault((dep.project_id, dep.environment), dep)
    latest_release: dict[int, Release] = {}
    for rel in session.exec(select(Release).order_by(col(Release.published_at).desc())):
        latest_release.setdefault(rel.project_id, rel)

    rows = []
    for project in projects:
        targets = []
        for preset in deploys.project_environments(session, project):
            dep = last.get((project.id, preset.environment))
            targets.append(
                DeployTarget(
                    environment=preset.environment,
                    preset_id=preset.id,
                    workflow_file=preset.workflow_file,
                    branch=deploys.default_branch(project, preset),
                    inputs=preset.inputs,
                    description=preset.description,
                    lock_branch=preset.lock_branch,
                    last_deployment=_read(dep, project) if dep else None,
                )
            )
        rel = latest_release.get(project.id)
        rows.append(
            DeployOverviewRow(
                project=ProjectRead.model_validate(project),
                latest_release=ReleaseRead.model_validate(rel) if rel else None,
                targets=targets,
            )
        )
    return rows


@router.get("/deployments", response_model=list[DeploymentRead])
def list_deployments(
    session: SessionDep,
    project_id: int | None = None,
    environment: str | None = None,
    limit: int = 50,
):
    query = (
        select(Deployment, Project)
        .join(Project, Project.id == Deployment.project_id)
        .order_by(col(Deployment.created_at).desc())
        .limit(min(limit, 500))
    )
    if project_id is not None:
        query = query.where(Deployment.project_id == project_id)
    if environment := (environment or "").strip():
        query = query.where(Deployment.environment == environment)
    return [_read(dep, project) for dep, project in session.exec(query)]


@router.post("/deployments", response_model=DeploymentRead, status_code=201)
def create_deployment(data: DeploymentCreate, session: SessionDep):
    project = _get_project(session, data.project_id)
    try:
        login = gh.token_login(project.repo) if gh.is_configured() else None
        dep = deploys.create_deployment(
            session, project, data.environment, data.branch, triggered_by=login or "dashboard"
        )
    except deploys.DeployError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None
    return _read(dep, project)


@router.post("/deployments/{deployment_id}/refresh", response_model=DeploymentRead)
def refresh_deployment(deployment_id: int, session: SessionDep):
    dep = session.get(Deployment, deployment_id)
    if not dep:
        raise HTTPException(404, "Deployment not found")
    dep = deploys.refresh_deployment(session, dep)
    return _read(dep, session.get(Project, dep.project_id))


@router.post("/deployments/{deployment_id}/dismiss", response_model=DeploymentRead)
def dismiss_deployment(deployment_id: int, session: SessionDep):
    dep = session.get(Deployment, deployment_id)
    if not dep:
        raise HTTPException(404, "Deployment not found")
    dep = deploys.dismiss_deployment(session, dep)
    return _read(dep, session.get(Project, dep.project_id))


@router.get("/projects/{project_id}/releases", response_model=list[ReleaseRead])
def project_releases(project_id: int, session: SessionDep, limit: int = 20):
    _get_project(session, project_id)
    return session.exec(
        select(Release)
        .where(Release.project_id == project_id)
        .order_by(col(Release.published_at).desc())
        .limit(limit)
    ).all()


def _run_sync(run_id: int, project_id: int | None, months: int) -> None:
    with Session(engine) as session:
        run = session.get(SyncRun, run_id)
        if run is None:
            return
        try:
            query = select(Project).where(Project.archived.is_(False))
            if project_id is not None:
                query = query.where(Project.id == project_id)
            sync_releases(session, list(session.exec(query)), months=months, run=run)
        except Exception as exc:  # noqa: BLE001 - never leave the run "running"
            session.rollback()
            releases.fail_run(session, run, f"Sync failed to start: {exc}")


@router.post("/releases/sync", response_model=SyncRunRead, status_code=202)
def sync(
    session: SessionDep,
    background: BackgroundTasks,
    project_id: int | None = None,
    months: int = Query(6, ge=1, le=24),
):
    """Start a release sync in the background; poll /releases/sync/latest for the result."""
    if not gh.is_configured():
        raise HTTPException(503, "GITHUB_TOKEN is not set")
    run, created = releases.start_run(session, months)
    if created:
        background.add_task(_run_sync, run.id, project_id, months)
    return run


@router.get("/releases/sync/latest", response_model=SyncRunRead | None)
def latest_sync(session: SessionDep):
    return releases.latest_run(session)

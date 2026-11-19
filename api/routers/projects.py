from fastapi import APIRouter, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from api.db import SessionDep
from api.labels import resolve_tags, resolve_teams
from api.models import Project, Tag, Team, utcnow
from api.schemas import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])

NULLABLE_FIELDS = {"description", "deploy_environments"}
# Starred projects get their pending changes checked live on GitHub, so keep them few.
MAX_STARRED = 5


def _get(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(
    session: SessionDep,
    team: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
):
    query = select(Project).order_by(Project.starred.desc(), Project.name)
    if team and team.strip():
        query = query.where(Project.teams.any(Team.name == team.strip().lower()))
    if tag and tag.strip():
        query = query.where(Project.tags.any(Tag.name == tag.strip().lower()))
    if not include_archived:
        query = query.where(Project.archived.is_(False))
    return session.exec(query).all()


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(data: ProjectCreate, session: SessionDep):
    # GitHub repo names are case-insensitive, so Org/Repo and org/repo are the same project.
    if session.exec(select(Project).where(func.lower(Project.repo) == data.repo.lower())).first():
        raise HTTPException(409, f"Project {data.repo} already exists")
    project = Project.model_validate(
        data.model_dump(exclude={"tags", "teams"})
        | {"name": data.name or data.repo.split("/", 1)[1]}
    )
    project.tags = resolve_tags(session, data.tags)
    project.teams = resolve_teams(session, data.teams)
    session.add(project)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Conflicting update, please retry") from None
    session.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, session: SessionDep):
    return _get(session, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, data: ProjectUpdate, session: SessionDep):
    project = _get(session, project_id)
    changes = data.model_dump(exclude_unset=True)
    # Only these columns are nullable; an explicit null elsewhere means "no change".
    changes = {k: v for k, v in changes.items() if v is not None or k in NULLABLE_FIELDS}
    if changes.get("starred") and not project.starred:
        starred = session.exec(
            select(func.count())
            .select_from(Project)
            .where(Project.starred, Project.archived == False)
        ).one()
        if starred >= MAX_STARRED:
            raise HTTPException(
                409, f"You can star up to {MAX_STARRED} projects. Unstar one first."
            )
    if (tags := changes.pop("tags", None)) is not None:
        project.tags = resolve_tags(session, tags)
    if (teams := changes.pop("teams", None)) is not None:
        project.teams = resolve_teams(session, teams)
    for key, value in changes.items():
        setattr(project, key, value)
    project.updated_at = utcnow()
    session.add(project)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Conflicting update, please retry") from None
    session.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, session: SessionDep):
    session.delete(_get(session, project_id))
    session.commit()

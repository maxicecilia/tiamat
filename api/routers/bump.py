from fastapi import APIRouter, HTTPException
from sqlmodel import Field, SQLModel

from api import bump
from api.db import SessionDep
from api.models import Project
from services import github_api as gh

router = APIRouter(tags=["releases"])


class CreateReleaseRequest(SQLModel):
    bump: str | None = None  # major | minor | patch
    version: str | None = None  # explicit tag, overrides `bump`
    # The latest version the user saw; refused if a newer release appeared since.
    expected_current: str | None = None
    target: str = Field(min_length=1)
    name: str | None = None
    draft: bool = False
    prerelease: bool = False


def _project(session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if not project or project.archived:
        raise HTTPException(404, "Project not found")
    if not gh.is_configured():
        raise HTTPException(503, "GITHUB_TOKEN is not set")
    return project


@router.get("/projects/{project_id}/next-version")
def next_version(project_id: int, session: SessionDep, target: str | None = None):
    project = _project(session, project_id)
    try:
        return bump.plan(project, (target or "").strip() or None)
    except gh.GitHubError as exc:
        raise HTTPException(502, f"GitHub: {exc}") from None


@router.post("/projects/{project_id}/releases", status_code=201)
def create_release(project_id: int, data: CreateReleaseRequest, session: SessionDep):
    project = _project(session, project_id)
    try:
        return bump.create(
            session,
            project,
            bump=data.bump,
            version=(data.version or "").strip() or None,
            expected_current=data.expected_current,
            target=data.target.strip(),
            name=(data.name or "").strip() or None,
            draft=data.draft,
            prerelease=data.prerelease,
        )
    except bump.BumpError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None
    except gh.GitHubUncertain as exc:
        raise HTTPException(
            504, f"{exc}. The release may have been created; refresh before retrying."
        ) from None
    except gh.GitHubError as exc:
        raise HTTPException(502, f"GitHub: {exc}") from None

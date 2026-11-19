from fastapi import APIRouter, HTTPException
from sqlmodel import Field, SQLModel, col, select

from api import pulls
from api.db import SessionDep
from api.models import Project
from services import github_api as gh

router = APIRouter(tags=["pull requests"])


class CheckRequest(SQLModel):
    project_ids: list[int] | None = None  # None = every active project
    base: str | None = None  # override each project's base branch
    head: str | None = None


class PullTarget(SQLModel):
    project_id: int
    # The branches the user confirmed; sent explicitly so a project edited after the
    # check can't open a PR for different branches than the dialog showed.
    base: str = Field(min_length=1)
    head: str = Field(min_length=1)


class CreatePullsRequest(SQLModel):
    targets: list[PullTarget]
    notify_slack: bool = False  # pinging a developer group is opt-in


def _projects(session, ids: list[int] | None) -> list[Project]:
    query = (
        select(Project)
        .where(Project.archived.is_(False))
        .order_by(Project.starred.desc(), Project.name)
    )
    if ids is not None:
        query = query.where(col(Project.id).in_(ids))
    projects = list(session.exec(query))
    if ids is not None and len(projects) != len(set(ids)):
        raise HTTPException(404, "Some projects were not found or are archived")
    return projects


def _require_github():
    if not gh.is_configured():
        raise HTTPException(503, "GITHUB_TOKEN is not set")


@router.post("/pending")
def check_pending(data: CheckRequest, session: SessionDep):
    """Like `check`: commits waiting on each project's head branch to reach its base."""
    _require_github()
    base = (data.base or "").strip() or None
    head = (data.head or "").strip() or None
    return pulls.check(_projects(session, data.project_ids), base, head)


@router.post("/pull-requests")
def create_pull_requests(data: CreatePullsRequest, session: SessionDep):
    """Like `createpr`: open head->base PRs where there are pending commits, then
    (optionally) announce the new ones on Slack."""
    _require_github()
    if not data.targets:
        raise HTTPException(422, "Select at least one project")
    branches = {t.project_id: (t.base.strip(), t.head.strip()) for t in data.targets}
    return pulls.create_pull_requests(
        _projects(session, list(branches)), data.notify_slack, branches
    )

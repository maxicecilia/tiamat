"""Request/response shapes for the API."""

from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints
from sqlmodel import Field, SQLModel

from api.models import WorkflowVersion


class TeamRead(SQLModel):
    id: int
    name: str


class TeamWithCount(TeamRead):
    project_count: int = 0


class TeamUpdate(SQLModel):
    name: str


class TagRead(SQLModel):
    id: int
    name: str
    color: str | None = None


class TagWithCount(TagRead):
    project_count: int = 0


class TagCreate(SQLModel):
    name: str
    color: str | None = None


class TagUpdate(SQLModel):
    name: str | None = None
    color: str | None = None


REPO_PATTERN = r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"


class ProjectBase(SQLModel):
    repo: Annotated[str, StringConstraints(strip_whitespace=True, pattern=REPO_PATTERN)]
    name: str | None = None
    workflow_version: WorkflowVersion = WorkflowVersion.v1
    base_branch: str = Field(default="main", min_length=1)
    head_branch: str = Field(default="release", min_length=1)
    description: str | None = None
    deploy_environments: list[str] | None = None


class ProjectCreate(ProjectBase):
    tags: list[str] = []
    teams: list[str] = []


class ProjectUpdate(SQLModel):
    name: str | None = None
    workflow_version: WorkflowVersion | None = None
    base_branch: str | None = Field(default=None, min_length=1)
    head_branch: str | None = Field(default=None, min_length=1)
    description: str | None = None
    deploy_environments: list[str] | None = None
    archived: bool | None = None
    starred: bool | None = None
    tags: list[str] | None = None
    teams: list[str] | None = None


class ProjectRead(ProjectBase):
    id: int
    name: str
    archived: bool
    starred: bool = False
    created_at: datetime
    updated_at: datetime
    tags: list[TagRead] = []
    teams: list[TeamRead] = []


class WorkflowPresetBase(SQLModel):
    environment: str
    version: WorkflowVersion = WorkflowVersion.v1
    workflow_file: str
    branch: str | None = None
    inputs: dict = {}
    description: str | None = None
    lock_branch: bool = False


class WorkflowPresetRead(WorkflowPresetBase):
    id: int


class WorkflowPresetCreate(WorkflowPresetBase):
    pass


class WorkflowPresetUpdate(SQLModel):
    environment: str | None = None
    version: WorkflowVersion | None = None
    workflow_file: str | None = None
    branch: str | None = None
    inputs: dict | None = None
    description: str | None = None
    lock_branch: bool | None = None


class DeploymentCreate(SQLModel):
    project_id: int
    environment: str
    branch: str | None = None


class DeploymentRead(SQLModel):
    id: int
    project_id: int
    project_name: str
    repo: str
    environment: str
    workflow_file: str
    branch: str
    inputs: dict
    status: str
    error: str | None = None
    run_id: int | None = None
    run_url: str | None = None
    triggered_by: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ReleaseRead(SQLModel):
    id: int
    project_id: int
    tag: str
    name: str | None = None
    url: str | None = None
    published_at: datetime


class DeployTarget(SQLModel):
    environment: str
    preset_id: int
    workflow_file: str
    branch: str
    inputs: dict
    description: str | None = None
    lock_branch: bool = False
    last_deployment: DeploymentRead | None = None


class DeployOverviewRow(SQLModel):
    project: ProjectRead
    latest_release: ReleaseRead | None = None
    targets: list[DeployTarget]


class SyncRunRead(SQLModel):
    id: int
    kind: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    details: dict

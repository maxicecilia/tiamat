"""Database models.

Project/Tag/WorkflowPreset hold configuration that used to live in `.env` and
`commands/actions.py`. Deployment/Release/SyncRun hold history for metrics.
"""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class WorkflowVersion(StrEnum):
    v1 = "v1"
    v2 = "v2"


class ProjectTag(SQLModel, table=True):
    __tablename__ = "project_tag"
    project_id: int = Field(foreign_key="project.id", primary_key=True, ondelete="CASCADE")
    tag_id: int = Field(foreign_key="tag.id", primary_key=True, ondelete="CASCADE")


class ProjectTeam(SQLModel, table=True):
    __tablename__ = "project_team"
    project_id: int = Field(foreign_key="project.id", primary_key=True, ondelete="CASCADE")
    team_id: int = Field(foreign_key="team.id", primary_key=True, ondelete="CASCADE")


class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)

    projects: list["Project"] = Relationship(back_populates="teams", link_model=ProjectTeam)


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    color: str | None = None

    projects: list["Project"] = Relationship(back_populates="tags", link_model=ProjectTag)


class Project(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    repo: str = Field(unique=True, index=True, description="Full 'org/name' GitHub repo")
    name: str = Field(index=True)
    workflow_version: WorkflowVersion = WorkflowVersion.v1
    base_branch: str = "main"
    head_branch: str = "release"
    description: str | None = None
    # Deploy environments enabled for this project; None means every preset environment.
    deploy_environments: list[str] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True))
    )
    archived: bool = False
    # Favourites: shown first everywhere.
    starred: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    tags: list[Tag] = Relationship(
        back_populates="projects",
        link_model=ProjectTag,
        sa_relationship_kwargs={"order_by": "Tag.name"},
    )
    teams: list[Team] = Relationship(
        back_populates="projects",
        link_model=ProjectTeam,
        sa_relationship_kwargs={"order_by": "Team.name"},
    )


class WorkflowPreset(SQLModel, table=True):
    """A deployable environment: which workflow file runs for a workflow version."""

    __tablename__ = "workflow_preset"
    __table_args__ = (UniqueConstraint("environment", "version"),)

    id: int | None = Field(default=None, primary_key=True)
    environment: str = Field(index=True)
    version: WorkflowVersion = WorkflowVersion.v1
    workflow_file: str
    branch: str | None = None
    inputs: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    description: str | None = None
    # When set, deploys must use the preset's branch (or the project's base branch);
    # the dashboard won't accept another one. On for prod by default.
    lock_branch: bool = False


class Deployment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True, ondelete="CASCADE")
    environment: str = Field(index=True)
    workflow_file: str
    workflow_id: int | None = None
    branch: str
    inputs: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    # dispatching -> dispatched (waiting for GitHub to report the run) -> queued/in_progress
    # -> a run conclusion (success, failure, cancelled, ...), or error/unknown.
    status: str = Field(default="dispatching", index=True)
    error: str | None = None
    run_id: int | None = None
    run_url: str | None = None
    triggered_by: str | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)
    # Set just before the dispatch request; used to match the run GitHub starts.
    dispatched_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # Last time the poller heard from GitHub about this deployment.
    checked_at: datetime | None = None


class Release(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("project_id", "tag"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True, ondelete="CASCADE")
    tag: str
    name: str | None = None
    url: str | None = None
    published_at: datetime = Field(index=True)
    # GitHub's release `created_at`; `stats` buckets and measures lead time from it,
    # so metrics use it too (falling back to published_at).
    created_at: datetime | None = Field(default=None, index=True)
    # Hours from the oldest commit since the previous release to this release.
    lead_time_hours: float | None = None
    # Derived from release notes with the same rules as `stats` (see GitHubService).
    is_failed: bool = False
    tickets: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    # When lead time was last computed (None = not yet).
    enriched_at: datetime | None = None


class SyncRun(SQLModel, table=True):
    __tablename__ = "sync_run"

    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(index=True)
    status: str = "running"
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    details: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class Integration(SQLModel, table=True):
    """Placeholder for Jira and other integrations. Secrets stay in the env, not here."""

    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(index=True)
    name: str
    enabled: bool = True
    config: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))

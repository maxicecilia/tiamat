"""Import the existing `.env` repo lists and workflow presets into the database.

Each step runs once per database, marked by a `SyncRun` row, so projects deleted
or edited in the dashboard are never re-created or overwritten from `.env`.
"""

import os

from sqlmodel import Session, select

from api.labels import resolve_teams
from api.models import Project, SyncRun, Tag, WorkflowPreset, WorkflowVersion, utcnow
from services.presets import load_deploy_presets

# Team env var -> team name. A repo joins every team whose list includes it,
# matching how `stats --team` groups repos (fnd = REPOSITORIES + FE_REPOSITORIES).
TEAM_ENV = [
    ("BETA_REPOSITORIES", "beta"),
    ("ML_REPOSITORIES", "ml"),
    ("DATAOPS_REPOSITORIES", "dataops"),
    ("REPOSITORIES", "fnd"),
    ("FE_REPOSITORIES", "fnd"),
]
# Repos only listed here get this team so they are not left without one.
FALLBACK_TEAM = ("REPOSITORIES_v2", "fnd")


def _env_list(name: str) -> list[str]:
    return [r.strip() for r in os.getenv(name, "").split(",") if r.strip()]


def _get_or_create_tag(session: Session, name: str) -> Tag:
    tag = session.exec(select(Tag).where(Tag.name == name)).first()
    if not tag:
        tag = Tag(name=name)
        session.add(tag)
    return tag


def env_teams() -> dict[str, list[str]]:
    """repo -> team names from the `.env` lists, in first-seen order."""
    teams: dict[str, list[str]] = {}
    for env_name, team in TEAM_ENV:
        for repo in _env_list(env_name):
            if team not in teams.setdefault(repo, []):
                teams[repo].append(team)
    env_name, team = FALLBACK_TEAM
    for repo in _env_list(env_name):
        teams.setdefault(repo, [team])
    return teams


def seed_projects_from_env(session: Session) -> int:
    v2 = set(_env_list("REPOSITORIES_v2"))
    frontend = set(_env_list("FE_REPOSITORIES"))
    existing = set(session.exec(select(Project.repo)).all())

    added = 0
    for repo, teams in env_teams().items():
        if repo in existing or "/" not in repo:
            continue
        project = Project(
            repo=repo,
            name=repo.split("/", 1)[1],
            workflow_version=WorkflowVersion.v2 if repo in v2 else WorkflowVersion.v1,
        )
        session.add(project)  # before resolving, so autoflush can persist it with its teams
        project.teams = resolve_teams(session, teams)
        if repo in frontend:
            project.tags.append(_get_or_create_tag(session, "frontend"))
        session.add(project)
        added += 1
    return added


def seed_workflow_presets(session: Session) -> int:
    existing = {(p.environment, p.version) for p in session.exec(select(WorkflowPreset)).all()}
    added = 0
    for env, cfg in load_deploy_presets().items():
        rows = [
            (WorkflowVersion.v1, cfg["workflow"], cfg.get("branch"), cfg.get("inputs", {})),
        ]
        if "v2" in cfg:
            # v2 workflows only take the branch as input.
            rows.append((WorkflowVersion.v2, cfg["v2"]["workflow"], cfg.get("branch"), {}))
        for version, workflow_file, branch, inputs in rows:
            if (env, version) in existing:
                continue
            session.add(
                WorkflowPreset(
                    environment=env,
                    version=version,
                    workflow_file=workflow_file,
                    branch=branch,
                    inputs=inputs,
                    description=cfg.get("description"),
                    lock_branch="prod" in env.lower(),
                )
            )
            added += 1
    return added


def _once(session: Session, kind: str, step) -> int | dict | None:
    if session.exec(select(SyncRun).where(SyncRun.kind == kind)).first():
        return None
    result = step(session)
    details = result if isinstance(result, dict) else {"added": result}
    session.add(SyncRun(kind=kind, status="success", finished_at=utcnow(), details=details))
    session.commit()
    return result


def _seed_projects_and_presets(session: Session) -> dict[str, int]:
    return {
        "projects": seed_projects_from_env(session),
        "workflow_presets": seed_workflow_presets(session),
    }


def backfill_teams_from_env(session: Session) -> int:
    """Add `.env` team memberships to projects seeded when a project could only have one team.

    Only touches projects whose teams still come from `.env` (a non-empty subset of their
    `.env` teams); projects whose teams were changed or cleared in the dashboard are left
    alone. Only adds teams, never removes any."""
    teams_by_repo = env_teams()
    added = 0
    for project in session.exec(select(Project)).all():
        current = {t.name for t in project.teams}
        env = teams_by_repo.get(project.repo, [])
        if not current or not current <= set(env):
            continue
        missing = [t for t in env if t not in current]
        if missing:
            project.teams = [*project.teams, *resolve_teams(session, missing)]
            session.add(project)
            added += len(missing)
    return added


def seed(session: Session) -> dict[str, int]:
    result = _once(session, "seed", _seed_projects_and_presets) or {
        "projects": 0,
        "workflow_presets": 0,
    }
    result["team_memberships"] = _once(session, "seed-teams", backfill_teams_from_env) or 0
    return result


if __name__ == "__main__":
    from api.db import engine

    with Session(engine) as s:
        print(seed(s))

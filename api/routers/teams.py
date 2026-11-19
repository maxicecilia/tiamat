from fastapi import APIRouter, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from api.db import SessionDep
from api.labels import normalize
from api.models import ProjectTeam, Team
from api.schemas import TeamRead, TeamUpdate, TeamWithCount

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[TeamWithCount])
def list_teams(session: SessionDep):
    rows = session.exec(
        select(Team, func.count(ProjectTeam.project_id))
        .outerjoin(ProjectTeam, ProjectTeam.team_id == Team.id)
        .group_by(Team.id)
        .order_by(Team.name)
    ).all()
    return [TeamWithCount(id=t.id, name=t.name, project_count=n) for t, n in rows]


@router.post("", response_model=TeamRead, status_code=201)
def create_team(data: TeamUpdate, session: SessionDep):
    name = normalize(data.name)
    if not name:
        raise HTTPException(422, "Team name is required")
    team = Team(name=name)
    session.add(team)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, f"Team {name} already exists") from None
    session.refresh(team)
    return team


@router.patch("/{team_id}", response_model=TeamRead)
def rename_team(team_id: int, data: TeamUpdate, session: SessionDep):
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    name = normalize(data.name)
    if not name:
        raise HTTPException(422, "Team name is required")
    team.name = name
    session.add(team)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, f"Team {name} already exists") from None
    session.refresh(team)
    return team


@router.delete("/{team_id}", status_code=204)
def delete_team(team_id: int, session: SessionDep):
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    session.delete(team)
    session.commit()

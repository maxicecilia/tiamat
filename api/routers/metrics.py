from fastapi import APIRouter, Query

from api import metrics
from api.db import SessionDep
from api.labels import normalize

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def get_metrics(
    session: SessionDep,
    months: int = Query(6, ge=1, le=24),
    team: str | None = None,
):
    return metrics.compute(session, months, normalize(team) if team and team.strip() else None)


@router.get("/releases")
def list_releases(
    session: SessionDep,
    months: int = Query(6, ge=1, le=24),
    team: str | None = None,
    limit: int = Query(200, ge=1, le=2000),
):
    team = normalize(team) if team and team.strip() else None
    return metrics.release_rows(session, months, team, limit)

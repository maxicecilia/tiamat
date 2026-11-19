"""Shared helpers for name-only labels (tags and teams), stored lowercase."""

from sqlmodel import Session, select

from api.models import Tag, Team


def normalize(name: str) -> str:
    return name.strip().lower()


def _resolve(session: Session, model, names: list[str]):
    rows = []
    for name in dict.fromkeys(normalize(n) for n in names if n.strip()):
        rows.append(
            session.exec(select(model).where(model.name == name)).first() or model(name=name)
        )
    return rows


def resolve_tags(session: Session, names: list[str]) -> list[Tag]:
    return _resolve(session, Tag, names)


def resolve_teams(session: Session, names: list[str]) -> list[Team]:
    return _resolve(session, Team, names)

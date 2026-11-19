from fastapi import APIRouter, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from api.db import SessionDep
from api.models import ProjectTag, Tag
from api.schemas import TagCreate, TagRead, TagUpdate, TagWithCount

router = APIRouter(prefix="/tags", tags=["tags"])


def _commit(session: Session, name: str | None) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, f"Tag {name} already exists") from None


def _get(session: Session, tag_id: int) -> Tag:
    tag = session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    return tag


@router.get("", response_model=list[TagWithCount])
def list_tags(session: SessionDep):
    counts = (
        select(Tag, func.count(ProjectTag.project_id))
        .outerjoin(ProjectTag, ProjectTag.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    return [
        TagWithCount(id=t.id, name=t.name, color=t.color, project_count=n)
        for t, n in session.exec(counts).all()
    ]


@router.post("", response_model=TagRead, status_code=201)
def create_tag(data: TagCreate, session: SessionDep):
    name = data.name.strip().lower()
    if not name:
        raise HTTPException(422, "Tag name is required")
    tag = Tag(name=name, color=data.color)
    session.add(tag)
    _commit(session, name)
    session.refresh(tag)
    return tag


@router.patch("/{tag_id}", response_model=TagRead)
def update_tag(tag_id: int, data: TagUpdate, session: SessionDep):
    tag = _get(session, tag_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        name = (changes.pop("name") or "").strip().lower()
        if not name:
            raise HTTPException(422, "Tag name is required")
        tag.name = name
    if "color" in changes:
        tag.color = changes["color"]
    session.add(tag)
    _commit(session, tag.name)
    session.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=204)
def delete_tag(tag_id: int, session: SessionDep):
    session.delete(_get(session, tag_id))
    session.commit()

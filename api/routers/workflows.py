from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from api.db import SessionDep
from api.models import Project, WorkflowPreset
from api.schemas import WorkflowPresetCreate, WorkflowPresetRead, WorkflowPresetUpdate

router = APIRouter(prefix="/workflow-presets", tags=["workflows"])

NULLABLE_FIELDS = {"branch", "description"}


def _get(session: Session, preset_id: int) -> WorkflowPreset:
    preset = session.get(WorkflowPreset, preset_id)
    if not preset:
        raise HTTPException(404, "Workflow preset not found")
    return preset


def _commit(session: Session, preset: WorkflowPreset, before_commit=None) -> None:
    env, version = preset.environment, preset.version  # read before rollback reloads them
    try:
        session.flush()
        if before_commit:
            before_commit()
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, f"A {version} preset for '{env}' already exists") from None


def _sync_project_environments(session: Session, version, old: str, new: str | None) -> None:
    """Rename (or drop, when `new` is None) an environment in projects that list it explicitly.

    Skipped while another preset still provides `old` for the same version.
    """
    still_exists = session.exec(
        select(WorkflowPreset).where(
            WorkflowPreset.environment == old, WorkflowPreset.version == version
        )
    ).first()
    if still_exists:
        return
    projects = session.exec(select(Project).where(Project.workflow_version == version)).all()
    for project in projects:
        envs = project.deploy_environments
        if envs is None or old not in envs:
            continue
        renamed = [new if e == old else e for e in envs if new is not None or e != old]
        project.deploy_environments = list(dict.fromkeys(renamed))
        session.add(project)


def _validate(preset: WorkflowPreset) -> None:
    preset.environment = preset.environment.strip()
    preset.workflow_file = preset.workflow_file.strip()
    if not preset.environment or not preset.workflow_file:
        raise HTTPException(422, "environment and workflow_file are required")
    if not all(isinstance(v, str) for v in preset.inputs.values()):
        raise HTTPException(422, "workflow inputs must be strings")


@router.get("", response_model=list[WorkflowPresetRead])
def list_presets(session: SessionDep):
    return session.exec(
        select(WorkflowPreset).order_by(WorkflowPreset.environment, WorkflowPreset.version)
    ).all()


@router.post("", response_model=WorkflowPresetRead, status_code=201)
def create_preset(data: WorkflowPresetCreate, session: SessionDep):
    preset = WorkflowPreset.model_validate(data)
    _validate(preset)
    session.add(preset)
    _commit(session, preset)
    session.refresh(preset)
    return preset


@router.patch("/{preset_id}", response_model=WorkflowPresetRead)
def update_preset(preset_id: int, data: WorkflowPresetUpdate, session: SessionDep):
    preset = _get(session, preset_id)
    old_env, old_version = preset.environment, preset.version
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is not None or key in NULLABLE_FIELDS:
            setattr(preset, key, value)
    _validate(preset)
    session.add(preset)

    def sync():
        if (preset.environment, preset.version) != (old_env, old_version):
            same_version = preset.version == old_version
            _sync_project_environments(
                session, old_version, old_env, preset.environment if same_version else None
            )

    _commit(session, preset, before_commit=sync)
    session.refresh(preset)
    return preset


@router.delete("/{preset_id}", status_code=204)
def delete_preset(preset_id: int, session: SessionDep):
    preset = _get(session, preset_id)
    session.delete(preset)
    session.flush()
    _sync_project_environments(session, preset.version, preset.environment, None)
    session.commit()

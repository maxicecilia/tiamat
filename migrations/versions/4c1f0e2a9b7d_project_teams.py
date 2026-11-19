"""project teams: many-to-many instead of a single team column

Revision ID: 4c1f0e2a9b7d
Revises: 1838e756cdb9
Create Date: 2026-11-18

Existing `project.team` values become rows in `team`/`project_team`
(trimmed and lowercased), then the column is dropped.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "4c1f0e2a9b7d"
down_revision: str | None = "1838e756cdb9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "team",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("team", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_team_name"), ["name"], unique=True)

    op.create_table(
        "project_team",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "team_id"),
    )

    # Normalise in Python (str.strip().lower(), as the API does), not SQLite's
    # ASCII-only lower() / space-only trim().
    conn = op.get_bind()
    team_ids: dict[str, int] = {}
    rows = conn.execute(sa.text("SELECT id, team FROM project WHERE team IS NOT NULL")).all()
    for project_id, raw in rows:
        name = raw.strip().lower()
        if not name:
            continue
        if name not in team_ids:
            conn.execute(sa.text("INSERT INTO team (name) VALUES (:name)"), {"name": name})
            team_ids[name] = conn.execute(
                sa.text("SELECT id FROM team WHERE name = :name"), {"name": name}
            ).scalar_one()
        conn.execute(
            sa.text("INSERT INTO project_team (project_id, team_id) VALUES (:p, :t)"),
            {"p": project_id, "t": team_ids[name]},
        )

    with op.batch_alter_table("project", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_project_team"))
        batch_op.drop_column("team")


def downgrade() -> None:
    with op.batch_alter_table("project", schema=None) as batch_op:
        batch_op.add_column(sa.Column("team", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.create_index(batch_op.f("ix_project_team"), ["team"], unique=False)
    # A project keeps only its alphabetically first team.
    op.execute(
        """
        UPDATE project SET team = (
            SELECT min(team.name) FROM project_team
            JOIN team ON team.id = project_team.team_id
            WHERE project_team.project_id = project.id
        )
        """
    )
    op.drop_table("project_team")
    with op.batch_alter_table("team", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_team_name"))
    op.drop_table("team")

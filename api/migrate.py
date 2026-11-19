"""Run Alembic migrations programmatically (used on API startup)."""

from alembic import command
from alembic.config import Config

from api.config import DATABASE_URL, ROOT_DIR


def alembic_config(url: str = DATABASE_URL) -> Config:
    cfg = Config(str(ROOT_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def upgrade_to_head(url: str = DATABASE_URL) -> None:
    command.upgrade(alembic_config(url), "head")

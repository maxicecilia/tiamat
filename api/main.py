"""Tiamat dashboard API.

Run locally: `uv run uvicorn api.main:app --reload`
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from api.config import ALLOWED_HOSTS, CORS_ORIGINS, ROOT_DIR
from api.db import engine
from api.deploys import poll_active
from api.migrate import upgrade_to_head
from api.releases import close_interrupted_runs
from api.routers import bump, deploys, metrics, projects, pulls, tags, teams, workflows
from api.seed import seed

STATIC_DIR = ROOT_DIR / "frontend" / "dist"


POLL_SECONDS = int(os.getenv("TIAMAT_POLL_SECONDS", "10"))
log = logging.getLogger("tiamat")


def _poll_once() -> None:
    with Session(engine) as session:
        poll_active(session)


async def _poll_deployments() -> None:
    """Keep in-flight deployments in sync with their GitHub Actions runs."""
    while True:
        try:
            await asyncio.to_thread(_poll_once)
        except Exception:
            log.exception("Deployment poll failed")
        await asyncio.sleep(POLL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    upgrade_to_head()
    with Session(engine) as session:
        seed(session)
        close_interrupted_runs(session)
    poller = None
    if os.getenv("TIAMAT_DISABLE_POLLER") != "1":
        poller = asyncio.create_task(_poll_deployments())
    yield
    if poller:
        poller.cancel()
        with suppress(asyncio.CancelledError):
            await poller


app = FastAPI(title="Tiamat", lifespan=lifespan)
# The API has no auth: only answer requests addressed to this machine (blocks DNS rebinding).
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"]
)

for router in (
    projects.router,
    tags.router,
    teams.router,
    workflows.router,
    deploys.router,
    metrics.router,
    pulls.router,
    bump.router,
):
    app.include_router(router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the built frontend (production / docker). In dev, Vite serves it instead.
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not found")
        file = STATIC_DIR / path
        if path and file.is_file() and file.resolve().is_relative_to(STATIC_DIR.resolve()):
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")

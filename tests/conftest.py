import os
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="tiamat-test-"))
os.environ["TIAMAT_DATA_DIR"] = str(_tmp)
os.environ["TIAMAT_DISABLE_POLLER"] = "1"
os.environ["TIAMAT_DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
# Deterministic seed input, independent of the developer's .env.
os.environ["REPOSITORIES"] = "acme/api,acme/web"
os.environ["REPOSITORIES_v2"] = "acme/worker"
os.environ["FE_REPOSITORIES"] = "acme/web"
os.environ["BETA_REPOSITORIES"] = "acme/beta-svc,acme/web"
os.environ["ML_REPOSITORIES"] = ""
os.environ["DATAOPS_REPOSITORIES"] = ""
os.environ["TIAMAT_PRESETS_FILE"] = str(Path(__file__).parent.parent / "presets.example.json")

from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests must never reach GitHub or Slack for real."""

    def blocked(*args, **kwargs):
        raise AssertionError(f"Unexpected network call: {args[:2]}")

    import requests

    for name in ("request", "get", "post", "put", "patch", "delete"):
        monkeypatch.setattr(requests, name, blocked)

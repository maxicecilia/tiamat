from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select

from api import deploys
from api.db import engine
from api.models import Deployment, Release
from services import github_api as gh


class FakeGitHub:
    """In-memory stand-in for services.github_api."""

    def __init__(self):
        self.dispatches = []
        self.runs = {}
        self.dispatch_returns_run_id = True
        self.fail_dispatch = None
        self.releases = {}
        self.compares = []
        self.commit_dates = {}

    def install(self, monkeypatch):
        monkeypatch.setattr(gh, "is_configured", lambda: True)
        monkeypatch.setattr(gh, "resolve_workflow_id", lambda repo, wf: 4242)
        monkeypatch.setattr(gh, "dispatch_workflow", self.dispatch)
        monkeypatch.setattr(gh, "get_run", lambda repo, run_id: self.runs[run_id])
        monkeypatch.setattr(gh, "list_dispatch_runs", self.list_runs)
        monkeypatch.setattr(gh, "list_releases_since", self.list_releases)
        monkeypatch.setattr(gh, "oldest_commit_date", self.oldest_commit)
        monkeypatch.setattr(gh, "token_login", lambda repo: "tiamat-bot")

    def dispatch(self, repo, workflow_id, ref, inputs):
        if self.fail_dispatch:
            raise gh.GitHubError(self.fail_dispatch, 422)
        self.dispatches.append((repo, workflow_id, ref, inputs))
        run_id = 1000 + len(self.dispatches)
        self.runs[run_id] = {
            "id": run_id,
            "status": "queued",
            "conclusion": None,
            "html_url": f"https://github.com/{repo}/actions/runs/{run_id}",
            "triggering_actor": {"login": "tiamat-bot"},
            "created_at": datetime.now(UTC).isoformat(),
            "run_started_at": None,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        return run_id if self.dispatch_returns_run_id else None

    def list_runs(self, repo, workflow_id, branch, created_after):
        return list(self.runs.values())

    def oldest_commit(self, repo, base, head):
        self.compares.append((repo, base, head))
        value = self.commit_dates.get((repo, head))
        if isinstance(value, Exception):
            raise value
        return value

    def list_releases(self, repo, since):
        if repo in self.releases and isinstance(self.releases[repo], Exception):
            raise self.releases[repo]
        return self.releases.get(repo, [])


@pytest.fixture
def fake_gh(monkeypatch):
    fake = FakeGitHub()
    fake.install(monkeypatch)
    yield fake
    with Session(engine) as s:
        for model in (Deployment, Release):
            for row in s.exec(select(model)):
                s.delete(row)
        s.commit()


def _project(client, repo):
    return next(p for p in client.get("/api/projects").json() if p["repo"] == repo)


def test_overview_lists_environments_per_workflow_version(client):
    rows = {r["project"]["repo"]: r for r in client.get("/api/deploys/overview").json()}
    v1 = rows["acme/api"]["targets"]
    assert [t["environment"] for t in v1] == ["staging", "demo", "prod"]
    staging = v1[0]
    assert staging["workflow_file"] == "deploy-staging.yml"
    assert staging["branch"] == "release"
    assert staging["inputs"] == {"stage": "staging"}
    assert rows["acme/worker"]["targets"][2]["workflow_file"] == "release-prod.yml"


def test_deploy_dispatches_preset_and_tracks_run(client, fake_gh):
    p = _project(client, "acme/worker")
    r = client.post("/api/deployments", json={"project_id": p["id"], "environment": "prod"})
    assert r.status_code == 201, r.text
    dep = r.json()
    assert fake_gh.dispatches == [("acme/worker", 4242, "main", {})]
    assert dep["status"] == "queued"
    assert dep["run_url"].endswith("/runs/1001")

    # A second deploy while the first is running is refused.
    again = client.post("/api/deployments", json={"project_id": p["id"], "environment": "prod"})
    assert again.status_code == 409

    fake_gh.runs[1001] |= {"status": "completed", "conclusion": "success"}
    with Session(engine) as s:
        assert deploys.poll_active(s) == 1
    done = client.get("/api/deployments", params={"project_id": p["id"]}).json()[0]
    assert done["status"] == "success"
    assert done["finished_at"] is not None
    prod_only = client.get(
        "/api/deployments", params={"project_id": p["id"], "environment": "prod"}
    ).json()
    assert [d["id"] for d in prod_only] == [dep["id"]]
    assert client.get("/api/deployments", params={"environment": "staging"}).json() == []

    row = next(
        r for r in client.get("/api/deploys/overview").json() if r["project"]["id"] == p["id"]
    )
    prod = next(t for t in row["targets"] if t["environment"] == "prod")
    assert prod["last_deployment"]["status"] == "success"


def test_branch_override_and_run_lookup_without_run_id(client, fake_gh):
    fake_gh.dispatch_returns_run_id = False
    p = _project(client, "acme/api")
    r = client.post(
        "/api/deployments",
        json={"project_id": p["id"], "environment": "staging", "branch": "hotfix"},
    )
    dep = r.json()
    assert fake_gh.dispatches[0][2] == "hotfix"
    assert fake_gh.dispatches[0][3] == {"stage": "staging"}
    # The run was found by listing workflow_dispatch runs.
    assert dep["run_id"] == 1001
    assert dep["status"] == "queued"


def test_dispatch_failure_is_recorded(client, fake_gh):
    fake_gh.fail_dispatch = "Workflow does not have 'workflow_dispatch' trigger"
    p = _project(client, "acme/api")
    dep = client.post(
        "/api/deployments", json={"project_id": p["id"], "environment": "demo"}
    ).json()
    assert dep["status"] == "error"
    assert "workflow_dispatch" in dep["error"]
    # A failed dispatch does not block a retry.
    fake_gh.fail_dispatch = None
    retry = client.post("/api/deployments", json={"project_id": p["id"], "environment": "demo"})
    assert retry.status_code == 201


def test_unknown_or_disabled_environment(client, fake_gh):
    p = client.post(
        "/api/projects", json={"repo": "acme/limited", "deploy_environments": ["staging"]}
    ).json()
    r = client.post("/api/deployments", json={"project_id": p["id"], "environment": "prod"})
    assert r.status_code == 404
    assert fake_gh.dispatches == []
    client.delete(f"/api/projects/{p['id']}")


def test_missing_token_returns_503(client, monkeypatch):
    monkeypatch.setattr(gh, "is_configured", lambda: False)
    p = _project(client, "acme/api")
    r = client.post("/api/deployments", json={"project_id": p["id"], "environment": "staging"})
    assert r.status_code == 503
    with Session(engine) as s:
        assert s.exec(select(Deployment)).first() is None


def test_run_lookup_gives_up(client, fake_gh, monkeypatch):
    monkeypatch.setattr(gh, "dispatch_workflow", lambda *a: None)
    p = _project(client, "acme/api")
    dep_id = client.post(
        "/api/deployments", json={"project_id": p["id"], "environment": "staging"}
    ).json()["id"]
    with Session(engine) as s:
        dep = s.get(Deployment, dep_id)
        dep.created_at = dep.dispatched_at = datetime.now(UTC) - timedelta(minutes=11)
        s.add(dep)
        s.commit()
        deploys.poll_active(s)
        assert s.get(Deployment, dep_id).status == "unknown"


def _dep_id(client, repo, env, **extra):
    p = _project(client, repo)
    r = client.post("/api/deployments", json={"project_id": p["id"], "environment": env, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_uncertain_dispatch_keeps_looking_instead_of_failing(client, fake_gh, monkeypatch):
    def timeout(*a):
        raise gh.GitHubUncertain("No response from GitHub: read timed out")

    monkeypatch.setattr(gh, "dispatch_workflow", timeout)
    dep = _dep_id(client, "acme/api", "prod")
    assert dep["status"] == "dispatched"
    assert "did not confirm" in dep["error"]
    # Still active, so a second (possibly duplicate) prod deploy is refused.
    p = _project(client, "acme/api")
    assert (
        client.post(
            "/api/deployments", json={"project_id": p["id"], "environment": "prod"}
        ).status_code
        == 409
    )


def test_unexpected_exception_never_leaves_dispatching(client, fake_gh, monkeypatch):
    def boom(*a):
        raise KeyError("workflows")

    monkeypatch.setattr(gh, "resolve_workflow_id", boom)
    dep = _dep_id(client, "acme/api", "staging")
    assert dep["status"] == "error"


def test_stale_dispatching_row_is_swept(client, fake_gh):
    p = _project(client, "acme/api")
    with Session(engine) as s:
        dep = Deployment(
            project_id=p["id"],
            environment="demo",
            workflow_file="x.yml",
            branch="release",
            status="dispatching",
            created_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        s.add(dep)
        s.commit()
        dep_id = dep.id
        deploys.poll_active(s)
        swept = s.get(Deployment, dep_id)
        assert swept.status == "unknown"
        assert "Interrupted" in swept.error


def test_run_that_disappears_becomes_unknown(client, fake_gh, monkeypatch):
    dep = _dep_id(client, "acme/worker", "staging")

    def gone(repo, run_id):
        raise gh.GitHubError("Not Found", 404)

    monkeypatch.setattr(gh, "get_run", gone)
    with Session(engine) as s:
        deploys.poll_active(s)
        assert s.get(Deployment, dep["id"]).status == "unknown"


def test_transient_error_keeps_deployment_active(client, fake_gh, monkeypatch):
    dep = _dep_id(client, "acme/worker", "demo")

    def flaky(repo, run_id):
        raise gh.GitHubError("Server Error", 502)

    monkeypatch.setattr(gh, "get_run", flaky)
    with Session(engine) as s:
        deploys.poll_active(s)
        assert s.get(Deployment, dep["id"]).status == "queued"


def test_run_matching_ignores_other_peoples_runs(client, fake_gh, monkeypatch):
    fake_gh.dispatch_returns_run_id = False
    now = datetime.now(UTC).isoformat()
    fake_gh.runs[900] = {
        "id": 900,
        "status": "in_progress",
        "conclusion": None,
        "html_url": "theirs",
        "created_at": now,
        "run_started_at": None,
        "updated_at": now,
        "triggering_actor": {"login": "a-colleague"},
    }
    dep = _dep_id(client, "acme/api", "demo")
    assert dep["run_id"] == 1001
    assert dep["run_url"].endswith("/runs/1001")


def test_dismiss_unblocks_environment(client, fake_gh):
    dep = _dep_id(client, "acme/worker", "prod")
    r = client.post(f"/api/deployments/{dep['id']}/dismiss")
    assert r.json()["status"] == "dismissed"
    assert _dep_id(client, "acme/worker", "prod")["status"] == "queued"


def test_poll_continues_after_one_failure(client, fake_gh, monkeypatch):
    first = _dep_id(client, "acme/worker", "staging")
    second = _dep_id(client, "acme/worker", "demo")
    fake_gh.runs[second["run_id"]] |= {"status": "completed", "conclusion": "success"}
    real_get_run = gh.get_run

    def get_run(repo, run_id):
        if run_id == first["run_id"]:
            raise RuntimeError("bad payload")
        return real_get_run(repo, run_id)

    monkeypatch.setattr(gh, "get_run", get_run)
    with Session(engine) as s:
        deploys.poll_active(s)
        assert s.get(Deployment, second["id"]).status == "success"


def test_unknown_host_is_rejected(client):
    assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400


def _rel(tag, created, body="", **extra):
    return {
        "tag_name": tag,
        "name": None,
        "html_url": f"u/{tag}",
        "created_at": created,
        "published_at": created,
        "body": body,
        **extra,
    }


def _sync(client):
    assert client.post("/api/releases/sync").status_code == 202
    return client.get("/api/releases/sync/latest").json()


def test_release_sync_enriches_and_reports_errors(client, fake_gh):
    fake_gh.releases = {
        "acme/api": [
            _rel("1.2.0", "2026-11-10T10:00:00Z", "[ABC-1] [ABC-2] [hotfix] fix"),
            _rel("1.1.0", "2026-11-01T10:00:00Z", "[ABC-3] feature"),
        ],
        "acme/web": gh.GitHubError("Not Found", 404),
    }
    fake_gh.commit_dates = {("acme/api", "1.2.0"): datetime(2026, 11, 8, 10, tzinfo=UTC)}
    run = _sync(client)
    assert run["status"] == "partial"
    assert run["details"]["added"] == 2
    assert run["details"]["lead_times"] == 1
    assert run["details"]["errors"] == {"acme/web": "Not Found"}
    assert fake_gh.compares == [("acme/api", "1.1.0", "1.2.0")]

    with Session(engine) as s:
        rows = {r.tag: r for r in s.exec(select(Release))}
    assert rows["1.2.0"].tickets == ["ABC-1", "ABC-2"]
    assert rows["1.2.0"].is_failed is True
    assert rows["1.2.0"].lead_time_hours == 48.0
    assert rows["1.1.0"].is_failed is False
    assert rows["1.1.0"].lead_time_hours is None

    # A second sync updates in place and does not recompute lead time.
    fake_gh.compares.clear()
    assert _sync(client)["details"]["added"] == 0
    assert fake_gh.compares == []


def test_lead_time_errors_are_retried(client, fake_gh):
    fake_gh.releases = {
        "acme/api": [
            _rel("2.0.0", "2026-11-10T10:00:00Z"),
            _rel("1.9.0", "2026-11-01T10:00:00Z"),
        ]
    }
    fake_gh.commit_dates = {("acme/api", "2.0.0"): gh.GitHubError("rate limited", 403)}
    run = _sync(client)
    assert run["status"] == "partial"  # every repo synced; only lead times failed
    assert run["details"]["lead_time_errors"] == 1
    assert "lead times" in run["details"]["errors"]
    fake_gh.commit_dates = {("acme/api", "2.0.0"): datetime(2026, 11, 9, 10, tzinfo=UTC)}
    assert _sync(client)["details"]["lead_times"] == 1


def test_release_sync_skips_incomplete_releases(client, fake_gh):
    fake_gh.releases = {
        "acme/api": [
            {"tag_name": None, "created_at": "2026-11-10T10:00:00Z"},
            {"tag_name": "2.0.0", "published_at": None, "created_at": None},
            _rel("2.1.0", "2026-11-12T10:00:00Z"),
        ],
        "acme/web": ValueError("not json"),
    }
    run = _sync(client)
    assert run["details"]["added"] == 1
    assert "acme/web" in run["details"]["errors"]
    assert run["status"] == "partial"


def test_sync_endpoint_needs_token(client, monkeypatch):
    monkeypatch.setattr(gh, "is_configured", lambda: False)
    assert client.post("/api/releases/sync").status_code == 503


def test_recreated_tag_recomputes_lead_time(client, fake_gh):
    fake_gh.releases = {
        "acme/api": [_rel("3.1.0", "2026-11-10T10:00:00Z"), _rel("3.0.0", "2026-11-01T10:00:00Z")]
    }
    fake_gh.commit_dates = {("acme/api", "3.1.0"): datetime(2026, 11, 9, 10, tzinfo=UTC)}
    _sync(client)
    fake_gh.compares.clear()
    # The tag is deleted and released again two days later.
    fake_gh.releases["acme/api"][0] = _rel("3.1.0", "2026-11-12T10:00:00Z")
    _sync(client)
    assert fake_gh.compares == [("acme/api", "3.0.0", "3.1.0")]
    with Session(engine) as s:
        r = s.exec(select(Release).where(Release.tag == "3.1.0")).one()
        assert r.lead_time_hours == 72.0


def test_stale_running_sync_is_closed(client, fake_gh):
    from api.models import SyncRun

    with Session(engine) as s:
        s.add(
            SyncRun(kind="releases", status="running", started_at=datetime(2026, 1, 1, tzinfo=UTC))
        )
        s.commit()
    latest = client.get("/api/releases/sync/latest").json()
    assert latest["status"] == "error"
    assert "Interrupted" in latest["details"]["errors"]["sync"]
    # A new sync can start.
    assert _sync(client)["status"] in {"success", "partial"}


def test_prod_is_locked_to_its_branch(client, fake_gh):
    p = _project(client, "acme/api")
    prod = next(
        t
        for r in client.get("/api/deploys/overview").json()
        if r["project"]["id"] == p["id"]
        for t in r["targets"]
        if t["environment"] == "prod"
    )
    assert prod["lock_branch"] is True and prod["branch"] == "main"

    r = client.post(
        "/api/deployments", json={"project_id": p["id"], "environment": "prod", "branch": "hotfix"}
    )
    assert r.status_code == 409
    assert "locked to 'main'" in r.json()["detail"]
    assert fake_gh.dispatches == []

    # Sending the locked branch explicitly is fine.
    r = client.post(
        "/api/deployments", json={"project_id": p["id"], "environment": "prod", "branch": "main"}
    )
    assert r.status_code == 201
    assert fake_gh.dispatches[0][2] == "main"


def test_unlocking_a_preset_allows_other_branches(client, fake_gh):
    presets = client.get("/api/workflow-presets").json()
    prod_v1 = next(x for x in presets if x["environment"] == "prod" and x["version"] == "v1")
    staging_v1 = next(x for x in presets if x["environment"] == "staging" and x["version"] == "v1")
    assert prod_v1["lock_branch"] is True and staging_v1["lock_branch"] is False

    client.patch(f"/api/workflow-presets/{prod_v1['id']}", json={"lock_branch": False})
    try:
        p = _project(client, "acme/api")
        r = client.post(
            "/api/deployments",
            json={"project_id": p["id"], "environment": "prod", "branch": "hotfix"},
        )
        assert r.status_code == 201
        assert fake_gh.dispatches[0][2] == "hotfix"
    finally:
        client.patch(f"/api/workflow-presets/{prod_v1['id']}", json={"lock_branch": True})

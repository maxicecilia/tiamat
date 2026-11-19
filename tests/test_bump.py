import pytest
from sqlmodel import Session, select

from api.db import engine
from api.models import Release
from services import github_api as gh


@pytest.fixture
def fake(client, monkeypatch):
    """Fake GitHub releases (nothing is created for real)."""
    state = {"releases": {}, "created": [], "ahead": 3, "tags": set(), "drafts": {}}
    monkeypatch.setattr(gh, "is_configured", lambda: True)

    def list_releases(repo, limit=20, include_drafts=False):
        rows = list(state["releases"].get(repo, []))
        return rows + list(state["drafts"].get(repo, [])) if include_drafts else rows

    monkeypatch.setattr(gh, "list_releases", list_releases)
    monkeypatch.setattr(gh, "tag_exists", lambda repo, tag: tag in state["tags"])
    monkeypatch.setattr(
        gh,
        "compare_branches",
        lambda repo, base, head, max_commits=50: {"ahead_by": state["ahead"], "commits": []},
    )

    def create(repo, tag, target, name=None, draft=False, prerelease=False):
        state["created"].append((repo, tag, target, name, draft, prerelease))
        return {
            "tag_name": tag,
            "name": name,
            "html_url": f"https://github.com/{repo}/releases/{tag}",
            "draft": draft,
            "prerelease": prerelease,
            "created_at": "2026-11-18T12:00:00Z",
            "published_at": None if draft else "2026-11-18T12:00:00Z",
        }

    monkeypatch.setattr(gh, "create_release", create)
    yield state
    with Session(engine) as s:
        for r in s.exec(select(Release)):
            s.delete(r)
        s.commit()


def _pid(client, repo):
    return next(p["id"] for p in client.get("/api/projects").json() if p["repo"] == repo)


def _rel(tag, created, prerelease=False):
    return {
        "tag_name": tag,
        "created_at": created,
        "prerelease": prerelease,
        "html_url": f"u/{tag}",
    }


def test_plan_shows_candidates_and_unreleased_commits(client, fake):
    fake["releases"]["acme/api"] = [
        _rel("v1.4.0-rc1", "2026-11-12T00:00:00Z", prerelease=True),
        _rel("v1.3.2", "2026-11-10T00:00:00Z"),
        _rel("v1.3.1", "2026-11-01T00:00:00Z"),
    ]
    plan = client.get(f"/api/projects/{_pid(client, 'acme/api')}/next-version").json()
    assert plan["current"] == "v1.3.2"
    assert plan["candidates"] == {"major": "v2.0.0", "minor": "v1.4.0", "patch": "v1.3.3"}
    assert plan["unreleased_commits"] == 3
    assert plan["target"] == "main"
    assert plan["managed_by_workflow"] is False


def test_plan_without_releases_starts_at_zero(client, fake):
    plan = client.get(f"/api/projects/{_pid(client, 'acme/api')}/next-version").json()
    assert plan["current"] is None
    # Same starting point as the CLI (DEFAULT_VERSION 0.0.1).
    assert plan["candidates"] == {"major": "1.0.0", "minor": "0.1.0", "patch": "0.0.2"}
    assert plan["unreleased_commits"] is None


def test_non_semver_tag_needs_explicit_version(client, fake):
    fake["releases"]["acme/api"] = [_rel("3.4.0.web", "2026-11-10T00:00:00Z")]
    pid = _pid(client, "acme/api")
    plan = client.get(f"/api/projects/{pid}/next-version").json()
    assert plan["parseable"] is False
    assert plan["candidates"] == {}
    r = client.post(
        f"/api/projects/{pid}/releases",
        json={"bump": "minor", "expected_current": "3.4.0.web", "target": "main"},
    )
    assert r.status_code == 422
    assert fake["created"] == []
    r = client.post(
        f"/api/projects/{pid}/releases",
        json={"version": "3.5.0.web", "expected_current": "3.4.0.web", "target": "main"},
    )
    assert r.status_code == 201
    assert fake["created"][0][1] == "3.5.0.web"


def test_create_release_bumps_and_records_it(client, fake):
    fake["releases"]["acme/api"] = [_rel("v1.3.2", "2026-11-10T00:00:00Z")]
    pid = _pid(client, "acme/api")
    r = client.post(
        f"/api/projects/{pid}/releases",
        json={"bump": "minor", "expected_current": "v1.3.2", "target": "main"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["tag"] == "v1.4.0"
    assert fake["created"] == [("acme/api", "v1.4.0", "main", "v1.4.0", False, False)]
    with Session(engine) as s:
        assert s.exec(select(Release).where(Release.tag == "v1.4.0")).one().project_id == pid


def test_stale_view_is_refused(client, fake):
    fake["releases"]["acme/api"] = [_rel("v1.3.3", "2026-11-11T00:00:00Z")]
    pid = _pid(client, "acme/api")
    r = client.post(
        f"/api/projects/{pid}/releases",
        json={"bump": "patch", "expected_current": "v1.3.2", "target": "main"},
    )
    assert r.status_code == 409
    assert "v1.3.3" in r.json()["detail"]
    assert fake["created"] == []


def test_v2_projects_are_refused(client, fake):
    pid = _pid(client, "acme/worker")
    r = client.post(f"/api/projects/{pid}/releases", json={"bump": "minor", "target": "main"})
    assert r.status_code == 409
    assert "v2" in r.json()["detail"]
    assert fake["created"] == []


def test_drafts_are_not_recorded_and_errors_surface(client, fake, monkeypatch):
    pid = _pid(client, "acme/api")
    r = client.post(
        f"/api/projects/{pid}/releases", json={"bump": "patch", "target": "main", "draft": True}
    )
    assert r.status_code == 201
    with Session(engine) as s:
        assert s.exec(select(Release)).first() is None

    def exists(*a, **k):
        raise gh.GitHubError("Validation Failed: tag_name already exists", 422)

    monkeypatch.setattr(gh, "create_release", exists)
    r = client.post(f"/api/projects/{pid}/releases", json={"bump": "patch", "target": "main"})
    assert r.status_code == 502
    assert "already exists" in r.json()["detail"]


def test_timeout_says_release_may_exist(client, fake, monkeypatch):
    def timeout(*a, **k):
        raise gh.GitHubUncertain("No response from GitHub: read timed out")

    monkeypatch.setattr(gh, "create_release", timeout)
    pid = _pid(client, "acme/api")
    r = client.post(f"/api/projects/{pid}/releases", json={"bump": "patch", "target": "main"})
    assert r.status_code == 504
    assert "may have been created" in r.json()["detail"]


def test_existing_tag_or_draft_is_refused(client, fake):
    fake["releases"]["acme/api"] = [_rel("v1.3.2", "2026-11-10T00:00:00Z")]
    pid = _pid(client, "acme/api")
    body = {"bump": "minor", "expected_current": "v1.3.2", "target": "main"}

    fake["tags"] = {"v1.4.0"}  # tag pushed by hand, no release
    r = client.post(f"/api/projects/{pid}/releases", json=body)
    assert r.status_code == 409 and "Tag v1.4.0 already exists" in r.json()["detail"]

    fake["tags"] = set()
    fake["drafts"]["acme/api"] = [{"tag_name": "v1.4.0", "draft": True}]
    r = client.post(f"/api/projects/{pid}/releases", json=body)
    assert r.status_code == 409 and "draft" in r.json()["detail"]
    assert fake["created"] == []


@pytest.mark.parametrize("tag", ["main", "a..b", "-x", "v1 .0", "feat/x"])
def test_invalid_custom_tags(client, fake, tag):
    pid = _pid(client, "acme/api")
    r = client.post(f"/api/projects/{pid}/releases", json={"version": tag, "target": "main"})
    assert r.status_code == 422
    assert fake["created"] == []


def test_local_record_failure_still_reports_success(client, fake, monkeypatch):
    import api.bump as bump_mod

    def broken(*a, **k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(bump_mod, "_upsert", broken)
    pid = _pid(client, "acme/api")
    r = client.post(f"/api/projects/{pid}/releases", json={"bump": "patch", "target": "main"})
    assert r.status_code == 201
    assert r.json()["recorded"] is False

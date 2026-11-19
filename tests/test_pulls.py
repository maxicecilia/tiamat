import pytest

from api import pulls
from services import github_api as gh
from services.slack import SlackService


@pytest.fixture
def fake(client, monkeypatch):
    """Fake GitHub compare/PR calls and Slack (never post for real)."""
    state = {"ahead": {}, "open": {}, "created": [], "slack": [], "fail": {}}
    monkeypatch.setattr(gh, "is_configured", lambda: True)

    def compare(repo, base, head, max_commits=50):
        if repo in state["fail"]:
            raise gh.GitHubError(state["fail"][repo], 404)
        n = state["ahead"].get(repo, 0)
        commits = [
            {"sha": f"c{i}", "message": f"commit {i}", "author": "dev", "date": None, "url": None}
            for i in range(n)
        ][:max_commits]
        return {"ahead_by": n, "behind_by": 0, "compare_url": f"cmp/{repo}", "commits": commits}

    def create(repo, base, head):
        if repo in state["open"]:
            return state["open"][repo], False
        url = f"https://github.com/{repo}/pull/1"
        state["created"].append((repo, base, head))
        return url, True

    def send(message, **kw):
        state["slack"].append((message, kw))
        return True

    monkeypatch.setattr(gh, "compare_branches", compare)
    monkeypatch.setattr(gh, "find_open_pull_request", lambda repo, b, h: state["open"].get(repo))
    monkeypatch.setattr(gh, "create_pull_request", create)
    monkeypatch.setattr(SlackService, "send_message", staticmethod(send))
    monkeypatch.setattr(SlackService, "is_configured", staticmethod(lambda: True))
    return state


def _t(ids, base="main", head="release"):
    return [{"project_id": i, "base": base, "head": head} for i in ids]


def _ids(client, *repos):
    by_repo = {p["repo"]: p for p in client.get("/api/projects").json()}
    return [by_repo[r]["id"] for r in repos]


def test_check_reports_pending_commits_and_open_prs(client, fake):
    fake["ahead"] = {"acme/api": 3}
    fake["open"] = {"acme/api": "https://github.com/acme/api/pull/9"}
    fake["fail"] = {"acme/worker": "Not Found"}
    rows = {r["repo"]: r for r in client.post("/api/pending", json={}).json()}
    assert rows["acme/api"]["ahead_by"] == 3
    assert len(rows["acme/api"]["commits"]) == 3
    assert rows["acme/api"]["open_pr_url"].endswith("/pull/9")
    assert rows["acme/api"]["base"] == "main" and rows["acme/api"]["head"] == "release"
    assert rows["acme/web"]["ahead_by"] == 0
    assert rows["acme/web"]["open_pr_url"] is None
    assert rows["acme/worker"]["error"].startswith("Branch 'release' or 'main' not found")


def test_check_with_branch_override(client, fake):
    [pid] = _ids(client, "acme/api")
    [row] = client.post(
        "/api/pending", json={"project_ids": [pid], "base": "release", "head": "develop"}
    ).json()
    assert (row["base"], row["head"]) == ("release", "develop")


def test_create_prs_groups_slack_by_audience(client, fake):
    # acme/web carries the "frontend" tag from FE_REPOSITORIES.
    fake["ahead"] = {"acme/api": 2, "acme/web": 1, "acme/worker": 4}
    fake["open"] = {"acme/worker": "https://github.com/acme/worker/pull/5"}
    ids = _ids(client, "acme/api", "acme/web", "acme/worker")
    out = client.post("/api/pull-requests", json={"targets": _t(ids), "notify_slack": True}).json()
    status = {r["repo"]: r["status"] for r in out["results"]}
    assert status == {"acme/api": "created", "acme/web": "created", "acme/worker": "exists"}
    assert sorted(c[0] for c in fake["created"]) == ["acme/api", "acme/web"]

    messages = {("fe" if kw["tag_fe_developers"] else "be"): m for m, kw in fake["slack"]}
    assert messages == {
        "fe": "A new PR has been created for acme/web:\nhttps://github.com/acme/web/pull/1",
        "be": "A new PR has been created for acme/api:\nhttps://github.com/acme/api/pull/1",
    }
    assert out["slack"]["sent"] == [
        {"audience": "frontend", "ok": True},
        {"audience": "backend", "ok": True},
    ]


def test_create_prs_skips_repos_without_changes_and_can_skip_slack(client, fake):
    fake["ahead"] = {"acme/api": 1}
    ids = _ids(client, "acme/api", "acme/web")
    out = client.post("/api/pull-requests", json={"targets": _t(ids)}).json()
    assert {r["repo"]: r["status"] for r in out["results"]} == {
        "acme/api": "created",
        "acme/web": "no_changes",
    }
    assert fake["slack"] == []


def test_create_prs_reports_errors(client, fake):
    fake["fail"] = {"acme/api": "Not Found"}
    [pid] = _ids(client, "acme/api")
    [result] = client.post(
        "/api/pull-requests", json={"targets": _t([pid]), "notify_slack": True}
    ).json()["results"]
    assert result["status"] == "error"
    assert "not found" in result["error"]
    assert fake["slack"] == []


def test_validation(client, fake):
    assert client.post("/api/pull-requests", json={"targets": []}).status_code == 422
    assert client.post("/api/pull-requests", json={"targets": _t([99999])}).status_code == 404
    bad = [{"project_id": 1, "base": "", "head": "release"}]
    assert client.post("/api/pull-requests", json={"targets": bad}).status_code == 422


def test_multiple_new_prs_share_one_message():
    results = [
        {"status": "created", "frontend": False, "repo": "a/1", "url": "u1"},
        {"status": "created", "frontend": False, "repo": "a/2", "url": "u2"},
        {"status": "exists", "frontend": False, "repo": "a/3", "url": "u3"},
    ]
    assert pulls.slack_messages(results) == {"be": "New PRs have been created:\nu1\nu2"}


def test_create_prs_with_branch_override(client, fake):
    fake["ahead"] = {"acme/api": 1}
    [pid] = _ids(client, "acme/api")
    client.post(
        "/api/pull-requests",
        json={"targets": [{"project_id": pid, "base": "release", "head": "develop"}]},
    )
    assert fake["created"] == [("acme/api", "release", "develop")]


def test_slack_is_opt_in(client, fake):
    fake["ahead"] = {"acme/api": 1}
    [pid] = _ids(client, "acme/api")
    out = client.post("/api/pull-requests", json={"targets": _t([pid])}).json()
    assert out["results"][0]["status"] == "created"
    assert fake["slack"] == []


def test_uncertain_create_says_pr_may_exist(client, fake, monkeypatch):
    fake["ahead"] = {"acme/api": 1}

    def timeout(repo, base, head):
        raise gh.GitHubUncertain("No response from GitHub: read timed out")

    monkeypatch.setattr(gh, "create_pull_request", timeout)
    [pid] = _ids(client, "acme/api")
    [r] = client.post("/api/pull-requests", json={"targets": _t([pid])}).json()["results"]
    assert r["status"] == "error"
    assert "may have been created" in r["error"]

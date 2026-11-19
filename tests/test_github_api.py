import pytest
import requests

from services import github_api as gh


class Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body
        self.text = str(body)

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


@pytest.fixture
def calls(monkeypatch):
    log, queue = [], []
    monkeypatch.setattr(gh, "is_configured", lambda: True)

    def fake_request(method, url, **kwargs):
        log.append((method, url, kwargs.get("json"), kwargs.get("params")))
        return queue.pop(0)

    monkeypatch.setattr(requests, "request", fake_request)
    return log, queue


def test_dispatch_returns_run_id(calls):
    log, queue = calls
    queue.append(Resp(200, {"workflow_run_id": 77}))
    assert gh.dispatch_workflow("acme/api", 5, "main", {"a": "b"}) == 77
    assert log[0][2] == {"ref": "main", "inputs": {"a": "b"}, "return_run_details": True}


def test_dispatch_retries_without_run_details_flag(calls):
    log, queue = calls
    queue += [Resp(422, {"message": "'return_run_details' is not a permitted key"}), Resp(204)]
    assert gh.dispatch_workflow("acme/api", 5, "main", {}) is None
    assert "return_run_details" not in log[1][2]


def test_dispatch_error_raises(calls):
    _, queue = calls
    queue.append(Resp(404, {"message": "Not Found"}))
    with pytest.raises(gh.GitHubError, match="Not Found"):
        gh.dispatch_workflow("acme/api", 5, "main", {})


def test_resolve_workflow_id_by_file_name(calls):
    _, queue = calls
    queue.append(
        Resp(
            200,
            {
                "workflows": [
                    {
                        "id": 1,
                        "name": "Release staging",
                        "path": ".github/workflows/release-staging.yml",
                    },
                    {"id": 2, "name": "Release prod", "path": ".github/workflows/release-prod.yml"},
                ]
            },
        )
    )
    assert gh.resolve_workflow_id("acme/api", "release-prod.yml") == 2


def test_resolve_workflow_id_does_not_substring_match(calls):
    _, queue = calls
    queue.append(
        Resp(
            200,
            {
                "workflows": [
                    {"id": 1, "name": "x", "path": ".github/workflows/pre-release-prod.yml"}
                ]
            },
        )
    )
    with pytest.raises(gh.GitHubError):
        gh.resolve_workflow_id("acme/api", "release-prod.yml")


def test_list_releases_skips_drafts(calls):
    _, queue = calls
    queue.append(Resp(200, [{"tag_name": "1", "draft": True}, {"tag_name": "2", "draft": False}]))
    assert [r["tag_name"] for r in gh.list_releases("acme/api")] == ["2"]


def test_read_timeout_is_uncertain(monkeypatch):
    monkeypatch.setattr(gh, "is_configured", lambda: True)

    def timeout(*a, **k):
        raise requests.ReadTimeout("read timed out")

    monkeypatch.setattr(requests, "request", timeout)
    with pytest.raises(gh.GitHubUncertain):
        gh.dispatch_workflow("acme/api", 5, "main", {})


def test_connect_timeout_is_certain_failure(monkeypatch):
    monkeypatch.setattr(gh, "is_configured", lambda: True)

    def no_connect(*a, **k):
        raise requests.ConnectTimeout("connect timed out")

    monkeypatch.setattr(requests, "request", no_connect)
    with pytest.raises(gh.GitHubError) as exc:
        gh.dispatch_workflow("acme/api", 5, "main", {})
    assert not isinstance(exc.value, gh.GitHubUncertain)


def test_bad_json_raises_github_error(calls):
    _, queue = calls
    queue.append(Resp(200, None))
    with pytest.raises(gh.GitHubError, match="Unexpected response"):
        gh.list_releases("acme/api")


def test_list_releases_since_stops_at_cutoff(calls):
    from datetime import UTC, datetime

    log, queue = calls
    page = [
        {"tag_name": "3", "created_at": "2026-11-10T00:00:00Z"},
        {"tag_name": "2", "created_at": "2026-10-10T00:00:00Z", "draft": True},
        {"tag_name": "1", "created_at": "2026-01-10T00:00:00Z"},
    ]
    queue.append(Resp(200, page))
    got = gh.list_releases_since("acme/api", datetime(2026, 6, 1, tzinfo=UTC))
    assert [r["tag_name"] for r in got] == ["3"]
    assert len(log) == 1


def test_oldest_commit_date(calls):
    _, queue = calls
    queue.append(Resp(200, {"commits": [{"commit": {"author": {"date": "2026-11-01T09:00:00Z"}}}]}))
    assert gh.oldest_commit_date("acme/api", "1.0", "1.1").day == 1
    queue.append(Resp(404, {"message": "Not Found"}))
    assert gh.oldest_commit_date("acme/api", "gone", "1.1") is None


def test_create_pull_request_falls_back_to_existing(calls):
    log, queue = calls
    queue += [
        Resp(422, {"message": "A pull request already exists"}),
        Resp(200, [{"html_url": "https://github.com/acme/api/pull/3"}]),
    ]
    assert gh.create_pull_request("acme/api", "main", "release") == (
        "https://github.com/acme/api/pull/3",
        False,
    )
    assert log[0][2]["head"] == "release" and log[0][2]["base"] == "main"
    assert log[1][3] == {"head": "acme:release", "base": "main", "state": "open"}


def test_create_pull_request_error(calls):
    _, queue = calls
    queue += [
        Resp(
            422,
            {
                "message": "Validation Failed",
                "errors": [{"message": "No commits between main and release"}],
            },
        ),
        Resp(200, []),
    ]
    with pytest.raises(gh.GitHubError, match="Validation Failed: No commits"):
        gh.create_pull_request("acme/api", "main", "release")


def test_compare_branches_newest_first(calls):
    _, queue = calls
    queue.append(
        Resp(
            200,
            {
                "ahead_by": 2,
                "behind_by": 0,
                "html_url": "cmp",
                "commits": [
                    {
                        "sha": "aaaaaaa1",
                        "commit": {"message": "old\nbody", "author": {"name": "A", "date": "d1"}},
                    },
                    {
                        "sha": "bbbbbbb2",
                        "commit": {"message": "new", "author": {"name": "B", "date": "d2"}},
                    },
                ],
            },
        )
    )
    out = gh.compare_branches("acme/api", "main", "release")
    assert [c["message"] for c in out["commits"]] == ["new", "old"]
    assert out["ahead_by"] == 2


def test_compare_quotes_branch_names(calls):
    log, queue = calls
    queue.append(Resp(200, {"ahead_by": 0, "commits": []}))
    gh.compare_branches("acme/api", "main", "feat/a#1")
    assert log[0][1].endswith("/compare/main...feat/a%231")


def test_create_release_payload(calls):
    log, queue = calls
    queue.append(Resp(201, {"tag_name": "v1.4.0", "html_url": "u"}))
    assert gh.create_release("acme/api", "v1.4.0", "main")["tag_name"] == "v1.4.0"
    assert log[0][2] == {
        "tag_name": "v1.4.0",
        "target_commitish": "main",
        "name": "v1.4.0",
        "body": "",
        "draft": False,
        "prerelease": False,
        "generate_release_notes": True,
    }


def test_tag_exists(calls):
    log, queue = calls
    queue += [Resp(200, {"ref": "refs/tags/v1.0.0"}), Resp(404, {"message": "Not Found"})]
    assert gh.tag_exists("acme/api", "v1.0.0") is True
    assert gh.tag_exists("acme/api", "v9.9.9") is False
    assert log[0][1].endswith("/git/ref/tags/v1.0.0")


def test_org_specific_token(monkeypatch):
    from services import github

    assert github.org_token_var("my-org/app") == "GITHUB_TOKEN_MY_ORG"
    assert github.org_token_var(None) is None
    monkeypatch.setattr(github, "GITHUB_TOKEN", "default-token")
    monkeypatch.setenv("GITHUB_TOKEN_MY_ORG", "org-token")
    assert github._get_headers("my-org/app")["Authorization"] == "token org-token"
    assert github._get_headers("other/app")["Authorization"] == "token default-token"

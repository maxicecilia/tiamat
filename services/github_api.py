"""Data-returning GitHub helpers for the dashboard API.

`services/github.py` is built for the CLI (it prints with rich and returns
booleans). These helpers share its auth and URL logic but return data and
raise `GitHubError`, so the API can turn failures into HTTP responses.
"""

import os
from datetime import datetime
from urllib.parse import quote

import requests

from services.github import GITHUB_TOKEN, _get_headers, _get_url, org_token_var

TIMEOUT = 15


class GitHubError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class GitHubUncertain(GitHubError):
    """The request may have reached GitHub but we got no answer (timeout, dropped connection).

    For a dispatch this means the workflow might be running, so it must not be retried blindly.
    """


def is_configured() -> bool:
    return bool(GITHUB_TOKEN)


def _error_message(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text
    message = data.get("message") or response.text
    details = [e.get("message") for e in data.get("errors") or [] if isinstance(e, dict)]
    details = [d for d in details if d]
    return f"{message}: {'; '.join(details)}" if details else message


def _ref(branch: str) -> str:
    return quote(branch, safe="/")


def _request(method: str, repo: str | None, path: str, **kwargs) -> requests.Response:
    if not is_configured():
        raise GitHubError("GITHUB_TOKEN is not set")
    try:
        return requests.request(
            method, _get_url(path), headers=_get_headers(repo), timeout=TIMEOUT, **kwargs
        )
    except requests.ConnectTimeout as exc:
        # Never connected, so the request certainly did not reach GitHub.
        raise GitHubError(f"Could not reach GitHub: {exc}") from exc
    except requests.RequestException as exc:
        raise GitHubUncertain(f"No response from GitHub: {exc}") from exc


def _json(response: requests.Response):
    try:
        return response.json()
    except ValueError as exc:
        raise GitHubError(f"Unexpected response from GitHub: {response.text[:200]}") from exc


def _get_json(repo: str | None, path: str, **params):
    response = _request("GET", repo, path, params=params or None)
    if response.status_code != 200:
        raise GitHubError(_error_message(response), response.status_code)
    return _json(response)


_login_cache: dict[str, str | None] = {}


def token_login(repo: str) -> str | None:
    """GitHub login of the token used for `repo` (cached), or None if unavailable."""
    var = org_token_var(repo)
    key = var if var and os.getenv(var) else "default"
    if key not in _login_cache:
        try:
            _login_cache[key] = _get_json(repo, "user").get("login")
        except GitHubError:
            return None
    return _login_cache[key]


def parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def resolve_workflow_id(repo: str, workflow: str) -> int:
    """Find a workflow's numeric id from its file name (e.g. `deploy-prod.yml`) or name."""
    if workflow.isdigit():
        return int(workflow)
    workflows = _get_json(repo, f"repos/{repo}/actions/workflows", per_page=100).get(
        "workflows", []
    )
    for wf in workflows:
        if wf.get("path", "").endswith(f"/{workflow}") or wf.get("name") == workflow:
            return wf["id"]
    raise GitHubError(f"No workflow named '{workflow}' in {repo}", 404)


def dispatch_workflow(repo: str, workflow_id: int, ref: str, inputs: dict) -> int | None:
    """Trigger a workflow_dispatch run. Returns the run id when GitHub reports it."""
    payload = {"ref": ref, "inputs": inputs or {}, "return_run_details": True}
    path = f"repos/{repo}/actions/workflows/{workflow_id}/dispatches"
    response = _request("POST", repo, path, json=payload)
    if response.status_code == 422 and "return_run_details" in _error_message(response):
        # Older API versions reject this flag; retry without it and find the run later.
        payload.pop("return_run_details")
        response = _request("POST", repo, path, json=payload)
    if response.status_code == 204:
        return None
    if response.status_code == 200:
        try:
            return response.json().get("workflow_run_id")
        except ValueError:
            return None  # Accepted, but no run id; the run is matched later.
    raise GitHubError(_error_message(response), response.status_code)


def list_dispatch_runs(repo: str, workflow_id: int, branch: str, created_after: datetime) -> list:
    created = created_after.strftime("%Y-%m-%dT%H:%M:%SZ")
    data = _get_json(
        repo,
        f"repos/{repo}/actions/workflows/{workflow_id}/runs",
        event="workflow_dispatch",
        branch=branch,
        created=f">={created}",
        per_page=50,
    )
    return data.get("workflow_runs", [])


def get_run(repo: str, run_id: int) -> dict:
    return _get_json(repo, f"repos/{repo}/actions/runs/{run_id}")


def list_releases(repo: str, limit: int = 20, include_drafts: bool = False) -> list:
    """Releases, newest first; drafts only when asked for."""
    releases = _get_json(repo, f"repos/{repo}/releases", per_page=limit)
    return releases if include_drafts else [r for r in releases if not r.get("draft")]


def tag_exists(repo: str, tag: str) -> bool:
    try:
        _get_json(repo, f"repos/{repo}/git/ref/tags/{_ref(tag)}")
    except GitHubError as exc:
        if exc.status == 404:
            return False
        raise
    return True


def list_releases_since(repo: str, since: datetime, max_pages: int = 10) -> list:
    """Non-draft releases created at or after `since`, newest first (paginates)."""
    found = []
    for page in range(1, max_pages + 1):
        batch = _get_json(repo, f"repos/{repo}/releases", per_page=100, page=page)
        if not batch:
            break
        for release in batch:
            created = parse_time(release.get("created_at"))
            if created and created < since:
                return found  # GitHub lists newest first, so the rest are older
            if not release.get("draft"):
                found.append(release)
        if len(batch) < 100:
            break
    return found


def oldest_commit_date(repo: str, base: str, head: str) -> datetime | None:
    """Author date of the oldest commit in base...head (lead time for changes)."""
    try:
        data = _get_json(repo, f"repos/{repo}/compare/{base}...{head}")
    except GitHubError as exc:
        if exc.status == 404:
            return None  # tag deleted or unrelated histories
        raise
    commits = data.get("commits") or []
    if not commits:
        return None
    return parse_time(commits[0].get("commit", {}).get("author", {}).get("date"))


def compare_branches(repo: str, base: str, head: str, max_commits: int = 50) -> dict:
    """Commits on `head` that are not on `base` (what a base<-head PR would merge)."""
    data = _get_json(repo, f"repos/{repo}/compare/{_ref(base)}...{_ref(head)}")
    commits = data.get("commits") or []
    return {
        "ahead_by": data.get("ahead_by", len(commits)),
        "behind_by": data.get("behind_by", 0),
        "compare_url": data.get("html_url"),
        # GitHub lists oldest first; show newest first.
        "commits": [
            {
                "sha": c.get("sha", "")[:7],
                "message": (c.get("commit", {}).get("message") or "").split("\n")[0],
                "author": (c.get("commit", {}).get("author") or {}).get("name")
                or (c.get("author") or {}).get("login"),
                "date": (c.get("commit", {}).get("author") or {}).get("date"),
                "url": c.get("html_url"),
            }
            for c in reversed(commits[-max_commits:] if max_commits else [])
        ],
    }


def find_open_pull_request(repo: str, base: str, head: str) -> str | None:
    owner = repo.split("/")[0]
    prs = _get_json(repo, f"repos/{repo}/pulls", head=f"{owner}:{head}", base=base, state="open")
    return prs[0]["html_url"] if prs else None


def create_pull_request(repo: str, base: str, head: str) -> tuple[str, bool]:
    """Open a head->base PR (same title/body as the CLI). Returns (url, created);
    `created` is False when an open PR between the branches already existed."""
    payload = {
        "title": f"Merge {head} into {base} - {datetime.now().strftime('%B %Y')}",
        "head": head,
        "base": base,
        "body": "Auto-generated by Tiamat",
    }
    response = _request("POST", repo, f"repos/{repo}/pulls", json=payload)
    if response.status_code == 201:
        return _json(response)["html_url"], True
    if response.status_code == 422:
        existing = find_open_pull_request(repo, base, head)
        if existing:
            return existing, False
    raise GitHubError(_error_message(response), response.status_code)


def create_release(
    repo: str,
    tag: str,
    target: str,
    name: str | None = None,
    draft: bool = False,
    prerelease: bool = False,
) -> dict:
    """Create a release and its tag, with GitHub-generated notes (same as the CLI's `bump`)."""
    payload = {
        "tag_name": tag,
        "target_commitish": target,
        "name": name or tag,
        "body": "",
        "draft": draft,
        "prerelease": prerelease,
        "generate_release_notes": True,
    }
    response = _request("POST", repo, f"repos/{repo}/releases", json=payload)
    if response.status_code == 201:
        return _json(response)
    raise GitHubError(_error_message(response), response.status_code)

"""Pending-changes checks and release PRs (the dashboard's `check` and `createpr`)."""

import logging
from concurrent.futures import ThreadPoolExecutor

from api.models import Project
from services import github_api as gh
from services.slack import SlackService

log = logging.getLogger("tiamat.pulls")

FRONTEND_TAG = "frontend"


def _target(project: Project, base: str | None = None, head: str | None = None) -> dict:
    # Plain values only: these go to worker threads.
    return {
        "project_id": project.id,
        "name": project.name,
        "repo": project.repo,
        "base": base or project.base_branch,
        "head": head or project.head_branch,
        "frontend": any(t.name == FRONTEND_TAG for t in project.tags),
        "starred": project.starred,
    }


def _describe(exc: Exception, t: dict) -> str:
    if isinstance(exc, gh.GitHubUncertain):
        return f"{exc}. The PR may have been created; check again before retrying."
    if isinstance(exc, gh.GitHubError) and exc.status == 404:
        return f"Branch '{t['head']}' or '{t['base']}' not found (or no access to the repo)"
    return str(exc)


def _check_one(t: dict) -> dict:
    result = t | {"ahead_by": None, "commits": [], "open_pr_url": None, "error": None}
    try:
        result |= gh.compare_branches(t["repo"], t["base"], t["head"])
        if result["ahead_by"]:
            result["open_pr_url"] = gh.find_open_pull_request(t["repo"], t["base"], t["head"])
    except Exception as exc:  # noqa: BLE001 - report per project
        result["error"] = _describe(exc, t)
    return result


def check(projects: list[Project], base: str | None = None, head: str | None = None) -> list[dict]:
    targets = [_target(p, base, head) for p in projects]
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(_check_one, targets))


def _create_one(t: dict) -> dict:
    result = t | {"status": None, "url": None, "error": None, "ahead_by": None}
    try:
        compare = gh.compare_branches(t["repo"], t["base"], t["head"], max_commits=0)
        result["ahead_by"] = compare["ahead_by"]
        if not compare["ahead_by"]:
            result["status"] = "no_changes"
            return result
        url, created = gh.create_pull_request(t["repo"], t["base"], t["head"])
        result["url"] = url
        result["status"] = "created" if created else "exists"
    except Exception as exc:  # noqa: BLE001
        result["status"] = "error"
        result["error"] = _describe(exc, t)
    return result


def slack_messages(results: list[dict]) -> dict[str, str]:
    """Group new PRs into one message for frontend and one for backend devs (like the CLI).
    PRs that already existed are not announced again."""
    groups: dict[str, list[dict]] = {"fe": [], "be": []}
    for r in results:
        if r["status"] == "created":
            groups["fe" if r["frontend"] else "be"].append(r)
    messages = {}
    for key, prs in groups.items():
        if len(prs) == 1:
            messages[key] = f"A new PR has been created for {prs[0]['repo']}:\n{prs[0]['url']}"
        elif prs:
            messages[key] = "New PRs have been created:\n" + "\n".join(p["url"] for p in prs)
    return messages


def create_pull_requests(
    projects: list[Project], notify_slack: bool, branches: dict[int, tuple[str, str]] | None = None
) -> dict:
    """`branches` maps project id -> (base, head) as shown to the user; defaults to the
    project's configured branches."""
    branches = branches or {}
    targets = [_target(p, *branches.get(p.id, (None, None))) for p in projects]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_create_one, targets))

    slack = {"requested": notify_slack, "configured": SlackService.is_configured(), "sent": []}
    if notify_slack:
        for key, message in slack_messages(results).items():
            ok = SlackService.send_message(
                message, tag_fe_developers=key == "fe", tag_be_developers=key == "be"
            )
            slack["sent"].append({"audience": "frontend" if key == "fe" else "backend", "ok": ok})
    return {"results": results, "slack": slack}

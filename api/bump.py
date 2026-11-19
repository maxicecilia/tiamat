"""Version bump + release creation (the dashboard's `bump`)."""

import logging
import re

from sqlmodel import Session

from api.models import Project, WorkflowVersion
from api.releases import _aware, _upsert
from services import github_api as gh
from services.github import DEFAULT_VERSION, GitHubService

log = logging.getLogger("tiamat.bump")

# Tags `bump` can safely increment: 1.2.3 or v1.2.3. Anything else (e.g. "3.4.0.web")
# would make GitHubService.bump_version restart at 0.x, so a version must be typed.
SEMVER = re.compile(r"^v?\d+\.\d+\.\d+$")
BUMPS = ("major", "minor", "patch")
# Conservative tag names: letters, digits, dots, dashes, underscores; no "..", no leading "-".
TAG = re.compile(r"^(?!-)(?!.*\.\.)[A-Za-z0-9._-]+$")


class BumpError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def latest_release(repo: str) -> dict | None:
    """Newest published, non-prerelease release (what `get_latest_version` uses)."""
    releases = [r for r in gh.list_releases(repo, 100) if not r.get("prerelease")]
    return max(releases, key=lambda r: r.get("created_at") or "", default=None)


def tag_taken(repo: str, tag: str) -> str | None:
    """Why `tag` can't be used, or None. Checks existing tags (a release on an existing
    tag would ignore the chosen target) and releases, including drafts and pre-releases."""
    if gh.tag_exists(repo, tag):
        return f"Tag {tag} already exists in {repo}"
    if any(r.get("tag_name") == tag for r in gh.list_releases(repo, 100, include_drafts=True)):
        return f"A release (or draft) for {tag} already exists in {repo}"
    return None


def plan(project: Project, target: str | None = None) -> dict:
    """What a bump would do now: current version, candidate versions, unreleased commits."""
    target = target or project.base_branch
    latest = latest_release(project.repo)
    current = latest["tag_name"] if latest else None
    parseable = current is None or bool(SEMVER.match(current))
    base_version = current or DEFAULT_VERSION  # same starting point as the CLI
    candidates = (
        {b: GitHubService.bump_version(base_version, b) for b in BUMPS} if parseable else {}
    )
    unreleased = None
    if current:
        try:
            unreleased = gh.compare_branches(project.repo, current, target, max_commits=0)[
                "ahead_by"
            ]
        except gh.GitHubError:
            unreleased = None
    return {
        "project_id": project.id,
        "repo": project.repo,
        "workflow_version": project.workflow_version,
        "managed_by_workflow": project.workflow_version == WorkflowVersion.v2,
        "current": current,
        "current_url": latest.get("html_url") if latest else None,
        "current_date": latest.get("created_at") if latest else None,
        "parseable": parseable,
        "candidates": candidates,
        "target": target,
        "unreleased_commits": unreleased,
    }


def create(
    session: Session,
    project: Project,
    *,
    bump: str | None,
    version: str | None,
    expected_current: str | None,
    target: str,
    name: str | None,
    draft: bool,
    prerelease: bool,
) -> dict:
    if project.workflow_version == WorkflowVersion.v2:
        raise BumpError(
            f"{project.name} uses the v2 release workflows, which create the release "
            "automatically. Deploy it instead.",
            409,
        )
    latest = latest_release(project.repo)
    current = latest["tag_name"] if latest else None
    if current != expected_current:
        raise BumpError(
            f"The latest release is now {current or 'none'} (you saw "
            f"{expected_current or 'none'}). Review the new version and try again.",
            409,
        )
    if version:
        tag = version.strip()
    elif bump in BUMPS:
        if current and not SEMVER.match(current):
            raise BumpError(
                f"The latest tag '{current}' isn't a plain x.y.z version, so it can't be "
                "bumped automatically. Enter the version to create.",
                422,
            )
        tag = GitHubService.bump_version(current or DEFAULT_VERSION, bump)
    else:
        raise BumpError("Choose major, minor or patch, or enter a version", 422)
    if not TAG.match(tag) or tag.lower() in {"main", "master", "release", "develop", "head"}:
        raise BumpError(f"'{tag}' isn't a valid release tag", 422)
    if reason := tag_taken(project.repo, tag):
        raise BumpError(reason, 409)

    data = gh.create_release(project.repo, tag, target, name or tag, draft, prerelease)

    # Show it on the dashboard right away (drafts aren't counted as releases). The release
    # exists on GitHub either way, so a local failure must not turn this into an error.
    recorded = False
    if not data.get("draft"):
        try:
            _upsert(session, project.id, [data])
            session.commit()
            recorded = True
        except Exception:
            session.rollback()
            log.exception("Release %s created but not recorded locally", tag)
    return {
        "recorded": recorded,
        "tag": tag,
        "previous": current,
        "url": data.get("html_url"),
        "draft": bool(data.get("draft")),
        "prerelease": bool(data.get("prerelease")),
        "target": target,
        "created_at": _aware(gh.parse_time(data.get("created_at")))
        if data.get("created_at")
        else None,
    }

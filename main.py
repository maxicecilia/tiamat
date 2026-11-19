import os
import sys

import click
from dotenv import load_dotenv
from rich import print as rprint
from rich.console import Console
from rich.table import Table

load_dotenv()

from commands.actions import register_actions_commands
from commands.help import register_help_command
from commands.merge import register_merge_commands
from commands.release import register_release_commands
from commands.shell import register_shell_command
from commands.slack import register_slack_commands
from commands.stats import register_stats_command
from services.github import GITHUB_TOKEN, GitHubService
from services.slack import SlackService

# Default branches
DEFAULT_BASE_BRANCH = "main"
DEFAULT_HEAD_BRANCH = "release"

REPOSITORIES = os.getenv("REPOSITORIES", "").split(",")
# Repositories using the v2 release workflows (release.<env>.yml).
# These create releases automatically, so `bump` is not needed for them.
REPOSITORIES_V2 = [r for r in os.getenv("REPOSITORIES_v2", "").split(",") if r]
# Every repository Tiamat manages (v1 + v2), used by repo-wide commands.
ALL_REPOSITORIES = REPOSITORIES + [r for r in REPOSITORIES_V2 if r not in REPOSITORIES]
FE_REPOSITORIES = os.getenv("FE_REPOSITORIES", "").split(",")
BETA_REPOSITORIES = os.getenv("BETA_REPOSITORIES", "").split(",")
ML_REPOSITORIES = os.getenv("ML_REPOSITORIES", "").split(",")
DATAOPS_REPOSITORIES = os.getenv("DATAOPS_REPOSITORIES", "").split(",")

console = Console()


def is_fe_repo(repo):
    return repo in FE_REPOSITORIES


class TiamatContext:
    def __init__(self):
        self.base_branch = DEFAULT_BASE_BRANCH
        self.head_branch = DEFAULT_HEAD_BRANCH


pass_tiamat_context = click.make_pass_decorator(TiamatContext, ensure=True)


def parse_compare_args(compare_spec, repo, base_branch, head_branch):
    """Parse optional COMPARE_SPEC and REPO arguments.

    A single argument without '..' is treated as the repository, so
    `check my-service` targets one repo instead of silently running on all.
    """
    if compare_spec and ".." not in compare_spec and not repo:
        return base_branch, head_branch, compare_spec
    if compare_spec:
        if "..." in compare_spec:
            base_branch, head_branch = compare_spec.split("...", 1)
        elif ".." in compare_spec:
            base_branch, head_branch = compare_spec.split("..", 1)
    return base_branch, head_branch, repo


def resolve_repo(repo_input):
    """Convert short repo name to full name if needed"""
    if "/" not in repo_input:
        matching_repos = [
            r for r in ALL_REPOSITORIES if r.split("/")[1] == repo_input
        ]
        if matching_repos:
            return matching_repos[0]
    return repo_input


@click.group()
@click.version_option(version="0.1.0")
@click.option(
    "--base",
    default=DEFAULT_BASE_BRANCH,
    help=f"Base branch (default: {DEFAULT_BASE_BRANCH})",
)
@click.option(
    "--head",
    default=DEFAULT_HEAD_BRANCH,
    help=f"Head branch (default: {DEFAULT_HEAD_BRANCH})",
)
@click.pass_context
def cli(ctx, base, head):
    """🐉 Tiamat - Repository Management Tool"""
    ctx.ensure_object(TiamatContext)
    ctx.obj.base_branch = base
    ctx.obj.head_branch = head


# Register the help command and get a reference to it
help_command = register_help_command(cli)

# Register the shell command
shell_command = register_shell_command(cli, ALL_REPOSITORIES, GITHUB_TOKEN, TiamatContext)

# Register release commands
bump_command, releases_command = register_release_commands(
    cli, REPOSITORIES, REPOSITORIES_V2
)

# Register GitHub Actions commands
run_command = register_actions_commands(cli, REPOSITORIES, REPOSITORIES_V2)

# Register merge commands
merge_command = register_merge_commands(cli, ALL_REPOSITORIES)

# Register Slack commands
send_command = register_slack_commands(cli)

# Register stats command
stats_command = register_stats_command(
    cli,
    ALL_REPOSITORIES,
    FE_REPOSITORIES,
    BETA_REPOSITORIES,
    ML_REPOSITORIES,
    DATAOPS_REPOSITORIES,
)


@cli.command()
@click.argument("compare_spec", required=False)
@click.argument("repo", required=False)
@pass_tiamat_context
def check(ctx, compare_spec, repo):
    """Check for pending commits between branches.

    COMPARE_SPEC can be in format 'base...head' or 'base..head'
    Examples:
      - check main...release
      - check main...release my-service
      - check my-service (default branches, single repo)
      - check (uses default branches from context)
    """
    if not GITHUB_TOKEN:
        rprint(
            "[bold red]❌ GITHUB_TOKEN is not set. Please set it in your environment.[/bold red]"
        )
        return

    base_branch = ctx.base_branch
    head_branch = ctx.head_branch

    base_branch, head_branch, repo = parse_compare_args(
        compare_spec, repo, base_branch, head_branch
    )

    if repo:
        repo_full = resolve_repo(repo)
        GitHubService.get_pending_commits(repo_full, base_branch, head_branch)
    else:
        for repo in ALL_REPOSITORIES:
            GitHubService.get_pending_commits(repo, base_branch, head_branch)


@cli.command()
@click.argument("compare_spec", required=False)
@click.argument("repo", required=False)
@pass_tiamat_context
def createpr(ctx, compare_spec, repo):
    """Create pull requests between branches.

    COMPARE_SPEC can be in format 'base...head' or 'base..head'
    Examples:
      - createpr main...release
      - createpr main...release my-service
      - createpr my-service (default branches, single repo)
      - createpr (uses default branches from context)
    """
    if not GITHUB_TOKEN:
        rprint(
            "[bold red]❌ GITHUB_TOKEN is not set. Please set it in your environment.[/bold red]"
        )
        return

    base_branch = ctx.base_branch
    head_branch = ctx.head_branch

    base_branch, head_branch, repo = parse_compare_args(
        compare_spec, repo, base_branch, head_branch
    )

    notifications = {"fe": None, "be": None}

    if repo:
        repo_full = resolve_repo(repo)
        has_commits = GitHubService.get_pending_commits(
            repo_full, base_branch, head_branch, display_table=False
        )
        if has_commits:
            pr_url, created = GitHubService.create_pull_request(
                repo_full, base_branch, head_branch
            )
            if pr_url and not created:
                rprint(f"🔗 Already open (no Slack message sent): {pr_url}")
            elif pr_url:
                rprint(f"🔗 {pr_url}")
                key = "fe" if is_fe_repo(repo_full) else "be"
                notifications[key] = (
                    f"A new PR has been created for {repo_full}:\n{pr_url}"
                )
            else:
                rprint(f"❌ Failed to create PR for {repo_full}")
    else:
        for repo in ALL_REPOSITORIES:
            has_commits = GitHubService.get_pending_commits(
                repo, base_branch, head_branch, display_table=False
            )
            if has_commits:
                pr_url, created = GitHubService.create_pull_request(
                    repo, base_branch, head_branch
                )
                if pr_url and not created:
                    rprint(f"🔗 Already open (no Slack message sent): {pr_url}")
                elif pr_url:
                    rprint(f"🔗 {pr_url}")
                    key = "fe" if is_fe_repo(repo) else "be"
                    if notifications[key]:
                        notifications[key] += f"\n{pr_url}"
                    else:
                        notifications[key] = f"New PRs have been created:\n{pr_url}"
                else:
                    rprint(f"❌ Failed to create PR for {repo}")

    for key, message in notifications.items():
        if message:
            SlackService.send_message(
                message,
                tag_fe_developers=key == "fe",
                tag_be_developers=key == "be",
            )


@cli.command()
def list():
    """List all repositories."""
    table = Table(title="Repositories")
    table.add_column("Index", style="dim")
    table.add_column("Repository", style="cyan")
    table.add_column("Workflows", style="dim")

    for i, repo in enumerate(ALL_REPOSITORIES, 1):
        table.add_row(str(i), repo, "v2" if repo in REPOSITORIES_V2 else "v1")

    console.print(table)


@cli.command()
@pass_tiamat_context
def settings(ctx):
    """Display current settings."""
    table = Table(title="Current Settings")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Base Branch", ctx.base_branch)
    table.add_row("Head Branch", ctx.head_branch)
    table.add_row("GitHub Token", "Set ✅" if GITHUB_TOKEN else "Not Set ❌")
    table.add_row(
        "Slack Integration",
        "Configured ✅" if SlackService.is_configured() else "Not Configured ❌",
    )
    table.add_row("Repositories", str(len(ALL_REPOSITORIES)))
    table.add_row("Repositories (v2 workflows)", str(len(REPOSITORIES_V2)))

    console.print(table)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No arguments, start shell
        sys.argv.append("shell")
    cli()

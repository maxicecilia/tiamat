import os
import sys
import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from dotenv import load_dotenv

load_dotenv()

from services.github import GitHubService, GITHUB_TOKEN
from commands.help import register_help_command
from commands.shell import register_shell_command
from commands.release import register_release_commands
from commands.actions import register_actions_commands
from commands.jira import register_jira_commands

# Default branches
DEFAULT_BASE_BRANCH = "main"
DEFAULT_HEAD_BRANCH = "release"

REPOSITORIES = os.getenv("REPOSITORIES", "").split(",")

console = Console()


class TiamatContext:
    def __init__(self):
        self.base_branch = DEFAULT_BASE_BRANCH
        self.head_branch = DEFAULT_HEAD_BRANCH


pass_tiamat_context = click.make_pass_decorator(TiamatContext, ensure=True)


def resolve_repo(repo_input):
    """Convert short repo name to full name if needed"""
    if "/" not in repo_input:
        matching_repos = [r for r in REPOSITORIES if r.split("/")[1] == repo_input]
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
shell_command = register_shell_command(cli, REPOSITORIES, GITHUB_TOKEN, TiamatContext)

# Register release commands
bump_command, releases_command = register_release_commands(cli, REPOSITORIES)

# Register GitHub Actions commands
run_command = register_actions_commands(cli, REPOSITORIES)

# Register Jira commands
jira_command, sprint_report_command = register_jira_commands(cli)


@cli.command()
@click.argument("compare_spec", required=False)
@click.argument("repo", required=False)
@pass_tiamat_context
def check(ctx, compare_spec, repo):
    """Check for pending commits between branches.

    COMPARE_SPEC can be in format 'base...head' or 'base..head'
    Examples:
      - check main...release
      - check main...release coralreef
      - check (uses default branches from context)
    """
    if not GITHUB_TOKEN:
        rprint(
            "[bold red]❌ GITHUB_TOKEN is not set. Please set it in your environment.[/bold red]"
        )
        return

    base_branch = ctx.base_branch
    head_branch = ctx.head_branch

    # Parse the compare_spec if provided
    if compare_spec:
        if "..." in compare_spec:
            base_branch, head_branch = compare_spec.split("...", 1)
        elif ".." in compare_spec:
            base_branch, head_branch = compare_spec.split("..", 1)

    if repo:
        repo_full = resolve_repo(repo)
        GitHubService.get_pending_commits(repo_full, base_branch, head_branch)
    else:
        for repo in REPOSITORIES:
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
      - createpr main...release coralreef
      - createpr (uses default branches from context)
    """
    if not GITHUB_TOKEN:
        rprint(
            "[bold red]❌ GITHUB_TOKEN is not set. Please set it in your environment.[/bold red]"
        )
        return

    base_branch = ctx.base_branch
    head_branch = ctx.head_branch

    # Parse the compare_spec if provided
    if compare_spec:
        if "..." in compare_spec:
            base_branch, head_branch = compare_spec.split("...", 1)
        elif ".." in compare_spec:
            base_branch, head_branch = compare_spec.split("..", 1)

    if repo:
        repo_full = resolve_repo(repo)
        has_commits = GitHubService.get_pending_commits(
            repo_full, base_branch, head_branch
        )
        if has_commits:
            GitHubService.create_pull_request(repo_full, base_branch, head_branch)
    else:
        for repo in REPOSITORIES:
            has_commits = GitHubService.get_pending_commits(
                repo, base_branch, head_branch
            )
            if has_commits:
                GitHubService.create_pull_request(repo, base_branch, head_branch)


@cli.command()
def list():
    """List all repositories."""
    table = Table(title="Repositories")
    table.add_column("Index", style="dim")
    table.add_column("Repository", style="cyan")

    for i, repo in enumerate(REPOSITORIES, 1):
        table.add_row(str(i), repo)

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
    table.add_row("Repositories", str(len(REPOSITORIES)))

    console.print(table)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No arguments, start shell
        sys.argv.append("shell")
    cli()

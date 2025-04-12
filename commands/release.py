import click
from rich import print as rprint
from services.github import GitHubService, GITHUB_TOKEN


def register_release_commands(cli, REPOSITORIES):
    """Register release-related commands with the CLI"""

    def resolve_repo(repo_input):
        """Convert short repo name to full name if needed"""
        if not repo_input:
            return None

        if "/" not in repo_input:
            matching_repos = [r for r in REPOSITORIES if r.split("/")[1] == repo_input]
            if matching_repos:
                return matching_repos[0]
        return repo_input

    @cli.command()
    @click.argument("tag", required=True)
    @click.argument("repo", required=True)
    @click.option(
        "--target", "-t", default="main", help="Target branch for the release"
    )
    @click.option(
        "--name", "-n", help="Release name (defaults to tag if not specified)"
    )
    @click.option("--body", "-b", help="Release description")
    @click.option("--draft/--no-draft", default=False, help="Create as draft release")
    @click.option(
        "--prerelease/--no-prerelease", default=False, help="Mark as pre-release"
    )
    def release(tag, repo, target, name, body, draft, prerelease):
        """Create a new GitHub release.

        Examples:
          - release v1.0.0 coralreef
          - release v1.0.0 coralreef --target main --name "Version 1.0.0"
          - release v1.0.0 coralreef --draft --prerelease
        """
        if not GITHUB_TOKEN:
            rprint(
                "[bold red]❌ GITHUB_TOKEN is not set. Please set it in your environment.[/bold red]"
            )
            return

        repo_full = resolve_repo(repo)
        if not repo_full:
            rprint(f"[bold red]❌ Repository not found: {repo}[/bold red]")
            return

        GitHubService.create_release(
            repo_full,
            tag,
            target_branch=target,
            name=name,
            body=body,
            draft=draft,
            prerelease=prerelease,
        )

    @cli.command()
    @click.argument("repo", required=False)
    @click.option("--limit", "-n", default=5, help="Number of releases to show")
    def releases(repo, limit):
        """List recent releases for a repository.

        If REPO is not specified, lists releases for all repositories.

        Examples:
          - releases coralreef
          - releases coralreef --limit 10
          - releases (lists for all repos)
        """
        if not GITHUB_TOKEN:
            rprint(
                "[bold red]❌ GITHUB_TOKEN is not set. Please set it in your environment.[/bold red]"
            )
            return

        if repo:
            repo_full = resolve_repo(repo)
            if not repo_full:
                rprint(f"[bold red]❌ Repository not found: {repo}[/bold red]")
                return

            GitHubService.list_releases(repo_full, limit)
        else:
            for repository in REPOSITORIES:
                GitHubService.list_releases(repository, limit)

    # Return the command functions for reference
    return release, releases

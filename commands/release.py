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
    @click.argument("repo", required=True)
    @click.option("--major", is_flag=True, help="Bump the major version")
    @click.option("--minor", is_flag=True, help="Bump the minor version (default)")
    @click.option("--patch", is_flag=True, help="Bump the patch version")
    @click.option(
        "--branch", "-b", default="main", help="Target branch for the release"
    )
    @click.option("--name", "-n", help="Release name (defaults to '1.0.0' format)")
    @click.option("--draft/--no-draft", default=False, help="Create as draft release")
    @click.option(
        "--prerelease/--no-prerelease", default=False, help="Mark as pre-release"
    )
    def bump(repo, major, minor, patch, branch, name, draft, prerelease):
        """Bump version and create a new release.

        Automatically increments the version number based on the latest release
        and creates a new GitHub release with the bumped version.

        By default bumps the minor version (1.0.0 -> 1.1.0).

        Examples:
          - bump coralreef
          - bump coralreef --patch
          - bump coralreef --major --name "Major Release" -m "Lots of new features!"
        """
        if not GITHUB_TOKEN:
            rprint(
                "[bold red]❌ GITHUB_TOKEN is not set. Please set it in your environment.[/bold red]"
            )
            return

        # Resolve repository name
        repo_full = resolve_repo(repo)
        if not repo_full:
            rprint(f"[bold red]❌ Repository not found: {repo}[/bold red]")
            return

        # Get latest version
        current_version = GitHubService.get_latest_version(repo_full)

        # Determine which part to bump based on flags
        bump_type = "minor"  # default
        if major:
            bump_type = "major"
        elif patch:
            bump_type = "patch"

        # Bump version
        new_version = GitHubService.bump_version(current_version, bump_type)

        # Set default name if not provided
        if not name:
            name = f"{new_version}"

        # Print summary before creating release
        rprint(f"[bold blue]🚀 Creating new release:[/bold blue]")
        rprint(f"  • [green]Repository:[/green] {repo_full}")
        rprint(f"  • [green]Current version:[/green] {current_version}")
        rprint(f"  • [green]New version:[/green] {new_version} ({bump_type} bump)")
        rprint(f"  • [green]Target branch:[/green] {branch}")
        rprint(f"  • [green]Name:[/green] {name}")

        # Ask for confirmation
        if click.confirm("Do you want to create this release?", default=True):
            # Create the release
            success = GitHubService.create_release(
                repo_full,
                new_version,
                target_branch=branch,
                name=name,
                body="",
                draft=draft,
                prerelease=prerelease,
            )

            if success:
                rprint(
                    f"[bold green]✅ Successfully bumped version from {current_version} to {new_version}[/bold green]"
                )
        else:
            rprint("[yellow]Release creation cancelled.[/yellow]")

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
    return bump, releases

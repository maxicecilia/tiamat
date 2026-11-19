import click
from rich import print as rprint
from services.github import GitHubService, GITHUB_TOKEN


def register_merge_commands(cli, REPOSITORIES):
    """Register merge-related commands with the CLI"""

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
    @click.argument("pr_number", required=True, type=int)
    def merge(repo, pr_number):
        """Merge a pull request.

        Merges the specified pull request using the default merge method.

        Args:
            repo: Repository name (can be short name like 'my-service' or full name like 'owner/my-service')
            pr_number: The number of the pull request to merge

        Examples:
          - merge my-service 123
          - merge owner/my-service 456
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

        # Print summary before merging
        rprint("[bold blue]🔀 Merging pull request:[/bold blue]")
        rprint(f"  • [green]Repository:[/green] {repo_full}")
        rprint(f"  • [green]PR Number:[/green] #{pr_number}")

        # Ask for confirmation
        if click.confirm("Do you want to merge this pull request?", default=True):
            # Merge the pull request
            success = GitHubService.merge_pr(repo_full, pr_number)

            if success:
                rprint(
                    f"[bold green]✅ Successfully merged PR #{pr_number} in {repo_full}[/bold green]"
                )
            else:
                rprint(
                    f"[bold red]❌ Failed to merge PR #{pr_number} in {repo_full}[/bold red]"
                )
        else:
            rprint("[yellow]Merge cancelled.[/yellow]")

    # Return the command function for reference
    return merge

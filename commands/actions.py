from datetime import datetime

import click
from rich import print as rprint
from rich.table import Table

from services.github import GITHUB_TOKEN, GitHubService

# Define workflow shortcuts/presets
WORKFLOW_PRESETS = {
    "deploy": {
        "environments": {
            "staging": {
                "workflow": "deploy.preview.manual.yml",
                "inputs": {"region": "eu-central-1", "stage": "staging"},
                "branch": "release",
                "description": "Deploy to staging EU",
            },
            "prod": {
                "workflow": "deploy.live.manual.yml",
                "inputs": {},
                "branch": "main",
                "description": "Deploy to prod EU and US",
            },
            "demo": {
                "workflow": "deploy.preview.demo.yml",
                "inputs": {},
                "branch": "release",
                "description": "Deploy to demo EU and US",
            },
        }
    },
    # TODO: add presets for migrations later.
    "migrate": {
        "environments": {
            "staging": {
                "workflow": "test.yml",
                "inputs": {"type": "unit", "coverage": "true"},
                "branch": "develop",
                "description": "Run unit tests with coverage",
            },
        }
    },
}


def register_actions_commands(cli, REPOSITORIES):
    """Register GitHub Actions-related commands with the CLI"""

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
    def workflows(repo):
        """List GitHub Actions workflows for a repository.

        Examples:
          - workflows coralreef
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

        GitHubService.list_workflows(repo_full)

    @cli.command()
    @click.argument("workflow", required=True)
    @click.argument("repo", required=True)
    @click.option("--branch", "-b", default="main", help="Branch to run workflow on")
    @click.option(
        "--input", "-i", multiple=True, help="Workflow inputs in key=value format"
    )
    def run(workflow, repo, branch, input):
        """Run a GitHub Actions workflow.

        WORKFLOW can be the workflow ID, filename, or name.

        Examples:
          - run build.yml coralreef
          - run build.yml coralreef --branch develop
          - run "Build and Test" coralreef
          - run deploy.yml coralreef -i version=1.0.0 -i environment=production
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

        # Parse inputs if provided
        inputs = {}
        for inp in input:
            if "=" not in inp:
                rprint(
                    f"[bold yellow]⚠️ Ignoring invalid input format: {inp}. Use key=value format.[/bold yellow]"
                )
                continue

            key, value = inp.split("=", 1)
            inputs[key] = value

        inputs_dict = inputs if inputs else None
        GitHubService.trigger_workflow(repo_full, workflow, branch, inputs_dict)

    @cli.command()
    def presets():
        """List available workflow presets and environments."""
        table = Table(title="Available Workflow Presets")
        table.add_column("Command", style="cyan")
        table.add_column("Environment", style="green")
        table.add_column("Workflow", style="yellow")
        table.add_column("Branch", style="magenta")
        table.add_column("Description", style="blue")
        table.add_column("Inputs", style="dim")

        for preset_name, preset in WORKFLOW_PRESETS.items():
            for env_name, env in preset["environments"].items():
                workflow = env["workflow"]
                branch = env.get("branch", "main")
                inputs_str = ", ".join([f"{k}={v}" for k, v in env["inputs"].items()])
                command = f"{preset_name} {env_name} <repo>"

                table.add_row(
                    preset_name,
                    env_name,
                    workflow,
                    branch,
                    env["description"],
                    inputs_str,
                )

        rprint(table)
        rprint("\n[dim]Usage example: deploy staging coralreef[/dim]")
        rprint("[dim]Override branch: deploy staging coralreef --branch feature[/dim]")
        rprint("[dim]Add inputs: deploy staging coralreef -i debug=true[/dim]")

    @cli.command()
    @click.argument("repo", required=True)
    @click.option("--major", is_flag=True, help="Bump the major version")
    @click.option("--minor", is_flag=True, help="Bump the minor version (default)")
    @click.option("--patch", is_flag=True, help="Bump the patch version")
    @click.option(
        "--branch", "-b", default="main", help="Target branch for the release"
    )
    @click.option("--name", "-n", help="Release name (defaults to '1.0.0' format)")
    @click.option("--body", "-m", help="Release description/message")
    @click.option("--draft/--no-draft", default=False, help="Create as draft release")
    @click.option(
        "--prerelease/--no-prerelease", default=False, help="Mark as pre-release"
    )
    def bump(repo, major, minor, patch, branch, name, body, draft, prerelease):
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

        # Set default body if not provided
        if not body:
            body = f"Release {new_version} created by Tiamat on {datetime.now().strftime('%B %d, %Y')}"

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
                body=body,
                draft=draft,
                prerelease=prerelease,
            )

            if success:
                rprint(
                    f"[bold green]✅ Successfully bumped version from {current_version} to {new_version}[/bold green]"
                )
        else:
            rprint("[yellow]Release creation cancelled.[/yellow]")

    # Dynamic command registration based on presets
    # This creates commands like: deploy, test, etc.
    for preset_name, preset_config in WORKFLOW_PRESETS.items():
        # Define a closure to capture the preset name
        def make_command(name, config):
            @cli.command(name=name)
            @click.argument("environment", required=True)
            @click.argument("repo", required=True)
            @click.option("--branch", "-b", help="Override the default branch")
            @click.option(
                "--input",
                "-i",
                multiple=True,
                help="Additional inputs in key=value format",
            )
            def preset_command(environment, repo, branch, input):
                """Run a predefined workflow."""
                if not GITHUB_TOKEN:
                    rprint(
                        "[bold red]❌ GITHUB_TOKEN is not set. Please set it in your environment.[/bold red]"
                    )
                    return

                # Check if environment exists for this preset
                if environment not in config["environments"]:
                    available = ", ".join(config["environments"].keys())
                    rprint(
                        f"[bold red]❌ Unknown environment: '{environment}' for preset '{name}'.[/bold red]"
                    )
                    rprint(f"[yellow]Available environments: {available}[/yellow]")
                    return

                # Get environment configuration
                env_config = config["environments"][environment]
                workflow_file = env_config["workflow"]

                # Use provided branch or default from config
                workflow_branch = branch or env_config.get("branch", "main")

                # Start with preset inputs
                inputs = dict(env_config["inputs"])

                # Add any additional inputs from command line
                for inp in input:
                    if "=" not in inp:
                        rprint(
                            f"[bold yellow]⚠️ Ignoring invalid input format: {inp}. Use key=value format.[/bold yellow]"
                        )
                        continue

                    key, value = inp.split("=", 1)
                    inputs[key] = value

                # Resolve repository name
                repo_full = resolve_repo(repo)
                if not repo_full:
                    rprint(f"[bold red]❌ Repository not found: {repo}[/bold red]")
                    return

                # Show what we're about to do
                rprint(f"[bold blue]🚀 Running workflow:[/bold blue]")
                rprint(f"  • [green]Command:[/green] {name} {environment}")
                rprint(f"  • [green]Description:[/green] {env_config['description']}")
                rprint(f"  • [green]Workflow:[/green] {workflow_file}")
                rprint(f"  • [green]Repository:[/green] {repo_full}")
                rprint(f"  • [green]Branch:[/green] {workflow_branch}")

                if inputs:
                    rprint(f"  • [green]Inputs:[/green]")
                    for key, value in inputs.items():
                        rprint(f"    - {key}: {value}")

                # Trigger the workflow
                GitHubService.trigger_workflow(
                    repo_full, workflow_file, workflow_branch, inputs
                )

            # Add more specific help text
            environments = ", ".join(config["environments"].keys())
            preset_command.__doc__ = f"""
Run workflows with predefined settings.

Available environments: {environments}

Examples:
  - {name} {next(iter(config['environments']))} coralreef
  - {name} {next(iter(config['environments']))} coralreef --branch custom-branch
"""
            return preset_command

        # Create the command
        make_command(preset_name, preset_config)

    # Return the command functions for reference
    return workflows, run, bump

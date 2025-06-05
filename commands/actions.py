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
    }
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
    return run

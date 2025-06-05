import click
from rich import print as rprint
from services.jira import JiraService, JIRA_DEFAULT_PROJECT


def register_jira_commands(cli):
    """Register Jira-related commands with the CLI"""

    @cli.command()
    @click.argument("query", required=True)
    @click.option(
        "--project", "-p", help=f"Project key (default: {JIRA_DEFAULT_PROJECT})"
    )
    @click.option("--limit", "-n", default=20, help="Maximum number of results")
    def jira(query, project, limit):
        """Search for issues in Jira.

        QUERY is a JQL query string or simple text search.

        If no project is specified, the default project from JIRA_DEFAULT_PROJECT
        environment variable will be used.

        Examples:
          - jira "bug"
          - jira "priority = High" -p PROJ
          - jira "assignee = currentUser()"
          - jira "created >= -30d" --limit 50
        """
        # Use default project if not specified and default exists
        project_key = project or JIRA_DEFAULT_PROJECT

        if not project_key:
            rprint(
                "[yellow]No project specified. Searching across all projects.[/yellow]"
                "\n[dim]Set JIRA_DEFAULT_PROJECT in .env to use a default.[/dim]"
            )

        JiraService.search_issues(query, project_key, limit)

    @cli.command()
    @click.option("--sprint", help="Sprint name (e.g., 'Sprint 47')", required=True)
    @click.option(
        "--project", "-p", help=f"Project key (default: {JIRA_DEFAULT_PROJECT})"
    )
    def sprint_report(sprint, project):
        """Generate a concise sprint report with story point totals.

        Examples:
          - sprint-report --sprint "Sprint 47"
        """
        query = ' AND sprint = "Sprint 47" AND status in ("DONE", "CLOSED", "DEPLOYED")'

        # Use default project if not specified and default exists
        project_key = project or JIRA_DEFAULT_PROJECT

        JiraService.sprint_report(query, project_key)

    # Return the command functions for reference
    return jira, sprint_report

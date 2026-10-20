import csv
import io
import os
from datetime import UTC, datetime, timedelta

import click
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from services.github import GITHUB_TOKEN, GitHubService

console = Console()

RAW_COLUMNS = [
    "Date",
    "CreatedAt",
    "Repository",
    "Name",
    "Tag",
    "Tickets",
    "Failed",
    "LeadTimeDays",
    "Body",
]


TEAM_REPOS = {}

CACHE_DIR = "cache"


def register_stats_command(cli, REPOSITORIES, FE_REPOSITORIES, BETA_REPOSITORIES, ML_REPOSITORIES, DATAOPS_REPOSITORIES):
    """Register the stats command with the CLI"""

    global TEAM_REPOS
    TEAM_REPOS = {
        "beta": BETA_REPOSITORIES,
        "ml": ML_REPOSITORIES,
        "dataops": DATAOPS_REPOSITORIES,
        "fnd": REPOSITORIES + FE_REPOSITORIES,
    }

    def resolve_repo(repo_input, repos=None):
        """Convert short repo name to full name if needed"""
        if not repo_input:
            return None

        search_repos = repos if repos is not None else REPOSITORIES
        if "/" not in repo_input:
            matching_repos = [r for r in search_repos if r.split("/")[1] == repo_input]
            if matching_repos:
                return matching_repos[0]
        return repo_input

    @cli.command()
    @click.argument("month", required=False)
    @click.option(
        "--months",
        "-m",
        default=6,
        show_default=True,
        help="Number of months of release history",
    )
    @click.option(
        "--repo", "-r", default=None, help="Limit stats to a specific repository"
    )
    @click.option(
        "--team", "-t", type=click.Choice(["beta", "ml", "dataops", "fnd", "all"]), default=None,
        help="Run stats for a specific team (beta, ml, dataops, fnd) or all teams"
    )
    @click.option(
        "--refresh",
        is_flag=True,
        help="Ignore cached data and fetch fresh data from GitHub",
    )
    def stats(month, months, repo, team, refresh):
        """Show release activity and DORA metrics across repositories.

        Fetches all releases created within the last MONTHS for each repository
        and displays them as a copy-paste friendly CSV, a formatted table, and
        a DORA metrics summary. Raw data is cached to cache/stats_<date>.csv and
        reused on subsequent runs unless --refresh is passed.

        Pass MONTH as YYYY-MM to scope the stats to a single calendar month
        instead of a rolling window.

        Examples:
          - stats
          - stats --months 3
          - stats --repo coralreef
          - stats --refresh
          - stats 2026-07
          - stats --team beta
          - stats --team ml --months 3
          - stats --team dataops --refresh
          - stats --team all
        """
        if not GITHUB_TOKEN:
            rprint(
                "[bold red]❌ GITHUB_TOKEN is not set. Please set it in your environment.[/bold red]"
            )
            return

        month_range = None
        month_label = None
        if month:
            month_range = _parse_month(month)
            month_start, _ = month_range
            month_label = month_start.strftime("%B %Y")
            now = datetime.now(UTC)
            days_needed = (now - month_start).days + 1
            months = max(-(-days_needed // 30), 1)

        if team == "all":
            _run_all_teams_stats(months, month_range, month_label, refresh)
            return

        # Determine which repositories to use based on team
        if team:
            repos = TEAM_REPOS.get(team, [])
            if not repos:
                rprint(f"[bold red]❌ No repositories configured for team: {team}[/bold red]")
                return
            rprint(f"[bold blue]📊 Running stats for Team {team.upper()}: {len(repos)} repositories[/bold blue]")
        elif repo:
            repo_full = resolve_repo(repo)
            if not repo_full:
                rprint(f"[bold red]❌ Repository not found: {repo}[/bold red]")
                return
            repos = [repo_full]
        else:
            repos = REPOSITORIES

        filename = _stats_filename(team)
        cutoff = datetime.now(UTC) - timedelta(days=months * 30)

        cached = None
        window = None
        need_fetch = None

        if not refresh:
            cached, window = _load_raw_csv(filename)
            if cached is not None and window is not None and window >= months:
                cached_repos = {r["repo"] for r in cached}
                missing = [r for r in repos if r not in cached_repos]
                if not missing:
                    rprint(
                        f"[bold blue]📄 Using cached data from {filename} "
                        f"(pass --refresh to update).[/bold blue]"
                    )
                    windowed = [
                        r
                        for r in cached
                        if r["repo"] in repos and r["created_at"] >= cutoff
                    ]
                    filtered = _filter_to_month(windowed, month_range)
                    if not filtered:
                        rprint(
                            f"[yellow]No cached releases found for {month_label}.[/yellow]"
                            if month_range
                            else "[yellow]No cached releases match the requested window.[/yellow]"
                        )
                        return
                    dora_stats = (
                        _compute_dora_stats_for_month(filtered, month_label)
                        if month_range
                        else _compute_dora_stats(filtered, months)
                    )
                    _render(filtered, dora_stats)
                    return

                need_fetch = missing
                rprint(
                    f"[yellow]📄 Cache at {filename} is missing {len(missing)} "
                    f"repo(s) — fetching them from GitHub.[/yellow]"
                )
            elif cached is not None and window is not None:
                need_fetch = repos
                rprint(
                    f"[yellow]📄 Cache at {filename} covers {window} months but "
                    f"you need {months} — refreshing from GitHub.[/yellow]"
                )
            else:
                need_fetch = repos
                rprint(
                    f"[yellow]📄 No usable cache at {filename} — fetching from "
                    f"GitHub.[/yellow]"
                )
        else:
            need_fetch = repos
            rprint(
                "[yellow]📄 --refresh passed — fetching fresh data from GitHub.[/yellow]"
            )

        fetched = _fetch_and_enrich(need_fetch, months)
        base = [r for r in (cached or []) if r["repo"] not in need_fetch]
        windowed = [r for r in (base + fetched) if r["created_at"] >= cutoff]
        windowed.sort(key=lambda r: r["created_at"], reverse=True)

        if not windowed:
            rprint("[yellow]No releases found within the selected window.[/yellow]")
            return

        filtered = _filter_to_month(windowed, month_range)
        dora_stats = (
            _compute_dora_stats_for_month(filtered, month_label)
            if month_range
            else _compute_dora_stats(filtered, months)
        )
        if filtered:
            _render(filtered, dora_stats)
        else:
            rprint(f"[yellow]No releases found for {month_label}.[/yellow]")
        _save_raw_csv(windowed, dora_stats, filename, months)

    return stats


def _run_all_teams_stats(months, month_range, month_label, refresh):
    """Run stats for all teams and show only DORA metrics for each"""
    for team_name, repos in TEAM_REPOS.items():
        if not repos:
            continue
        rprint(f"\n[bold blue]📊 Team {team_name.upper()}: {len(repos)} repositories[/bold blue]")
        filename = _stats_filename(team_name)
        cutoff = datetime.now(UTC) - timedelta(days=months * 30)

        cached = None
        window = None
        need_fetch = None

        if not refresh:
            cached, window = _load_raw_csv(filename)
            if cached is not None and window is not None and window >= months:
                cached_repos = {r["repo"] for r in cached}
                missing = [r for r in repos if r not in cached_repos]
                if not missing:
                    windowed = [
                        r
                        for r in cached
                        if r["repo"] in repos and r["created_at"] >= cutoff
                    ]
                    filtered = _filter_to_month(windowed, month_range)
                    if filtered:
                        dora_stats = (
                            _compute_dora_stats_for_month(filtered, month_label)
                            if month_range
                            else _compute_dora_stats(filtered, months)
                        )
                        _print_dora_stats(dora_stats)
                    else:
                        rprint(f"[yellow]No releases found for {month_label}.[/yellow]")
                    continue

                need_fetch = missing
                rprint(
                    f"[yellow]📄 Cache at {filename} is missing {len(missing)} "
                    f"repo(s) — fetching them from GitHub.[/yellow]"
                )
            elif cached is not None and window is not None:
                need_fetch = repos
                rprint(
                    f"[yellow]📄 Cache at {filename} covers {window} months but "
                    f"you need {months} — refreshing from GitHub.[/yellow]"
                )
            else:
                need_fetch = repos
                rprint(
                    f"[yellow]📄 No usable cache at {filename} — fetching from "
                    f"GitHub.[/yellow]"
                )
        else:
            need_fetch = repos
            rprint(
                "[yellow]📄 --refresh passed — fetching fresh data from GitHub.[/yellow]"
            )

        fetched = _fetch_and_enrich(need_fetch, months)
        base = [r for r in (cached or []) if r["repo"] not in need_fetch]
        windowed = [r for r in (base + fetched) if r["created_at"] >= cutoff]
        windowed.sort(key=lambda r: r["created_at"], reverse=True)

        if not windowed:
            rprint("[yellow]No releases found within the selected window.[/yellow]")
            continue

        filtered = _filter_to_month(windowed, month_range)
        if filtered:
            dora_stats = (
                _compute_dora_stats_for_month(filtered, month_label)
                if month_range
                else _compute_dora_stats(filtered, months)
            )
            _print_dora_stats(dora_stats)
        else:
            rprint(f"[yellow]No releases found for {month_label}.[/yellow]")
        _save_raw_csv(windowed, dora_stats, filename, months)


def _fetch_and_enrich(repos, months):
    """Fetch releases from GitHub for the given repos and enrich them"""
    releases = []
    for repository in repos:
        releases.extend(GitHubService.get_releases_since(repository, months))
    if not releases:
        return []
    _enrich_releases(releases)
    return releases


def _enrich_releases(releases):
    """Add tickets, failure flag and lead time to each release"""
    by_repo = {}
    for release in releases:
        by_repo.setdefault(release["repo"], []).append(release)

    for repo_releases in by_repo.values():
        repo_releases.sort(key=lambda r: r["created_at"])
        previous = None
        for release in repo_releases:
            release["tickets"] = GitHubService.extract_tickets(release["body"])
            release["is_failed"] = GitHubService.is_failed_deployment(
                release["body"]
            )
            if previous is not None:
                oldest_commit = GitHubService.get_release_lead_time_commit(
                    release["repo"],
                    release["tag_name"],
                    previous["tag_name"],
                )
                release["lead_time_days"] = (
                    round(
                        (release["created_at"] - oldest_commit).total_seconds()
                        / 86400,
                        2,
                    )
                    if oldest_commit
                    else None
                )
            else:
                release["lead_time_days"] = None
            previous = release


def _parse_month(month_str):
    """Parse a 'YYYY-MM' string into a (start, end) UTC datetime range.

    `end` is exclusive (the first instant of the following month).
    """
    parts = month_str.split("-")
    if len(parts) != 2 or len(parts[0]) != 4:
        raise click.UsageError(
            f"Invalid month '{month_str}' — expected format YYYY-MM, e.g. 2026-07"
        )

    try:
        year, month_num = int(parts[0]), int(parts[1])
    except ValueError:
        raise click.UsageError(
            f"Invalid month '{month_str}' — expected format YYYY-MM, e.g. 2026-07"
        )

    if not 1 <= month_num <= 12:
        raise click.UsageError(
            f"Invalid month '{month_str}' — expected format YYYY-MM, e.g. 2026-07"
        )

    start = datetime(year, month_num, 1, tzinfo=UTC)
    end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if month_num == 12
        else datetime(year, month_num + 1, 1, tzinfo=UTC)
    )
    return start, end


def _filter_to_month(releases, month_range):
    """Narrow an already window-filtered release list down to one calendar month"""
    if not month_range:
        return releases
    start, end = month_range
    return [r for r in releases if start <= r["created_at"] < end]


def _compute_dora_stats_for_month(releases, month_label):
    """Compute DORA-style metrics scoped to a single calendar month"""
    total_deploys = len(releases)
    total_tickets = sum(len(r["tickets"]) for r in releases)
    total_failures = sum(1 for r in releases if r["is_failed"])
    change_failure_rate = (
        round(total_failures / total_deploys * 100, 1) if total_deploys else 0
    )

    lead_times = [
        r["lead_time_days"] for r in releases if r["lead_time_days"] is not None
    ]
    avg_lead_time = (
        round(sum(lead_times) / len(lead_times), 2) if lead_times else None
    )

    stats = {
        f"Total deploys ({month_label})": total_deploys,
        f"Total tickets deployed ({month_label})": total_tickets,
    }
    if total_deploys:
        stats[f"Change Failure Rate ({month_label})"] = f"{change_failure_rate}%"
        stats[f"Avg lead time / release ({month_label})"] = (
            f"{avg_lead_time} days" if avg_lead_time is not None else "n/a"
        )
    return stats


def _compute_dora_stats(releases, months):
    """Compute DORA-style metrics from the fetched releases"""
    now = datetime.now(UTC)
    cutoff_30d = now - timedelta(days=30)

    releases_30d = [r for r in releases if r["created_at"] >= cutoff_30d]
    total_deploys_30d = len(releases_30d)
    tickets_30d = sum(len(r["tickets"]) for r in releases_30d)

    total_deploys = len(releases)
    total_tickets = sum(len(r["tickets"]) for r in releases)

    total_failures = sum(1 for r in releases if r["is_failed"])
    change_failure_rate = (
        round(total_failures / total_deploys * 100, 1) if total_deploys else 0
    )

    lead_times = [
        r["lead_time_days"] for r in releases if r["lead_time_days"] is not None
    ]
    avg_lead_time = (
        round(sum(lead_times) / len(lead_times), 2) if lead_times else None
    )

    stats = {
        "Total deploys (last 30 days)": total_deploys_30d,
        "Total tickets deployed (last 30 days)": tickets_30d,
        f"Avg deploys/month (last {months} months)": round(
            total_deploys / months, 2
        ),
        f"Avg tickets/month (last {months} months)": round(
            total_tickets / months, 2
        ),
    }
    if total_deploys:
        stats[f"Change Failure Rate (last {months} months)"] = (
            f"{change_failure_rate}%"
        )
        stats[f"Avg lead time / release (last {months} months)"] = (
            f"{avg_lead_time} days" if avg_lead_time is not None else "n/a"
        )
    return stats


def _render(releases, dora_stats):
    _print_csv(releases, dora_stats)
    _print_table(releases)
    _print_dora_stats(dora_stats)


def _print_csv(releases, dora_stats):
    """Print releases and DORA metrics as copy-paste friendly CSV"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Date", "Repository", "Name"])
    for release in releases:
        writer.writerow([release["date"], release["repo"], release["name"]])
    buffer.write("\n")
    writer.writerow(["Metric", "Value"])
    for metric, value in dora_stats.items():
        writer.writerow([metric, value])
    rprint("\n[bold cyan]CSV:[/bold cyan]")
    click.echo(buffer.getvalue().rstrip())


def _print_table(releases):
    """Print releases as a nicely formatted table"""
    table = Table(title=f"Releases ({len(releases)})")
    table.add_column("Date", style="blue")
    table.add_column("Repository", style="cyan")
    table.add_column("Name", style="green")

    for release in releases:
        table.add_row(release["date"], release["repo"], release["name"])

    rprint("\n[bold]Summary:[/bold]")
    console.print(table)


def _print_dora_stats(stats):
    """Print DORA metrics as a nicely formatted table at the bottom"""
    table = Table(title="DORA Metrics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    for metric, value in stats.items():
        table.add_row(metric, str(value))

    rprint("\n[bold]Share with the team:[/bold]")
    console.print(table)


def _stats_filename(team=None):
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    name = f"stats_{team}_{date}.csv" if team else f"stats_{date}.csv"
    return os.path.join(CACHE_DIR, name)


def _save_raw_csv(releases, dora_stats, filename, months):
    """Save all raw release data used to compute the metrics to a file"""
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(RAW_COLUMNS)
        for release in releases:
            writer.writerow(
                [
                    release["date"],
                    release["created_at"].isoformat(),
                    release["repo"],
                    release["name"],
                    release["tag_name"],
                    " ".join(release["tickets"]),
                    "yes" if release["is_failed"] else "no",
                    (
                        release["lead_time_days"]
                        if release["lead_time_days"] is not None
                        else ""
                    ),
                    release["body"],
                ]
            )

        writer.writerow([])
        writer.writerow(["Metric", "Value"])
        for metric, value in dora_stats.items():
            writer.writerow([metric, value])
        writer.writerow([])
        writer.writerow(["Window months", months])

    rprint(f"\n[bold green]📄 Raw data saved to [cyan]{filename}[/cyan][/bold green]")


def _load_raw_csv(filename):
    """Load cached releases and window size from a saved stats CSV.

    Returns:
        (releases, window_months) on success, (None, None) if unusable.
    """
    if not os.path.exists(filename):
        return None, None

    try:
        with open(filename, newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
    except (OSError, csv.Error):
        return None, None

    if not rows or rows[0] != RAW_COLUMNS:
        return None, None

    releases = []
    for row in rows[1:]:
        if not row or not row[0].strip():
            break
        if len(row) < len(RAW_COLUMNS):
            continue
        date, created_at, repo, name, tag, tickets, failed, lead_time, body = row
        try:
            created_dt = datetime.fromisoformat(created_at)
        except ValueError:
            continue
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=UTC)

        releases.append(
            {
                "date": date,
                "created_at": created_dt,
                "repo": repo,
                "name": name,
                "tag_name": tag,
                "body": body,
                "tickets": [t for t in tickets.split(" ") if t],
                "is_failed": failed == "yes",
                "lead_time_days": float(lead_time) if lead_time else None,
            }
        )

    window = None
    for row in rows:
        if len(row) == 2 and row[0] == "Window months":
            try:
                window = int(row[1])
            except ValueError:
                pass
            break

    if not releases or window is None:
        return None, None

    return releases, window
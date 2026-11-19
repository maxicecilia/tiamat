from datetime import UTC, datetime

import pytest
from sqlmodel import Session, select

from api import metrics
from api.db import engine
from api.models import Project, Release

NOW = datetime(2026, 11, 18, 12, tzinfo=UTC)


def _rel(project_id, tag, when, lead_hours=None, failed=False, tickets=()):
    return Release(
        project_id=project_id,
        tag=tag,
        published_at=when,
        created_at=when,
        lead_time_hours=lead_hours,
        is_failed=failed,
        tickets=list(tickets),
    )


@pytest.fixture
def releases(client, monkeypatch):
    monkeypatch.setattr(metrics, "utcnow", lambda: NOW)
    with Session(engine) as s:
        ids = {p.repo: p.id for p in s.exec(select(Project))}
    # Earlier tests edit these projects; pin the teams this module relies on.
    for repo, teams in {
        "acme/api": ["fnd"],
        "acme/web": ["beta", "fnd"],
        "acme/worker": ["fnd"],
    }.items():
        client.patch(f"/api/projects/{ids[repo]}", json={"teams": teams, "archived": False})
    with Session(engine) as s:
        rows = [
            _rel(
                ids["acme/api"], "a2", datetime(2026, 11, 10, tzinfo=UTC), 48, True, ["T-1", "T-2"]
            ),
            _rel(ids["acme/api"], "a1", datetime(2026, 11, 2, tzinfo=UTC), 24, False, ["T-3"]),
            _rel(ids["acme/web"], "w1", datetime(2026, 10, 15, tzinfo=UTC), 72),
            _rel(ids["acme/worker"], "k1", datetime(2026, 9, 1, tzinfo=UTC)),
            _rel(ids["acme/api"], "old", datetime(2026, 1, 1, tzinfo=UTC), 999, True),
        ]
        s.add_all(rows)
        s.commit()
    yield ids
    with Session(engine) as s:
        for r in s.exec(select(Release)):
            s.delete(r)
        s.commit()


def test_month_starts_crosses_year():
    starts = metrics.month_starts(3, datetime(2026, 2, 5, tzinfo=UTC))
    assert [d.strftime("%Y-%m") for d in starts] == ["2025-12", "2026-01", "2026-02"]


def test_overall_metrics(client, releases):
    m = client.get("/api/metrics", params={"months": 6}).json()
    assert [row["month"] for row in m["monthly"]] == [
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
        "2026-10",
        "2026-11",
    ]
    assert m["monthly"][-1]["partial"] is True
    nov = m["monthly"][-1]
    assert nov["deploys"] == 2
    assert nov["failures"] == 1
    assert nov["change_failure_rate"] == 50.0
    assert nov["avg_lead_time_days"] == 1.5
    assert nov["tickets"] == 3

    s = m["summary"]
    assert s["deploys"] == 4  # the January release is outside the window
    # Jun-Oct are complete; Nov 1 -> Nov 18 12:00 is 17.5 of 30 days.
    assert m["elapsed_months"] == round(5 + 17.5 / 30, 2)
    assert s["deploys_per_month"] == round(4 / (5 + 17.5 / 30), 2)
    assert s["change_failure_rate"] == 25.0
    assert s["avg_lead_time_days"] == 2.0  # (2 + 1 + 3) / 3
    assert s["median_lead_time_days"] == 2.0
    assert s["deploys_last_30_days"] == 2


def test_projects_in_several_teams_count_for_each(client, releases):
    m = client.get("/api/metrics").json()
    teams = {t["team"]: t for t in m["teams"]}
    # acme/web is in beta and fnd; acme/api and acme/worker only fnd.
    assert teams["beta"]["deploys"] == 1
    assert teams["fnd"]["deploys"] == 4
    assert m["summary"]["deploys"] == 4  # overall counts each release once


def test_team_filter_and_release_rows(client, releases):
    m = client.get("/api/metrics", params={"team": "Beta"}).json()
    assert m["team"] == "beta"
    assert m["summary"]["deploys"] == 1
    assert m["teams"] == []
    assert {p["name"] for p in m["by_project"]} == {"web"}

    rows = client.get("/api/releases", params={"team": "fnd"}).json()
    assert [r["tag"] for r in rows] == ["a2", "a1", "w1", "k1"]
    assert rows[0]["lead_time_days"] == 2.0
    assert rows[0]["is_failed"] is True


def test_empty_metrics(client, monkeypatch):
    monkeypatch.setattr(metrics, "utcnow", lambda: NOW)
    m = client.get("/api/metrics", params={"team": "nobody"}).json()
    assert m["summary"]["deploys"] == 0
    assert m["summary"]["change_failure_rate"] is None
    assert len(m["monthly"]) == 6

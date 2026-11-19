from sqlmodel import Session

from api.db import engine
from api.seed import seed


def _by_repo(client):
    return {p["repo"]: p for p in client.get("/api/projects").json()}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_seed_imports_env_repos(client):
    projects = _by_repo(client)
    assert set(projects) == {"acme/api", "acme/web", "acme/worker", "acme/beta-svc"}
    assert projects["acme/worker"]["workflow_version"] == "v2"
    assert projects["acme/api"]["workflow_version"] == "v1"
    teams = {repo: [t["name"] for t in p["teams"]] for repo, p in projects.items()}
    assert teams["acme/beta-svc"] == ["beta"]
    assert teams["acme/api"] == ["fnd"]
    # Listed in both BETA_REPOSITORIES and REPOSITORIES: member of both teams.
    assert teams["acme/web"] == ["beta", "fnd"]
    # Only in REPOSITORIES_v2: falls back to fnd.
    assert teams["acme/worker"] == ["fnd"]
    assert [t["name"] for t in projects["acme/web"]["tags"]] == ["frontend"]


def test_seed_is_idempotent_and_keeps_edits(client):
    pid = _by_repo(client)["acme/api"]["id"]
    client.patch(f"/api/projects/{pid}", json={"teams": ["platform"]})
    with Session(engine) as s:
        assert seed(s) == {"projects": 0, "workflow_presets": 0, "team_memberships": 0}
    assert [t["name"] for t in _by_repo(client)["acme/api"]["teams"]] == ["platform"]


def test_workflow_presets_seeded(client):
    presets = {
        (p["environment"], p["version"]): p for p in client.get("/api/workflow-presets").json()
    }
    assert presets[("staging", "v1")]["inputs"] == {"stage": "staging"}
    assert presets[("prod", "v2")]["workflow_file"] == "release-prod.yml"
    assert presets[("prod", "v2")]["inputs"] == {}


def test_project_crud_and_tags(client):
    r = client.post(
        "/api/projects", json={"repo": "acme/new", "tags": ["critical", "critical", "api"]}
    )
    assert r.status_code == 201
    p = r.json()
    assert p["name"] == "new"
    assert sorted(t["name"] for t in p["tags"]) == ["api", "critical"]

    assert client.post("/api/projects", json={"repo": "acme/new"}).status_code == 409
    assert client.post("/api/projects", json={"repo": "noslash"}).status_code == 422

    assert [x["repo"] for x in client.get("/api/projects", params={"tag": "critical"}).json()] == [
        "acme/new"
    ]

    r = client.patch(f"/api/projects/{p['id']}", json={"tags": ["api"], "archived": True})
    assert [t["name"] for t in r.json()["tags"]] == ["api"]
    assert "acme/new" not in _by_repo(client)

    assert client.delete(f"/api/projects/{p['id']}").status_code == 204
    assert client.get(f"/api/projects/{p['id']}").status_code == 404


def test_deleted_project_is_not_reseeded(client):
    pid = _by_repo(client)["acme/beta-svc"]["id"]
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    with Session(engine) as s:
        seed(s)
    assert "acme/beta-svc" not in _by_repo(client)


def test_patch_null_on_required_field_is_ignored(client):
    p = _by_repo(client)["acme/web"]
    r = client.patch(
        f"/api/projects/{p['id']}", json={"name": None, "archived": None, "teams": None}
    )
    assert r.status_code == 200
    assert r.json()["name"] == "web"
    assert [t["name"] for t in r.json()["teams"]] == ["beta", "fnd"]


def test_unknown_api_path_is_json_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


def test_tags_list_counts_rename_and_conflict(client):
    p = client.post("/api/projects", json={"repo": "acme/tagged", "tags": ["svc", "team-x"]}).json()
    tags = {t["name"]: t for t in client.get("/api/tags").json()}
    assert tags["svc"]["project_count"] == 1

    r = client.patch(f"/api/tags/{tags['svc']['id']}", json={"name": "service", "color": "#ff0000"})
    assert r.json() == {"id": tags["svc"]["id"], "name": "service", "color": "#ff0000"}
    assert (
        client.patch(f"/api/tags/{tags['team-x']['id']}", json={"name": "service"}).status_code
        == 409
    )
    assert client.patch(f"/api/tags/{tags['team-x']['id']}", json={"name": "  "}).status_code == 422

    assert client.delete(f"/api/tags/{tags['team-x']['id']}").status_code == 204
    project = client.get(f"/api/projects/{p['id']}").json()
    assert [t["name"] for t in project["tags"]] == ["service"]
    client.delete(f"/api/projects/{p['id']}")


def test_project_deploy_environments(client):
    p = client.post(
        "/api/projects", json={"repo": "acme/envs", "deploy_environments": ["staging"]}
    ).json()
    assert p["deploy_environments"] == ["staging"]
    r = client.patch(f"/api/projects/{p['id']}", json={"deploy_environments": None})
    assert r.json()["deploy_environments"] is None
    client.delete(f"/api/projects/{p['id']}")


def test_workflow_preset_crud(client):
    body = {
        "environment": "qa",
        "version": "v1",
        "workflow_file": "deploy.qa.yml",
        "inputs": {"region": "us"},
    }
    r = client.post("/api/workflow-presets", json=body)
    assert r.status_code == 201
    pid = r.json()["id"]
    assert client.post("/api/workflow-presets", json=body).status_code == 409
    bad = body | {"environment": "qa2", "inputs": {"n": 1}}
    assert client.post("/api/workflow-presets", json=bad).status_code == 422

    r = client.patch(
        f"/api/workflow-presets/{pid}", json={"branch": "release", "workflow_file": None}
    )
    assert r.json()["branch"] == "release"
    assert r.json()["workflow_file"] == "deploy.qa.yml"

    assert client.delete(f"/api/workflow-presets/{pid}").status_code == 204
    assert client.patch(f"/api/workflow-presets/{pid}", json={}).status_code == 404


def test_tags_are_case_insensitive(client):
    r = client.post("/api/tags", json={"name": " Backend "})
    assert r.json()["name"] == "backend"
    assert client.post("/api/tags", json={"name": "BACKEND"}).status_code == 409
    p = client.post(
        "/api/projects", json={"repo": "acme/case", "tags": ["Backend", "backend"]}
    ).json()
    assert [t["name"] for t in p["tags"]] == ["backend"]
    client.delete(f"/api/projects/{p['id']}")
    client.delete(f"/api/tags/{r.json()['id']}")


def test_project_validation(client):
    assert client.post("/api/projects", json={"repo": "a/b/c"}).status_code == 422
    assert (
        client.post("/api/projects", json={"repo": "acme/x", "base_branch": ""}).status_code == 422
    )
    assert client.post("/api/projects", json={"repo": "ACME/API"}).status_code == 409


def test_preset_rename_and_delete_update_project_environments(client):
    preset = client.post(
        "/api/workflow-presets", json={"environment": "uat", "workflow_file": "uat.yml"}
    ).json()
    p = client.post(
        "/api/projects", json={"repo": "acme/uat", "deploy_environments": ["uat", "prod"]}
    ).json()

    client.patch(f"/api/workflow-presets/{preset['id']}", json={"environment": "acceptance"})
    assert client.get(f"/api/projects/{p['id']}").json()["deploy_environments"] == [
        "acceptance",
        "prod",
    ]

    client.delete(f"/api/workflow-presets/{preset['id']}")
    assert client.get(f"/api/projects/{p['id']}").json()["deploy_environments"] == ["prod"]
    client.delete(f"/api/projects/{p['id']}")


def test_preset_conflict_message_names_attempted_values(client):
    staging_v1 = next(
        p
        for p in client.get("/api/workflow-presets").json()
        if p["environment"] == "staging" and p["version"] == "v1"
    )
    r = client.patch(f"/api/workflow-presets/{staging_v1['id']}", json={"version": "v2"})
    assert r.status_code == 409
    assert r.json()["detail"] == "A v2 preset for 'staging' already exists"


def test_project_teams_crud_and_filter(client):
    p = client.post(
        "/api/projects", json={"repo": "acme/multi", "teams": [" Data ", "ml", "data"]}
    ).json()
    assert [t["name"] for t in p["teams"]] == ["data", "ml"]

    in_ml = [x["repo"] for x in client.get("/api/projects", params={"team": "ML"}).json()]
    assert "acme/multi" in in_ml

    teams = {t["name"]: t for t in client.get("/api/teams").json()}
    assert teams["data"]["project_count"] == 1

    r = client.patch(f"/api/teams/{teams['data']['id']}", json={"name": "DataOps"})
    assert r.json()["name"] == "dataops"
    assert (
        client.patch(f"/api/teams/{teams['ml']['id']}", json={"name": "dataops"}).status_code == 409
    )

    r = client.patch(f"/api/projects/{p['id']}", json={"teams": []})
    assert r.json()["teams"] == []
    client.delete(f"/api/projects/{p['id']}")
    client.delete(f"/api/teams/{teams['data']['id']}")


def test_backfill_adds_env_teams_to_existing_projects(client):
    from sqlmodel import select

    from api.models import SyncRun
    from api.seed import backfill_teams_from_env

    pid = _by_repo(client)["acme/web"]["id"]
    client.patch(f"/api/projects/{pid}", json={"teams": ["fnd"]})
    with Session(engine) as s:
        assert backfill_teams_from_env(s) >= 1
        s.commit()
        assert s.exec(select(SyncRun).where(SyncRun.kind == "seed-teams")).first()
    assert [t["name"] for t in _by_repo(client)["acme/web"]["teams"]] == ["beta", "fnd"]


def test_backfill_leaves_dashboard_team_changes_alone(client):
    from api.seed import backfill_teams_from_env

    pid = _by_repo(client)["acme/web"]["id"]
    client.patch(f"/api/projects/{pid}", json={"teams": ["platform"]})
    with Session(engine) as s:
        backfill_teams_from_env(s)
        s.commit()
    assert [t["name"] for t in _by_repo(client)["acme/web"]["teams"]] == ["platform"]
    client.patch(f"/api/projects/{pid}", json={"teams": ["beta", "fnd"]})


def test_blank_team_filter_returns_everything(client):
    everything = client.get("/api/projects").json()
    assert client.get("/api/projects", params={"team": " "}).json() == everything


def test_starred_projects_sort_first(client):
    projects = client.get("/api/projects").json()
    last = projects[-1]
    r = client.patch(f"/api/projects/{last['id']}", json={"starred": True})
    assert r.json()["starred"] is True
    assert client.get("/api/projects").json()[0]["id"] == last["id"]
    overview = client.get("/api/deploys/overview").json()
    assert overview[0]["project"]["id"] == last["id"]
    # null means "no change"
    assert (
        client.patch(f"/api/projects/{last['id']}", json={"starred": None}).json()["starred"]
        is True
    )
    client.patch(f"/api/projects/{last['id']}", json={"starred": False})
    assert client.get("/api/projects").json()[0]["id"] != last["id"]


def test_star_limit(client):
    projects = client.get("/api/projects").json()
    for p in projects:
        client.patch(f"/api/projects/{p['id']}", json={"starred": False})
    extra = [
        client.post("/api/projects", json={"repo": f"acme/star{i}"}).json()["id"] for i in range(6)
    ]
    ids = [p["id"] for p in projects] + extra
    for pid in ids[:5]:
        assert client.patch(f"/api/projects/{pid}", json={"starred": True}).status_code == 200
    r = client.patch(f"/api/projects/{ids[5]}", json={"starred": True})
    assert r.status_code == 409
    assert "up to 5" in r.json()["detail"]
    # Re-starring an already starred project is fine.
    assert client.patch(f"/api/projects/{ids[0]}", json={"starred": True}).status_code == 200
    for pid in ids[:5]:
        client.patch(f"/api/projects/{pid}", json={"starred": False})
    for pid in extra:
        client.delete(f"/api/projects/{pid}")

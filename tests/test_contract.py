import json
from pathlib import Path
import pytest

PATH = Path(__file__).resolve().parents[1] / "public/data/workspace.json"


@pytest.fixture
def data():
    if not PATH.exists():
        pytest.skip("Run the reproducible data build before release-contract checks")
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_source_model_split(data):
    evidence = data["evidence"]
    assert len(evidence["trainMatches"]) == 48
    assert len(evidence["testMatches"]) == 16
    assert not set(evidence["trainMatches"]) & set(evidence["testMatches"])
    assert all(c["passed"] for c in evidence["checks"])


def test_no_raw_statsbomb_event_rows_in_public_contract(data):
    lanes = [a for m in data["matches"] for a in m["actions"]]
    assert lanes
    assert all(a["count"]>=5 and a["playerId"]==0 and a["id"].startswith("lane-") for a in lanes)
    assert "original_event_id" not in PATH.read_text(encoding="utf-8")


def test_all_provider_data_stay_separate(data):
    assert len(data["tracking"]) >= 1
    assert all(t["source"] == "SkillCorner" for t in data["tracking"])
    assert len({p["name"] for p in data["evidence"]["providers"]}) == 3


def test_player_features_complete_and_unique(data):
    keys = {f["key"] for f in data["features"]}
    assert len({p["id"] for p in data["players"]}) == len(data["players"])
    assert all(keys <= p["metrics"].keys() and keys <= p["z"].keys() for p in data["players"])
    assert all(len(p["style"])==60 and p["minutes"]>0 for p in data["players"])


def test_api_returns_aggregate_neighbors(data):
    from fastapi.testclient import TestClient
    from api import app
    client = TestClient(app)
    assert client.get('/health').status_code==200
    p = data["players"][0]
    response = client.get(f'/api/players/{p["id"]}/neighbors').json()
    assert all(x["player"]["role"]==p["role"] for x in response["neighbors"])
    assert client.get('/api/players/0/neighbors').status_code==404
    assert client.get('/api/players/1/neighbors?limit=99999').status_code==422

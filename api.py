"""Optional local read-only API over the same derived research artifact as the UI."""
from functools import lru_cache
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pipeline.similarity import FEATURES, weighted_cosine, feature_weights

app = FastAPI(title="Touchline Research API", version="1.0.0", description="Historical research aggregates only. Not a production club service.")


@lru_cache(maxsize=1)
def dataset():
    path = Path(__file__).parent / "public/data/workspace.json"
    if not path.exists():
        raise HTTPException(503, "Run python -m pipeline.build before serving this API")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/health")
def health():
    d = dataset()
    return {"status":"ok", "version":d["version"], "scope":d["evidence"]["competition"]}


@app.get("/api/players")
def players(role: str | None = None, minimum_minutes: int = Query(180, ge=0, le=1500)):
    return [p for p in dataset()["players"] if p["minutes"] >= minimum_minutes and (role is None or p["role"] == role)]


@app.get("/api/players/{player_id}/neighbors")
def neighbors(player_id: int, minimum_minutes: int = Query(180, ge=0, le=1500), limit: int = Query(10, ge=1, le=50)):
    all_players = dataset()["players"]
    target = next((p for p in all_players if p["id"] == player_id), None)
    if target is None:
        raise HTTPException(404, "Player not present in this historical cohort")
    keys = [f["key"] for f in FEATURES]
    ranked = []
    for p in all_players:
        if p["id"] != player_id and p["role"] == target["role"] and p["minutes"] >= minimum_minutes:
            score = weighted_cosine([target["z"][k] for k in keys], [p["z"][k] for k in keys], feature_weights())
            if score is not None:
                ranked.append({"player":p, "cosine":score, "displaySimilarity":round(score*100,2)})
    ranked.sort(key=lambda p:(-p["cosine"],p["player"]["id"]))
    return {"reference":target["id"],"meaning":"Signed cosine x 100; style similarity, not quality or transfer-success probability", "neighbors":ranked[:limit]}


@app.get("/api/evidence")
def evidence():
    return dataset()["evidence"]

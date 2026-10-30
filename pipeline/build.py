from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from .events import event_profiles, fit_xt, load_competition, match_summaries

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"


def native(value):
    if isinstance(value, dict):
        return {str(k): native(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, np.ndarray)):
        return [native(v) for v in value]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if not np.isfinite(value):
            raise ValueError("Nonfinite numerical output cannot be published")
        return round(float(value), 8)
    return value


def source_analysis():
    # Only unpickle this project's own ignored local cache, never downloaded files.
    source_key = hashlib.sha256((ROOT / "data/source_manifest.json").read_bytes() + (ROOT / "pipeline/events.py").read_bytes()).hexdigest()
    cache = RAW / "event_analysis.pkl"
    if cache.exists():
        with cache.open("rb") as handle:
            saved = pickle.load(handle)
        if saved["key"] == source_key:
            print("Using locally generated, source-hashed analysis cache", flush=True)
            return saved
    bundles, count = load_competition(RAW)
    model, support, diagnostics = fit_xt(bundles)
    rows = event_profiles(bundles)
    matches = match_summaries(bundles)
    saved = {"key": source_key, "bundles": bundles, "event_count": count, "model": model,
             "support": support, "xt": diagnostics, "rows": rows, "matches": matches}
    with cache.open("wb") as handle:
        pickle.dump(saved, handle)
    return saved


def main(prepare=False):
    saved = source_analysis()
    if prepare:
        print(f"Prepared {saved['event_count']} original events; {len(saved['rows'])} player-match profiles", flush=True)
        return
    from .similarity import FEATURES, build_profiles
    from .tracking import build_tracking
    players, profile_diagnostics = build_profiles(saved["rows"], saved["xt"]["trainMatches"], saved["xt"]["testMatches"])
    dates = {int(b["game"]["game_id"]): pd.Timestamp(b["game"]["game_date"]) for b in saved["bundles"]}
    chronology = max(dates[i] for i in saved["xt"]["trainMatches"]) < min(dates[i] for i in saved["xt"]["testMatches"])
    if not chronology:
        raise RuntimeError("Training dates must strictly precede held-out dates")
    profile_diagnostics["split"]["chronologyVerified"] = True
    profile_diagnostics["split"]["scope"] = "Profiles describe train/test union; priors/scales use TRAIN only. Caller verified source match dates."
    tracking, tracking_meta = build_tracking(RAW)
    print(f"Built {len(players)} player profiles and {len(tracking)} publishable tracking samples", flush=True)
    checks = saved["xt"]["checks"] + [
        {"name":"Public event aggregation", "passed":all(a["count"]>=5 and a["playerId"]==0 for m in saved["matches"] for a in m["actions"]), "detail":"No raw StatsBomb event rows, UUIDs, exact pass coordinates, or event downloads are published."},
        {"name":"Unique player identities", "passed":len({p["id"] for p in players})==len(players), "detail":"Provider numeric IDs, not fuzzy name joins."},
        {"name":"Positive minute exposure", "passed":all(p["minutes"]>0 for p in players), "detail":"socceraction event-derived minutes include stoppage time; provider estimates are not official league minutes."},
        {"name":"Provider separation", "passed":all(t["source"]=="SkillCorner" for t in tracking), "detail":"Named-player event research and the separate historical tracking match are never joined."},
    ]
    checks.extend(tracking_meta.get("checks", []))
    evaluation = list(saved["xt"]["evaluation"])
    if isinstance(profile_diagnostics.get("evaluation"), list):
        evaluation.extend(profile_diagnostics["evaluation"])
    if isinstance(tracking_meta.get("evaluation"), list):
        evaluation.extend(tracking_meta["evaluation"])
    model = saved["model"]
    output = {
        "version":"1.0.0", "features":FEATURES, "players":players, "matches":saved["matches"], "tracking":tracking,
        "evidence":{
            "buildDate":"2026-10-29", "competition":"FIFA World Cup 2022 · historical public-data research",
            "events":saved["event_count"], "matches":len(saved["matches"]), "players":len(players),
            "trainMatches":saved["xt"]["trainMatches"], "testMatches":saved["xt"]["testMatches"],
            "xtGrid":model.xT.tolist(), "xtSupport":saved["support"].tolist(), "evaluation":evaluation, "checks":checks,
            "providers":[
                {"name":"StatsBomb", "scope":"64 World Cup 2022 matches; derived player, team, and cell-to-cell aggregates only.", "license":"Noncommercial research; attribution/logo required; raw redistribution prohibited.", "url":"https://github.com/hudl/open-data", "status":"Analyzed locally; aggregates published"},
                {"name":"SkillCorner", "scope":"Auckland FC vs Wellington Phoenix, 7 December 2024. Broadcast-derived, extrapolated tracking; centered 104 x 68 m.", "license":"MIT repository notice retained; source credited.", "url":"https://github.com/SkillCorner/opendata", "status":"Real tracking sample and modeled control surfaces"},
                {"name":"Metrica Sports", "scope":"Anonymized Sample Game 3; kloppy EPTS validation and model diagnostics only. No tracking positions redistributed.", "license":"Sample-use attribution; no blanket redistribution license assumed.", "url":"https://github.com/metrica-sports/sample-data", "status":"Local adapter validation; aggregate QA only"},
            ],
            "limitations":[
                "Historical tournament sample, not current MLS scouting data, a transfer forecast, or a recommendation to sign a player.",
                "Similarity describes measured style, not quality, replacement success, tactical fit, or player valuation. Team/opponent context remains a confounder.",
                "Successful-move xT does not fully debit failed moves, value defensive work, or measure total player contribution. Values depend on grid resolution and sparse cells.",
                "Per-90 rates use event-derived minutes including stoppage time. Low-minute profiles remain unstable despite shrinkage; match bootstrap intervals are descriptive, not future-performance guarantees.",
                "xT uses 48 chronological group-stage matches for fitting and 16 knockout matches for diagnostics. This tournament-stage shift is a limitation, not a randomized experiment.",
                "Pitch control is a simplified, uncalibrated two-dimensional arrival model. It is not a complete pass-success model or a substitute for video review; offside and aerial interception require separate treatment.",
                "Public StatsBomb displays contain derived aggregates only; raw events stay in the ignored local cache. Data terms are separate from the original code license.",
            ],
            "methodology":[
                "Source versions and SHA-256 hashes are recorded in data/source_manifest.json. No private club data or paid API access is used.",
                "socceraction converts provider events to SPADL and fits Karun Singh's expected-threat framework on training matches only, retaining failed-move transition mass.",
                "Role-specific metric profiles use explicit exposure shrinkage; a separate 60-bin pass/carry/pressure spatial fingerprint measures where actions occur. Feature weights are visible and adjustable.",
                "Same-player retrieval across train/held-out match windows is a style-stability proxy, not a measure of recruitment success.",
                "SkillCorner tracking and Metrica validation use provider-specific adapters and separate matches. Velocities must be smoothed at native sample rate before control surfaces are computed.",
            ],
            "profileDiagnostics":profile_diagnostics, "trackingDiagnostics":tracking_meta,
        },
    }
    output = native(output)
    if not all(x["passed"] for x in checks):
        raise RuntimeError("A release check failed: "+str([x for x in checks if not x["passed"]]))
    dest = ROOT / "public/data/workspace.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    (ROOT/"artifacts").mkdir(exist_ok=True)
    (ROOT/"artifacts/evidence.json").write_text(json.dumps(output["evidence"], ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    dbpath = ROOT / "data/processed/research.db"
    dbpath.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(dbpath) as conn:
        pd.DataFrame([{**r, "counts":json.dumps(r["counts"]), "style_counts":json.dumps(r["style_counts"])} for r in saved["rows"]]).to_sql("player_match", conn, if_exists="replace", index=False)
        pd.concat([b["actions"] for b in saved["bundles"]]).to_sql("spadl_actions", conn, if_exists="replace", index=False)
        pd.DataFrame([{k:v for k,v in p.items() if k not in ["metrics","z","style","matches","xtInterval"]} for p in players]).to_sql("player_summary", conn, if_exists="replace", index=False)
    print(json.dumps({"events":output["evidence"]["events"],"matches":len(output["matches"]),"players":len(players),"trackingFrames":sum(len(t["frames"]) for t in tracking),"publicBytes":dest.stat().st_size,"checks":len(checks)}, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-events", action="store_true")
    main(parser.parse_args().prepare_events)

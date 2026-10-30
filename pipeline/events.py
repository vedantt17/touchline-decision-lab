from __future__ import annotations

import json
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from socceraction.data.statsbomb import StatsBombLoader
from socceraction import spadl
from socceraction.spadl import config
from socceraction.xthreat import ExpectedThreat, get_successful_move_actions


ROLE_NAMES = {"Goalkeeper": "Goalkeeper", "Center Back": "Centre back", "Right Center Back": "Centre back", "Left Center Back": "Centre back",
              "Right Back": "Full back", "Left Back": "Full back", "Right Wing Back": "Full back", "Left Wing Back": "Full back",
              "Right Wing": "Wide forward", "Left Wing": "Wide forward", "Right Midfield": "Wide forward", "Left Midfield": "Wide forward",
              "Center Forward": "Striker", "Right Center Forward": "Striker", "Left Center Forward": "Striker", "Secondary Striker": "Striker"}


def role(name):
    return ROLE_NAMES.get(name, "Midfielder")


def cell(x, y, nx=16, ny=12):
    """SPADL bottom-left meters to library top-row-first grid indexes."""
    return (ny - 1 - min(ny - 1, max(0, int(y / 68 * ny))),
            min(nx - 1, max(0, int(x / 105 * nx))))


def native_xy(location):
    if not location or len(location) < 2:
        return None
    return np.clip(float(location[0]) / 120 * 105, 0, 105), np.clip(float(location[1]) / 80 * 68, 0, 68)


def possession_goals(raw):
    labels = defaultdict(int)
    for event in raw:
        if event.get("period", 0) > 4:
            continue
        pid = event.get("possession")
        if pid is None:
            continue
        labels[pid] = max(labels[pid], int(event.get("shot", {}).get("outcome", {}).get("name") == "Goal"))
    return labels


def load_competition(raw_dir):
    root = raw_dir / "statsbomb"
    loader = StatsBombLoader(getter="local", root=str(root))
    games = loader.games(43, 106).sort_values(["game_date", "game_id"])
    bundles = []
    event_count = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        warnings.simplefilter("ignore", UserWarning)
        for i, game in enumerate(games.to_dict("records")):
            game_id = int(game["game_id"])
            raw = json.loads((root / "events" / f"{game_id}.json").read_text(encoding="utf-8"))
            events = loader.events(game_id)
            events = events[events.period_id <= 4]
            players = loader.players(game_id)
            names = loader.teams(game_id).set_index("team_id").team_name.to_dict()
            actions = spadl.statsbomb.convert_to_actions(events, int(game["home_team_id"]), xy_fidelity_version=2, shot_fidelity_version=2)
            actions = spadl.play_left_to_right(actions, int(game["home_team_id"]))
            # Retain raw local action rows only in the ignored cache/database.
            bundles.append({"game": game, "raw": raw, "players": players, "names": names, "actions": actions})
            event_count += len(raw)
            if i % 8 == 0:
                print(f"Converted {i + 1}/{len(games)} matches with socceraction", flush=True)
    return bundles, event_count


def fit_xt(bundles):
    train_ids = [int(b["game"]["game_id"]) for b in bundles[:48]]
    test_ids = [int(b["game"]["game_id"]) for b in bundles[48:]]
    train = pd.concat([b["actions"] for b in bundles[:48]], ignore_index=True)
    model = ExpectedThreat(l=16, w=12, eps=1e-5)
    model.fit(train)
    coarse = ExpectedThreat(l=8, w=6, eps=1e-5)
    coarse.fit(train)
    support = np.zeros((12, 16), dtype=int)
    for a in train.itertuples():
        support[cell(a.start_x, a.start_y)] += 1
    train_possessions = [v for b in bundles[:48] for v in possession_goals(b["raw"]).values()]
    baseline = float(np.mean(train_possessions))
    truth, predicted, coarse_values = [], [], []
    for bundle in bundles:
        actions = bundle["actions"]
        bundle["rated"] = model.rate(actions)
        labels = possession_goals(bundle["raw"])
        source = {e["id"]: e for e in bundle["raw"] if e.get("period", 0) <= 4}
        if int(bundle["game"]["game_id"]) in test_ids:
            for a in get_successful_move_actions(actions).itertuples():
                event = source.get(a.original_event_id)
                if event and event.get("possession") in labels:
                    truth.append(labels[event["possession"]])
                    predicted.append(model.xT[cell(a.start_x, a.start_y)])
                    coarse_values.append(coarse.xT[cell(a.start_x, a.start_y, 8, 6)])
    y, p, c = np.array(truth), np.array(predicted), np.array(coarse_values)
    residual = model.xT - (model.shot_prob_matrix * model.scoring_prob_matrix +
                           model.move_prob_matrix * model.transition_matrix.dot(model.xT.ravel()).reshape(12, 16))
    diagnostics = {
        "trainMatches": train_ids, "testMatches": test_ids,
        "evaluation": [
            {"name": "Held-out move starts", "value": len(y), "detail": "16 knockout matches, not used to fit xT; repeated actions share possession labels."},
            {"name": "xT Brier score", "value": round(float(np.mean((p-y)**2)), 6), "detail": "Eventual possession-goal proxy at successful move starts; descriptive check, not calibrated match prediction."},
            {"name": "Constant baseline Brier", "value": round(float(np.mean((baseline-y)**2)), 6), "detail": "Training possession-goal prevalence applied to held-out move starts; lower is better."},
            {"name": "Coarse-grid Brier", "value": round(float(np.mean((c-y)**2)), 6), "detail": "8 x 6 grid fitted to the same training matches; grid-resolution sensitivity, not test-selected tuning."},
            {"name": "Bellman max residual", "value": round(float(np.max(np.abs(residual))), 9), "detail": "Numerical fixed-point residual; not model accuracy."},
            {"name": "Training source actions", "value": len(train), "detail": "SPADL conversion includes inferred dribbles; shootouts excluded."},
        ],
        "checks": [
            {"name": "No match overlap", "passed": not set(train_ids) & set(test_ids), "detail": "48 chronological training matches; 16 held-out knockout matches."},
            {"name": "Transition mass", "passed": bool(np.max(model.transition_matrix.sum(axis=1)) <= 1 + 1e-10), "detail": "Failed moves retain missing transition mass; rows are not forced to sum to one."},
            {"name": "Bounded xT", "passed": bool(np.isfinite(model.xT).all() and model.xT.min() >= 0 and model.xT.max() <= 1), "detail": "All state values finite and in [0, 1]."},
            {"name": "Converged value iteration", "passed": bool(np.max(np.abs(residual)) < 2e-5), "detail": "Bellman residual below 0.00002."},
            {"name": "Coordinate bounds", "passed": bool(all(b["actions"][["start_x", "end_x"]].ge(0).all().all() and b["actions"][["start_x", "end_x"]].le(105).all().all() and b["actions"][["start_y", "end_y"]].ge(0).all().all() and b["actions"][["start_y", "end_y"]].le(68).all().all() for b in bundles)), "detail": "Provider coordinates converted by socceraction; each team attacks left to right."},
        ],
    }
    return model, support, diagnostics


def event_profiles(bundles):
    rows = []
    for bundle in bundles:
        game = bundle["game"]
        game_id = int(game["game_id"])
        raw = [e for e in bundle["raw"] if e.get("period", 0) <= 4]
        by_player = defaultdict(list)
        for e in raw:
            if e.get("player", {}).get("id"):
                by_player[e["player"]["id"]].append(e)
        action_xt = defaultdict(float)
        action_moves = Counter()
        for a, value in zip(bundle["actions"].itertuples(), bundle["rated"]):
            if np.isfinite(value):
                action_xt[int(a.player_id)] += float(value)
                action_moves[int(a.player_id)] += 1
        for player in bundle["players"].to_dict("records"):
            player_id = int(player["player_id"])
            events = by_player.get(player_id, [])
            position_counts = Counter(e.get("position", {}).get("name") for e in events if e.get("position"))
            position = position_counts.most_common(1)[0][0] if position_counts else player["starting_position_name"]
            minutes = float(player["minutes_played"])
            if minutes <= 0 or not np.isfinite(minutes):
                continue
            counts = dict.fromkeys(["xt", "progressive_passes", "progressive_carries", "key_passes", "box_entries", "pressures", "defense", "shots", "npxg", "passes", "completed_passes", "moves"], 0.)
            counts["xt"], counts["moves"] = action_xt[player_id], action_moves[player_id]
            style = np.zeros(60)
            for event in events:
                kind = event["type"]["name"]
                xy = native_xy(event.get("location"))
                if xy and kind in ["Pass", "Carry", "Pressure"]:
                    channel = ["Pass", "Carry", "Pressure"].index(kind)
                    xbin, ybin = min(4, int(xy[0]/105*5)), min(3, int(xy[1]/68*4))
                    style[channel*20+ybin*5+xbin] += 1
                if kind in ["Pass", "Carry"]:
                    payload = event[kind.lower()]
                    end = native_xy(payload.get("end_location"))
                    successful = kind == "Carry" or "outcome" not in payload
                    if kind == "Pass":
                        counts["passes"] += 1
                        counts["completed_passes"] += int(successful)
                        counts["key_passes"] += int(payload.get("shot_assist", False))
                    if xy and end and successful:
                        progressive = end[0]-xy[0] >= 10 and end[0] >= 52.5
                        counts["progressive_passes" if kind == "Pass" else "progressive_carries"] += int(progressive)
                        in_box = lambda p: p[0] >= 88.5 and abs(p[1]-34) <= 20.16
                        counts["box_entries"] += int(in_box(end) and not in_box(xy))
                if kind == "Pressure":
                    counts["pressures"] += 1
                if kind == "Interception" or (kind == "Duel" and event.get("duel", {}).get("type", {}).get("name") == "Tackle"):
                    counts["defense"] += 1
                if kind == "Shot" and event.get("shot", {}).get("type", {}).get("name") != "Penalty":
                    counts["shots"] += 1
                    counts["npxg"] += event.get("shot", {}).get("statsbomb_xg", 0.)
            rows.append({"id": player_id, "name": player.get("nickname") or player["player_name"],
                         "team": bundle["names"][player["team_id"]], "role": role(position), "position": position,
                         "minutes": minutes, "matchid": game_id, "counts": counts, "style_counts": style.tolist()})
    return rows


def match_summaries(bundles):
    result = []
    for bundle in bundles:
        game = bundle["game"]
        game_id = int(game["game_id"])
        actions = bundle["actions"].copy()
        actions["xt"] = bundle["rated"]
        # Publish sufficiently supported cell-to-cell aggregates, never source event records.
        moves = actions[np.isfinite(actions.xt)].copy()
        groups = defaultdict(list)
        for a in moves.itertuples():
            kind = "carry" if config.actiontypes[int(a.type_id)] == "dribble" else "pass"
            sx, sy = min(5,int(a.start_x/105*6)), min(3,int((68-a.start_y)/68*4))
            ex, ey = min(5,int(a.end_x/105*6)), min(3,int((68-a.end_y)/68*4))
            minute = float(a.time_seconds/60 + {1:0,2:45,3:90,4:105}.get(a.period_id,0))
            groups[(int(a.team_id),kind,sx,sy,ex,ey,int(minute//15)*15)].append(float(a.xt))
        lanes = []
        for key, values in groups.items():
            tid,kind,sx,sy,ex,ey,minute = key
            if len(values) < 5:
                continue
            lanes.append({"id": "lane-"+"-".join(map(str,key)), "player": "Team aggregate", "playerId": 0,
                          "team": bundle["names"][tid], "minute":minute, "period":1 if minute<45 else 2 if minute<90 else 3 if minute<105 else 4,
                          "type":kind, "start":[(sx+.5)*105/6,(sy+.5)*68/4], "end":[(ex+.5)*105/6,(ey+.5)*68/4],
                          "xt":round(sum(values),6), "success":True, "count":len(values)})
        team_stats = []
        for tid, name in bundle["names"].items():
            raw = [e for e in bundle["raw"] if e.get("team",{}).get("id")==tid and e.get("period",0)<=4]
            shots = [e for e in raw if e["type"]["name"]=="Shot"]
            passes = [e for e in raw if e["type"]["name"]=="Pass"]
            team_moves = moves[moves.team_id==tid]
            lanes_xt = [float(team_moves.loc[(team_moves.start_y>=68/3*i)&(team_moves.start_y<68/3*(i+1)),"xt"].sum()) for i in range(3)]
            team_stats.append({"team":name,"shots":len(shots),"xg":round(sum(e["shot"].get("statsbomb_xg",0) for e in shots),3),
                               "xt":round(float(team_moves.xt.sum()),4),"passes":len(passes),"completions":sum("outcome" not in e["pass"] for e in passes),
                               "left":round(lanes_xt[2],4),"center":round(lanes_xt[1],4),"right":round(lanes_xt[0],4)})
        result.append({"id":game_id,"date":str(game["game_date"].date()),"home":bundle["names"][game["home_team_id"]],
                       "away":bundle["names"][game["away_team_id"]],"score":f"{game['home_score']}-{game['away_score']}",
                       "stage":game["competition_stage"],"actions":sorted(lanes,key=lambda a:a["xt"],reverse=True),"teamStats":team_stats})
    return result

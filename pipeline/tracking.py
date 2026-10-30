"""Bounded real-tracking demonstration; no raw Metrica positions are returned."""
from __future__ import annotations

import csv
import importlib.util
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
GRID = (16, 10)
KEYFRAME_TIMES = tuple(3.0 + 0.5 * i for i in range(20))
MAX_SKILLCORNER_LINES = 4000
MAX_METRICA_FRAMES = 5000
MAX_METRICA_SCAN = 200000
MAX_OBSERVED_SPEED = 12.0


def _reference():
    path = ROOT / "vendor" / "Metrica_PitchControl.py"
    license_paths = (path.with_name("LAURIE_LICENSE"), path.with_name("LICENSE"))
    if not path.is_file() or not any(p.is_file() for p in license_paths):
        raise FileNotFoundError("Fetch vendor/Metrica_PitchControl.py and its MIT license first")
    spec = importlib.util.spec_from_file_location("touchline_pitchcontrol_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seconds(timestamp):
    if isinstance(timestamp, (int, float)):
        return float(timestamp)
    h, m, s = str(timestamp).split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _finite_pair(x, y):
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y))


def _velocities(frames, fps):
    """Differentiate at native rate, smoothing only within contiguous valid tracks."""
    tracks = {}
    for frame in frames:
        for player in frame["players"]:
            player.update(vx=0.0, vy=0.0, _velocity_valid=False)
            tracks.setdefault(player["id"], []).append((frame, player))
    segment_count = 0
    valid_count = 0

    def finish(segment):
        nonlocal segment_count, valid_count
        segment_count += 1
        if len(segment) < 2:
            return
        times = np.array([f["t"] for f, _ in segment])
        positions = np.array([[p["x"], p["y"]] for _, p in segment])
        derivatives = np.gradient(positions, times, axis=0)
        for i, (_, player) in enumerate(segment):
            smooth = derivatives[max(0, i - 2): min(len(segment), i + 3)].mean(axis=0)
            if np.linalg.norm(smooth) <= MAX_OBSERVED_SPEED:
                player.update(vx=float(smooth[0]), vy=float(smooth[1]), _velocity_valid=True)
                valid_count += 1

    for track in tracks.values():
        segment = []
        for frame, player in track:
            if segment:
                previous, previous_player = segment[-1]
                dt = frame["t"] - previous["t"]
                displacement = math.hypot(player["x"] - previous_player["x"],
                                          player["y"] - previous_player["y"])
                contiguous = (frame["period"] == previous["period"]
                              and abs(dt - 1.0 / fps) < 1e-4
                              and player.get("detected") == previous_player.get("detected")
                              and displacement <= MAX_OBSERVED_SPEED * dt)
                if not contiguous:
                    finish(segment)
                    segment = []
            segment.append((frame, player))
        finish(segment)
    return {"velocitySegments": segment_count, "validVelocitySamples": valid_count,
            "zeroVelocityFallbackSamples": sum(len(t) for t in tracks.values()) - valid_count}


def _skillcorner(rawdir):
    meta = json.loads((rawdir / "skillcorner_match.json").read_text(encoding="utf-8"))
    if meta.get("id") != 1899585:
        raise ValueError("This bounded demonstration requires SkillCorner match 1899585")
    pitch = (float(meta["pitch_length"]), float(meta["pitch_width"]))
    if pitch != (104.0, 68.0):
        raise ValueError("Unexpected pitch dimensions for SkillCorner match 1899585")
    teams = {meta["home_team"]["id"]: "Home", meta["away_team"]["id"]: "Away"}
    players = {p["id"]: p for p in meta["players"]}
    goalkeepers = {}
    for p in meta["players"]:
        if "goalkeeper" in p.get("player_role", {}).get("name", "").lower():
            goalkeepers.setdefault(teams.get(p["team_id"]), str(p["id"]))
    with (rawdir / "skillcorner_phases.csv").open(newline="", encoding="utf-8-sig") as source:
        phases = [r for r in csv.DictReader(source) if int(r["period"]) == 1]
    if not phases:
        raise ValueError("No first-period in-play phase supplied")
    phase = min(phases, key=lambda row: int(row["frame_start"]))
    if int(phase["match_id"]) != meta["id"]:
        raise ValueError("Phase/tracking match identity mismatch")
    start, end = int(phase["frame_start"]), int(phase["frame_end"])
    quality = {"inputFramesRead": 0, "nullPeriodFrames": 0, "invalidPlayerCoordinates": 0,
               "unknownPlayerIds": 0, "duplicatePlayerIds": 0, "nonmonotonicFrames": 0,
               "playerSamples": 0, "detectedPlayerSamples": 0, "missingBallFrames": 0,
               "phaseStartFrame": start, "phaseEndFrame": end}
    frames = []
    last_frame = -1
    with (rawdir / "skillcorner_tracking.jsonl").open(encoding="utf-8-sig") as source:
        for line_number, line in enumerate(source):
            if line_number >= MAX_SKILLCORNER_LINES:
                raise ValueError("SkillCorner prefix exceeds the bounded 4000-line scan")
            if not line.strip():
                continue
            row = json.loads(line)
            quality["inputFramesRead"] += 1
            if row["frame"] <= last_frame:
                quality["nonmonotonicFrames"] += 1
            last_frame = row["frame"]
            if row.get("period") is None or row.get("timestamp") is None:
                quality["nullPeriodFrames"] += 1
                continue
            if row["period"] != 1 or _seconds(row["timestamp"]) > 300:
                break
            if not start - 5 <= row["frame"] <= end + 5:
                continue
            active = []
            seen = set()
            for p in row["player_data"]:
                identity = p["player_id"]
                if identity in seen:
                    quality["duplicatePlayerIds"] += 1
                    continue
                seen.add(identity)
                info = players.get(identity)
                if info is None or info["team_id"] not in teams:
                    quality["unknownPlayerIds"] += 1
                    continue
                if not _finite_pair(p.get("x"), p.get("y")):
                    quality["invalidPlayerCoordinates"] += 1
                    continue
                active.append({"id": str(identity), "team": teams[info["team_id"]],
                               "number": str(info.get("number", "")), "x": float(p["x"]),
                               "y": float(p["y"]), "detected": p.get("is_detected") is True})
            ball = row.get("ball_data") or {}
            ball_xy = [float(ball["x"]), float(ball["y"])] if _finite_pair(ball.get("x"), ball.get("y")) else None
            quality["playerSamples"] += len(active)
            quality["detectedPlayerSamples"] += sum(p["detected"] for p in active)
            quality["missingBallFrames"] += int(ball_xy is None)
            frames.append({"t": _seconds(row["timestamp"]), "period": 1, "_frame": row["frame"],
                           "players": active, "ball": ball_xy, "_in_play": start <= row["frame"] <= end})
    if quality["nonmonotonicFrames"] or quality["unknownPlayerIds"] or quality["duplicatePlayerIds"]:
        raise ValueError("SkillCorner identity/order checks failed: " + str(quality))
    quality.update(_velocities(frames, 10))
    quality["nativePhaseContextFrames"] = len(frames)
    return frames, meta, pitch, goalkeepers, quality


def _control(frame, pitch, reference, goalkeepers, params=None, grid=GRID):
    """Use both reference probabilities; never normalize away integration residuals."""
    params = dict(params or reference.default_model_params())
    rows = {"Home": {}, "Away": {}}
    for player in frame["players"]:
        prefix = f"{player['team']}_{player['id']}_"
        rows[player["team"]].update({prefix + key: player[key] for key in ("x", "y", "vx", "vy")})
    home = reference.initialise_players(rows["Home"], "Home", params, goalkeepers.get("Home"))
    away = reference.initialise_players(rows["Away"], "Away", params, goalkeepers.get("Away"))
    if not home or not away:
        raise ValueError("Pitch control requires players from both teams")
    nx, ny = grid
    xgrid = (np.arange(nx) + 0.5) * pitch[0] / nx - pitch[0] / 2
    ygrid = (np.arange(ny) + 0.5) * pitch[1] / ny - pitch[1] / 2
    home_control, away_control = np.zeros((ny, nx)), np.zeros((ny, nx))
    # Home is always the first control population, not the current possession team.
    # No check_offsides call: every active player participates explicitly.
    for iy, y in enumerate(ygrid):
        for ix, x in enumerate(xgrid):
            ph, pa = reference.calculate_pitch_control_at_target(
                np.array([x, y]), home, away,
                None if frame["ball"] is None else np.array(frame["ball"]), params)
            home_control[iy, ix], away_control[iy, ix] = float(ph), float(pa)
    if not (np.isfinite(home_control).all() and np.isfinite(away_control).all()
            and np.all((home_control >= 0) & (home_control <= 1))
            and np.all((away_control >= 0) & (away_control <= 1))):
        raise ValueError("Reference pitch-control probabilities are outside [0, 1]")
    mass_error = float(np.max(np.abs(1 - home_control - away_control)))
    if mass_error > params["model_converge_tol"] + 1e-9:
        raise ValueError(f"Reference pitch-control integration did not conserve mass: {mass_error}")
    return home_control, away_control, mass_error


def _sensitivity(frame, pitch, reference, goalkeepers, baseline):
    variants = []
    for reaction in (0.5, 0.9):
        params = reference.default_model_params()
        params["reaction_time"] = reaction
        surface, _, error = _control(frame, pitch, reference, goalkeepers, params)
        delta = np.abs(surface - baseline)
        variants.append({"reactionTimeSeconds": reaction, "meanAbsoluteChange": float(delta.mean()),
                         "maxAbsoluteChange": float(delta.max()),
                         "meanHomeControl": float(surface.mean()), "massError": error})
    return {"referenceTimeSeconds": frame["t"], "baselineReactionTimeSeconds": 0.7,
            "interpretation": "Parameter sensitivity only; not accuracy or calibration evidence",
            "variants": variants}


def _xml_text(root, name):
    return next((node.text for node in root.iter() if node.tag.split("}")[-1] == name), None)


def _metrica(rawdir, reference):
    paths = (rawdir / "metrica_metadata.xml", rawdir / "metrica_tracking.txt")
    if not all(p.is_file() for p in paths):
        return {"status": "unavailable", "reason": "Metrica source files not supplied", "positionsPublished": False}
    try:
        from kloppy import metrica
    except ImportError:
        return {"status": "unavailable", "reason": "kloppy is not installed", "positionsPublished": False}
    xml = ET.parse(paths[0]).getroot()
    fps = float(_xml_text(xml, "FrameRate"))
    field = next(n for n in xml.iter() if n.tag.split("}")[-1] == "FieldSize")
    pitch = (float(_xml_text(field, "Width")), float(_xml_text(field, "Height")))
    half_ends = []
    for parameter in xml.iter():
        if parameter.tag.split("}")[-1] == "ProviderParameter":
            name, value = _xml_text(parameter, "Name"), _xml_text(parameter, "Value")
            if name and name.endswith("half_end") and value:
                half_ends.append(int(value))
    expected_frames = max(half_ends, default=0)
    available = 0
    monotonic = True
    previous_id = 0
    with paths[1].open(encoding="utf-8-sig") as source:
        for line in source:
            if not line.strip():
                continue
            if available >= MAX_METRICA_SCAN:
                raise ValueError("Metrica raw input exceeds the bounded frame scan")
            frame_id = int(line.split(":", 1)[0])
            monotonic = monotonic and frame_id == previous_id + 1
            previous_id = frame_id
            available += 1
    dataset = metrica.load_tracking_epts(meta_data=str(paths[0]), raw_data=str(paths[1]),
                                         limit=MAX_METRICA_FRAMES, coordinates="metrica")
    teams = {team.team_id: ("Home" if str(team.ground) == "home" else "Away")
             for team in dataset.metadata.teams}
    frames = []
    invalid_coordinates = 0
    unpositioned_roster_entries = 0
    finite_player_samples = 0
    missing_players = 0
    missing_ball = 0
    native_outside_pitch = 0
    goalkeepers = {}
    for frame in dataset.records:
        active = []
        for player, data in frame.players_data.items():
            point = data.coordinates
            if point is None:
                unpositioned_roster_entries += 1
                continue
            if not _finite_pair(point.x, point.y):
                invalid_coordinates += 1
                continue
            finite_player_samples += 1
            native_outside_pitch += int(not (0 <= point.x <= 1 and 0 <= point.y <= 1))
            identity = str(player.player_id)
            team = teams[player.team.team_id]
            number = str(player.jersey_no or "")
            role = str(getattr(player, "starting_position", "")).lower()
            if "goal" in role or "keeper" in role:
                goalkeepers.setdefault(team, identity)
            active.append({"id": identity, "team": team, "number": number,
                           "x": (float(point.x) - 0.5) * pitch[0],
                           "y": (0.5 - float(point.y)) * pitch[1]})
        missing_players += max(0, 22 - len(active))
        point = frame.ball_coordinates
        ball = ([(float(point.x) - 0.5) * pitch[0], (0.5 - float(point.y)) * pitch[1]]
                if point is not None and _finite_pair(point.x, point.y) else None)
        missing_ball += int(ball is None)
        timestamp = frame.timestamp
        t = timestamp.total_seconds() if hasattr(timestamp, "total_seconds") else float(timestamp)
        frames.append({"t": t, "period": frame.period.id, "_frame": frame.frame_id,
                       "players": active, "ball": ball})
    velocity_quality = _velocities(frames, fps)
    summary = {"status": "validated", "source": "Metrica Sports Sample Game 3",
               "positionsPublished": False, "parser": "kloppy.metrica.load_tracking_epts",
               "fps": fps, "pitch": list(pitch), "availableRawFrames": available,
               "expectedFullMatchFrames": expected_frames, "loadedFrames": len(frames),
               "prefixOnly": available < expected_frames, "consecutiveRawFrames": monotonic,
               "loadedCountMatchesLimit": len(frames) == min(available, MAX_METRICA_FRAMES),
               "invalidPlayerCoordinates": invalid_coordinates,
               "unpositionedRosterEntries": unpositioned_roster_entries,
               "finitePlayerSamples": finite_player_samples, "missingPlayerSlots": missing_players,
               "missingBallFrames": missing_ball, "outsidePitchPlayerSamples": native_outside_pitch,
               "comparisonCaveat": "Different anonymized match; not paired validation or accuracy measurement",
               **velocity_quality}
    if not monotonic or not summary["loadedCountMatchesLimit"]:
        raise ValueError("Metrica frame-count/order validation failed")
    # Prefer a complete, ball-observed frame with established native-rate velocities.
    candidates = [f for f in frames if f["t"] >= 3 and f["ball"] is not None
                  and len(f["players"]) == 22 and all(p["_velocity_valid"] for p in f["players"])]
    if candidates:
        frame = min(candidates, key=lambda f: abs(f["t"] - 10))
        home, away, error = _control(frame, pitch, reference, goalkeepers)
        summary["controlSummary"] = {"timeSeconds": frame["t"], "grid": list(GRID),
                                     "meanHomeControl": float(home.mean()),
                                     "meanAwayControl": float(away.mean()), "massError": error,
                                     "goalkeepersIdentified": len(goalkeepers)}
    else:
        summary["controlSummaryUnavailable"] = "No complete frame with ball and valid native velocities"
    return summary


def build_tracking(rawdir: Path) -> tuple[list[dict], dict]:
    """Return public SkillCorner keyframes and separate aggregate QA metadata."""
    rawdir = Path(rawdir)
    reference = _reference()
    native, meta, pitch, goalkeepers, quality = _skillcorner(rawdir)
    selected = []
    for t in KEYFRAME_TIMES:
        candidates = [f for f in native if f["_in_play"] and abs(f["t"] - t) < 1e-4]
        if len(candidates) != 1:
            raise ValueError(f"Missing unique in-play SkillCorner keyframe at t={t}")
        frame = candidates[0]
        if (frame["ball"] is None or len(frame["players"]) != 22
                or any(sum(p["team"] == team for p in frame["players"]) != 11 for team in ("Home", "Away"))):
            raise ValueError(f"Incomplete SkillCorner keyframe at t={t}")
        selected.append(frame)
    surfaces = []
    output = []
    for frame in selected:
        home, _, error = _control(frame, pitch, reference, goalkeepers)
        surfaces.append(home)
        output.append({"t": frame["t"], "players": [{k: v for k, v in p.items() if not k.startswith("_")}
                                                    for p in frame["players"]],
                       "ball": frame["ball"], "control": home.tolist(), "massError": error})
    sensitivity = _sensitivity(selected[10], pitch, reference, goalkeepers, surfaces[10])
    quality.update({"keyframes": len(output), "nativeFps": 10, "outputFps": 2,
                    "gridColumns": GRID[0], "gridRows": GRID[1],
                    "maxMassError": max(f["massError"] for f in output),
                    "outputPlayerSamples": sum(len(f["players"]) for f in output),
                    "outputDetectedPlayerSamples": sum(p["detected"] for f in output for p in f["players"]),
                    "keyframeZeroVelocityFallbacks": sum(not p["_velocity_valid"] for f in selected for p in f["players"]),
                    "goalkeepersIdentified": len(goalkeepers), "coordinates": "centered meters; x/y increasing with grid columns/rows",
                    "surface": "Home control, not team-in-possession control", "offsides": "disabled",
                    "maxReactionSensitivity": max(v["maxAbsoluteChange"] for v in sensitivity["variants"])})
    assumptions = ["Laurie Shaw / Friends of Tracking reference pitch-control implementation; uncalibrated defaults",
                   "Offside filtering explicitly disabled; Home is always the first model population",
                   "Native 10 Hz velocities: finite differences and centered five-sample smoothing within continuous tracks",
                   "Do not differentiate across missing frames, detection transitions, periods, or >12 m/s jumps; unavailable velocity falls back to zero",
                   "Broadcast tracking includes extrapolated off-screen positions; detected flags are preserved",
                   "16 x 10 cell-center grid in centered pitch meters; rows increase with y, columns with x",
                   "A 9.5-second first-phase excerpt is not match-level evidence or a calibrated football forecast"]
    tracking = {"source": "SkillCorner", "dataset": "1899585", "label": "Auckland FC v Wellington Phoenix | 7 Dec 2024 | first in-play phase",
                "fps": 2, "pitch": list(pitch), "frames": output,
                "model": "LaurieOnTracking Spearman-style pitch control (reference implementation)",
                "assumptions": assumptions, "home": meta["home_team"]["name"],
                "away": meta["away_team"]["name"], "quality": quality}
    metrica = _metrica(rawdir, reference)
    checks = [{"name": "Tracking probability bounds", "passed": True,
               "detail": "Both reference team probabilities finite and within [0,1] at every evaluated cell"},
              {"name": "Tracking probability mass", "passed": quality["maxMassError"] <= 0.01 + 1e-9,
               "detail": f"Maximum per-cell |1-home-away|={quality['maxMassError']:.8f}; no renormalization"},
              {"name": "Tracking native identities and in-play keyframes", "passed": True,
               "detail": "20 unique first-phase keyframes, 22 players each; joined metadata player id to team id"},
              {"name": "Metrica aggregate-only validation", "passed": metrica["status"] == "validated",
               "detail": str(metrica.get("reason", f"Loaded {metrica.get('loadedFrames', 0)} native frames; no raw positions published"))}]
    return [tracking], {"checks": checks, "skillcorner": quality, "sensitivity": sensitivity,
                        "metrica": metrica, "methodology": assumptions,
                        "limitations": ["Separate providers describe different matches and must not be synchronized",
                                        "Numerical convergence and sensitivity are not accuracy or calibration measurements",
                                        "Metrica source positions and trajectories are excluded from all returned public objects"]}

"""Synthetic numerical/adapter tests plus optional ignored-source integration checks."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from pipeline import tracking


def native_frame(t, x, *, detected=True, period=1):
    return {"t": t, "period": period, "players": [
        {"id": "1", "team": "Home", "number": "1", "x": x, "y": 2.0, "detected": detected}]}


def two_team_frame():
    return {"t": 3.0, "period": 1, "ball": [0.0, 0.0], "players": [
        {"id": "1", "team": "Home", "number": "1", "x": -10., "y": 0., "vx": 0., "vy": 0.},
        {"id": "2", "team": "Away", "number": "1", "x": 10., "y": 0., "vx": 0., "vy": 0.}]}


@pytest.fixture
def reference():
    try:
        return tracking._reference()
    except FileNotFoundError:
        pytest.skip("Official MIT vendor reference has not been fetched")


def test_native_constant_velocity_before_subsampling():
    frames = [native_frame(i / 10, i * 0.2) for i in range(20)]
    report = tracking._velocities(frames, 10)
    assert report["validVelocitySamples"] == 20
    assert all(p["vx"] == pytest.approx(2.0) and p["vy"] == pytest.approx(0.0)
               for f in frames for p in f["players"])


@pytest.mark.parametrize("last", [native_frame(0.4, 20.0), native_frame(0.2, 20.0),
                                   native_frame(0.2, 20.0, detected=False),
                                   native_frame(0.2, 20.0, period=2)])
def test_velocity_does_not_bridge_gaps_jumps_detection_or_period(last):
    frames = [native_frame(0, 0), native_frame(0.1, 0.2), last]
    report = tracking._velocities(frames, 10)
    assert frames[0]["players"][0]["vx"] == pytest.approx(2)
    assert frames[1]["players"][0]["vx"] == pytest.approx(2)
    assert not frames[2]["players"][0]["_velocity_valid"]
    assert report["zeroVelocityFallbackSamples"] == 1


def test_detection_change_breaks_even_a_plausible_track():
    frames = [native_frame(0, 0), native_frame(.1, .2), native_frame(.2, .4, detected=False)]
    tracking._velocities(frames, 10)
    assert not frames[-1]["players"][0]["_velocity_valid"]


def test_reference_probability_bounds_and_per_cell_mass(reference):
    home, away, error = tracking._control(two_team_frame(), (104., 68.), reference,
                                            {"Home": "1", "Away": "2"})
    assert home.shape == away.shape == (10, 16)
    assert np.all((home >= 0) & (home <= 1))
    assert np.all((away >= 0) & (away <= 1))
    assert np.max(np.abs(1 - home - away)) == pytest.approx(error)
    assert error <= .01
    assert home[:, :4].mean() > home[:, -4:].mean()


def test_cellwise_mass_failure_not_hidden_by_mean_or_normalization():
    ref = SimpleNamespace(default_model_params=lambda: {"model_converge_tol": .01},
                          initialise_players=lambda *args: [object()],
                          calculate_pitch_control_at_target=lambda *args: (.4, .4))
    with pytest.raises(ValueError, match="conserve mass"):
        tracking._control(two_team_frame(), (104., 68.), ref, {})


@pytest.mark.parametrize("probability", [float("nan"), -0.1, 1.1])
def test_invalid_reference_probabilities_fail(probability):
    ref = SimpleNamespace(default_model_params=lambda: {"model_converge_tol": .01},
                          initialise_players=lambda *args: [object()],
                          calculate_pitch_control_at_target=lambda *args: (probability, .5))
    with pytest.raises(ValueError, match="outside"):
        tracking._control(two_team_frame(), (104., 68.), ref, {})


def test_parameter_sensitivity_is_variation_not_accuracy(reference):
    frame = two_team_frame()
    frame["players"][0]["vx"] = 2.0
    base, _, _ = tracking._control(frame, (104., 68.), reference, {})
    summary = tracking._sensitivity(frame, (104., 68.), reference, {}, base)
    assert [v["reactionTimeSeconds"] for v in summary["variants"]] == [.5, .9]
    assert all(0 <= v["meanAbsoluteChange"] <= v["maxAbsoluteChange"] <= 1
               for v in summary["variants"])
    assert "not accuracy" in summary["interpretation"]


@pytest.fixture
def tiny_source(tmp_path):
    meta = {"id": 1899585, "pitch_length": 104, "pitch_width": 68,
            "home_team": {"id": 100, "name": "Synthetic Home"},
            "away_team": {"id": 200, "name": "Synthetic Away"},
            "players": [{"id": 1, "trackable_object": 999, "team_id": 100, "number": 1,
                         "player_role": {"name": "Goalkeeper"}},
                        {"id": 2, "trackable_object": 888, "team_id": 200, "number": 1,
                         "player_role": {"name": "Goalkeeper"}}]}
    (tmp_path / "skillcorner_match.json").write_text(json.dumps(meta))
    (tmp_path / "skillcorner_phases.csv").write_text(
        "match_id,period,frame_start,frame_end\n1899585,1,11,201\n")
    frames = [{"frame": 10 + i, "period": 1, "timestamp": f"00:00:{i / 10:05.2f}",
               "ball_data": {"x": 0, "y": 0}, "player_data": [
                   {"player_id": 1, "x": -40 + i * .01, "y": 0, "is_detected": False},
                   {"player_id": 2, "x": 40, "y": 0, "is_detected": True}]} for i in range(200)]
    (tmp_path / "skillcorner_tracking.jsonl").write_text("\n".join(map(json.dumps, frames)))
    return tmp_path


def test_source_joins_player_id_not_trackable_object_and_preserves_flags(tiny_source):
    frames, _, pitch, keepers, quality = tracking._skillcorner(tiny_source)
    assert pitch == (104., 68.)
    assert keepers == {"Home": "1", "Away": "2"}
    assert quality["unknownPlayerIds"] == 0
    assert frames[0]["players"][0]["detected"] is False
    assert frames[0]["players"][1]["detected"] is True
    assert frames[0]["players"][0]["x"] < 0
    assert len([f for f in frames if f["_in_play"]]) == 191


def test_wrong_match_rejected(tiny_source):
    path = tiny_source / "skillcorner_match.json"
    meta = json.loads(path.read_text())
    meta["id"] = 123
    path.write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="1899585"):
        tracking._skillcorner(tiny_source)


def test_trackable_object_cannot_substitute_for_player_id(tiny_source):
    path = tiny_source / "skillcorner_tracking.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["player_data"][0]["player_id"] = 999
    path.write_text("\n".join(map(json.dumps, rows)))
    with pytest.raises(ValueError, match="identity/order"):
        tracking._skillcorner(tiny_source)


def test_phase_from_different_match_is_rejected(tiny_source):
    (tiny_source / "skillcorner_phases.csv").write_text(
        "match_id,period,frame_start,frame_end\n123,1,11,201\n")
    with pytest.raises(ValueError, match="identity mismatch"):
        tracking._skillcorner(tiny_source)


def test_missing_requested_keyframe_fails_without_synthesizing(tiny_source, monkeypatch):
    path = tiny_source / "skillcorner_tracking.jsonl"
    path.write_text("\n".join(path.read_text().splitlines()[:25]))
    monkeypatch.setattr(tracking, "_reference", lambda: object())
    with pytest.raises(ValueError, match="Missing unique in-play"):
        tracking.build_tracking(tiny_source)


def test_incomplete_keyframe_fails_before_model_call(tiny_source, monkeypatch):
    monkeypatch.setattr(tracking, "_reference", lambda: object())
    with pytest.raises(ValueError, match="Incomplete SkillCorner keyframe"):
        tracking.build_tracking(tiny_source)


def test_missing_metrica_is_explicit_and_contains_no_positions(tmp_path, reference):
    result = tracking._metrica(tmp_path, reference)
    assert result["status"] == "unavailable"
    assert result["positionsPublished"] is False
    assert "frames" not in result


@pytest.fixture(scope="module")
def actual_build():
    raw = Path(__file__).resolve().parents[1] / "data" / "raw"
    needed = ("skillcorner_match.json", "skillcorner_phases.csv", "skillcorner_tracking.jsonl")
    if not all((raw / name).is_file() for name in needed):
        pytest.skip("Ignored public-source fixtures have not been fetched")
    try:
        tracking._reference()
    except FileNotFoundError:
        pytest.skip("Official vendor reference has not been fetched")
    return tracking.build_tracking(raw)


def test_real_source_contract_and_bounds(actual_build):
    datasets, report = actual_build
    assert len(datasets) == 1
    dataset = datasets[0]
    assert dataset["source"] == "SkillCorner"
    assert dataset["pitch"] == [104., 68.]
    assert dataset["fps"] == 2
    assert [f["t"] for f in dataset["frames"]] == list(tracking.KEYFRAME_TIMES)
    assert len(dataset["frames"]) == 20
    for frame in dataset["frames"]:
        assert len(frame["players"]) == 22
        assert all(isinstance(p["detected"], bool) for p in frame["players"])
        control = np.array(frame["control"])
        assert control.shape == (10, 16)
        assert np.isfinite(control).all() and np.all((control >= 0) & (control <= 1))
        assert frame["massError"] <= .01 + 1e-9
    json.dumps((datasets, report), allow_nan=False)


def test_real_metrica_is_separate_aggregate_only(actual_build):
    _, report = actual_build
    metrica = report["metrica"]
    if metrica["status"] == "unavailable":
        pytest.skip(metrica["reason"])
    assert metrica["status"] == "validated"
    assert metrica["positionsPublished"] is False
    assert metrica["loadedFrames"] == min(metrica["availableRawFrames"], 5000)
    assert metrica["pitch"] == [105., 68.]
    assert metrica["fps"] == 25
    assert metrica["consecutiveRawFrames"]
    assert metrica["finitePlayerSamples"] > 0
    assert metrica["invalidPlayerCoordinates"] == 0
    assert "players" not in metrica and "frames" not in metrica
    if "controlSummary" in metrica:
        summary = metrica["controlSummary"]
        assert abs(1 - summary["meanHomeControl"] - summary["meanAwayControl"]) <= .01

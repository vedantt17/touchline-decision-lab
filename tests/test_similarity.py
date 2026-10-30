"""Synthetic fixtures verify mechanics; they are not empirical portfolio results."""
from copy import deepcopy
import json

import numpy as np
import pytest

from pipeline.similarity import (
    COUNT_KEYS, FEATURES, GROUPS, bootstrap_xt90, build_profiles, feature_weights,
    normalize_style, weighted_cosine,
)


def row(player=1, match=1, minutes=90, role="Midfielder", position="Center Midfield",
        style_bin=0, **counts):
    values = dict.fromkeys(COUNT_KEYS, 0.0)
    values.update(passes=20.0, completed_passes=15.0, moves=20.0)
    values.update(counts)
    style = np.zeros((3, 20))
    style[:, style_bin] = [20, 4, 8]
    return {"id": player, "name": f"Fixture {player}", "team": "Fixture Team",
            "role": role, "position": position, "minutes": minutes, "matchid": match,
            "counts": values, "style_counts": style.ravel().tolist()}


def cohort():
    signatures = [
        {"xt": 1.0, "progressive_passes": 8, "key_passes": 4},
        {"xt": 0.5, "progressive_carries": 8, "box_entries": 4},
        {"xt": 0.2, "pressures": 12, "defense": 5},
        {"xt": 0.8, "npxg": 0.9, "shots": 5},
    ]
    return [row(player=i + 1, match=match, style_bin=i, **signature)
            for i, signature in enumerate(signatures) for match in (1, 2, 3, 4)]


def by_id(players, player_id):
    return next(p for p in players if p["id"] == player_id)


def test_weighted_cosine_identity_and_geometry():
    assert weighted_cosine([1, -3, 5], [1, -3, 5], [2, 1, 0.5]) == pytest.approx(1)
    assert weighted_cosine([1, 0], [0, 1]) == pytest.approx(0)
    assert weighted_cosine([1, -2], [-1, 2]) == pytest.approx(-1)
    assert weighted_cosine([1, 2], [2, 1], [4, 1]) == pytest.approx(10 / np.sqrt(8 * 17))
    assert weighted_cosine([1e300, 2e300], [1e300, 2e300]) == pytest.approx(1)
    assert weighted_cosine([1, 1e300], [2, -1e300], [1, 0]) == pytest.approx(1)


@pytest.mark.parametrize("candidate,raw,signed,index", [
    ([-1, 0], -1.0, -100.0, 0.0),
    ([0, 1], 0.0, 0.0, 50.0),
    ([1, 0], 1.0, 100.0, 100.0),
])
def test_raw_cosine_is_not_a_signed_percentage_or_affine_display_index(candidate, raw, signed, index):
    cosine = weighted_cosine([1, 0], candidate)
    assert cosine == pytest.approx(raw)
    assert 100 * cosine == pytest.approx(signed)
    assert 50 * (cosine + 1) == pytest.approx(index)
    # Both presentation mappings must preserve the underlying distance/ranking.
    assert 1 - cosine == pytest.approx(2 * (1 - index / 100))


@pytest.mark.parametrize("a,b,w", [([0, 0], [1, 2], None), ([1, 2], [0, 0], None),
                                   ([1, 2], [1, 2], [0, 0]), ([np.nan, 0], [1, 2], None)])
def test_cosine_undefined_vectors_are_not_perfect_or_zero_similarity(a, b, w):
    assert weighted_cosine(a, b, w) is None


def test_feature_weights_split_group_mass_without_squaring():
    weights = feature_weights({"Progression": 3, "Security": 0})
    for group in GROUPS:
        total = sum(w for f, w in zip(FEATURES, weights) if f["group"] == group)
        assert total == pytest.approx(3 if group == "Progression" else 0 if group == "Security" else 1)
    assert [f["key"] for f in FEATURES] == [
        "xt90", "progressive_pass90", "progressive_carry90", "key_pass90", "box_entry90",
        "pressure90", "defense90", "npxg90", "shot90", "completion",
    ]
    assert set(GROUPS) == {"Progression", "Creation", "Defending", "Finishing", "Security"}
    with pytest.raises(ValueError):
        feature_weights({"Progression": -1})
    with pytest.raises(ValueError):
        feature_weights({"Typo": 1})
    with pytest.raises(ValueError):
        weighted_cosine([1], [1], [-1])


def test_raw_metrics_remain_raw_but_z_uses_role_shrinkage():
    rows = [row(1, xt=1, passes=10, completed_passes=5),
            row(2, xt=3, passes=30, completed_passes=27)]
    players, d = build_profiles(rows, [1], [])
    model = d["roleModels"]["Midfielder"]
    prior = d["rolePriors"]["Midfielder"]
    p = by_id(players, 1)
    assert p["metrics"]["xt90"] == 1
    assert p["metrics"]["completion"] == 50
    assert prior["rates"]["xt90"] == 2
    assert prior["completionFraction"] == pytest.approx(0.8)
    reconstructed_xt = p["z"]["xt90"] * model["scale"]["xt90"] + model["mean"]["xt90"]
    assert reconstructed_xt == pytest.approx((90 * 1 + 180 * 2) / 270)
    reconstructed_completion = p["z"]["completion"] * model["scale"]["completion"] + model["mean"]["completion"]
    assert reconstructed_completion == pytest.approx(100 * (5 + 50 * 0.8) / 60)
    assert model["minimumMinutes"] == 90
    assert p["xtInterval"] is None


def test_rates_use_sum_counts_over_sum_minutes_not_mean_of_match_rates():
    rows = [row(1, 1, minutes=90, xt=1), row(1, 2, minutes=10, xt=1)]
    players, _ = build_profiles(rows, [1, 2], [])
    assert players[0]["metrics"]["xt90"] == pytest.approx(1.8)
    assert players[0]["appearances"] == 2
    assert players[0]["matches"] == [1, 2]


def test_goalkeepers_zero_minutes_and_outside_split_excluded():
    rows = [row(1), row(2, role="Goalkeeper"), row(3, role="GK"),
            row(4, position="Goal Keeper"), row(5, minutes=0), row(6, match=999)]
    players, d = build_profiles(rows, [1], [])
    assert [p["id"] for p in players] == [1]
    assert d["counts"]["goalkeeperRows"] == 3
    assert d["counts"]["zeroMinuteRows"] == 1
    assert d["counts"]["outsideSplitRows"] == 1
    assert d["roleModels"]["Midfielder"]["scope"] == "unavailable"
    assert all(z == 0 for z in players[0]["z"].values())


def test_heldout_outlier_cannot_change_fit_or_training_prior():
    train = [row(1, xt=1), row(2, xt=3)]
    test = row(3, 2, xt=10)
    first, d1 = build_profiles([*train, test], [1], [2])
    test["counts"]["xt"] = 1e6
    second, d2 = build_profiles([*train, test], [1], [2])
    assert d1["roleModels"] == d2["roleModels"]
    assert d1["rolePriors"] == d2["rolePriors"]
    assert by_id(first, 1)["z"] == by_id(second, 1)["z"]
    assert by_id(first, 3)["z"] != by_id(second, 3)["z"]


def test_preferred_fit_threshold_excludes_low_exposure_player():
    rows = [row(1, minutes=180, xt=2), row(2, minutes=180, xt=6),
            row(3, minutes=90, xt=100)]
    _, d = build_profiles(rows, [1], [])
    model = d["roleModels"]["Midfielder"]
    assert model["scope"] == "role"
    assert model["minimumMinutes"] == 180
    assert model["playerIDs"] == [1, 2]
    # The pooled training prior deliberately uses all positive-minute TRAIN rows.
    assert d["rolePriors"]["Midfielder"]["playerIDs"] == [1, 2, 3]


def test_unseen_role_has_explicit_training_only_fallback():
    rows = [row(1, minutes=180, xt=1), row(2, minutes=180, xt=3),
            row(3, 2, role="Forward", minutes=180, xt=999)]
    _, d = build_profiles(rows, [1], [2])
    assert d["rolePriors"]["Forward"]["scope"] == "training_outfield"
    assert d["roleModels"]["Forward"]["scope"] == "training_outfield"
    assert d["roleModels"]["Forward"]["playerIDs"] == [1, 2]


def test_constant_features_are_neutral_even_for_heldout_outliers():
    players, d = build_profiles([row(1, xt=1), row(2, xt=3), row(3, 2, shots=999)], [1], [2])
    assert "shot90" in d["roleModels"]["Midfielder"]["zeroVarianceFeatures"]
    assert by_id(players, 3)["z"]["shot90"] == 0


def test_style_normalizes_each_action_and_does_not_invent_empty_blocks():
    counts = np.zeros((3, 20))
    counts[0, 0], counts[1, 19] = 10000, 1
    style = np.array(normalize_style(counts.ravel())).reshape(3, 20)
    assert style.sum(axis=1).tolist() == pytest.approx([1, 1, 0])
    assert style[0, 0] > 0.99
    assert style[1, 19] > 0.8
    assert style[0, 1] > 0
    assert not style[2].any()
    assert normalize_style([0] * 60) == [0] * 60


def test_bootstrap_seeded_ratio_and_order_independent():
    rows = [row(1, 1, minutes=90, xt=1), row(1, 2, minutes=10, xt=1),
            row(1, 3, minutes=45, xt=-0.5)]
    interval = bootstrap_xt90(rows)
    values = np.array([[90, 1], [10, 1], [45, -0.5]])
    samples = values[np.random.default_rng(42).integers(0, 3, size=(300, 3))].sum(axis=1)
    expected = np.quantile(90 * samples[:, 1] / samples[:, 0], [0.05, 0.95])
    assert interval == pytest.approx(expected)
    assert interval == bootstrap_xt90(rows)
    assert interval == bootstrap_xt90(list(reversed(rows)))
    assert bootstrap_xt90([rows[0]]) is None
    assert bootstrap_xt90([rows[0], rows[0]]) is None
    assert bootstrap_xt90([]) is None


def test_temporal_retrieval_real_calculation_and_chance_pool():
    rows = cohort()
    rows += [row(5, match, xt=0.3, shots=2, defense=2, style_bin=8) for match in (1, 2)]
    _, d = build_profiles(rows, [1, 2], [3, 4])
    performance = d["testPerformance"]
    assert performance["minimumAppearancesEachSplit"] == 2
    assert not performance["relaxedAppearances"]
    assert performance["eligibleIDs"] == [1, 2, 3, 4]
    for mode in ("metric", "spatial"):
        result = performance[mode]
        assert result["queryCount"] == 4
        assert result["top1"] == 1.0
        assert result["top3"] == 1.0
        assert result["chanceTop1"] == pytest.approx(1 / 5)
        assert result["chanceTop3"] == pytest.approx(3 / 5)
        assert result["candidateCounts"] == [5] * 4
    assert "NOT transfer quality" in performance["interpretation"]


def test_retrieval_relaxes_appearances_only_when_needed():
    rows = [r for r in cohort() if r["matchid"] in (1, 3)]
    _, d = build_profiles(rows, [1], [3])
    assert d["testPerformance"]["minimumAppearancesEachSplit"] == 1
    assert d["testPerformance"]["relaxedAppearances"]
    assert d["testPerformance"]["metric"]["queryCount"] == 4


def test_retrieval_candidates_are_role_restricted_and_evidence_is_computed():
    rows = cohort()
    rows += [row(5, match, role="Striker", xt=0.4, shots=3, style_bin=6)
             for match in (1, 2, 3, 4)]
    _, d = build_profiles(rows, [1, 2], [3, 4])
    assert 5 not in d["testPerformance"]["eligibleIDs"]
    for mode in ("metric", "spatial"):
        result = d["testPerformance"][mode]
        assert result["candidateCounts"] == [4] * 4
        assert result["chanceTop1"] == pytest.approx(0.25)
    evidence = {item["name"]: item["value"] for item in d["evaluation"]}
    assert evidence["Metric-profile temporal top-1"] == d["testPerformance"]["metric"]["top1"]
    assert evidence["Metric-profile chance top-3"] == d["testPerformance"]["metric"]["chanceTop3"]
    assert evidence["Profile feature count"] == len(FEATURES)


def test_retrieval_with_only_one_role_peer_is_unavailable_not_perfect():
    _, d = build_profiles([row(1, match) for match in (1, 2, 3, 4)], [1, 2], [3, 4])
    assert d["testPerformance"]["metric"]["status"] == "unavailable"
    assert d["testPerformance"]["metric"]["top1"] is None
    assert d["testPerformance"]["spatial"]["top1"] is None
    evidence = {item["name"]: item["value"] for item in d["evaluation"]}
    assert evidence["Metric-profile temporal top-1"] == "Unavailable"


def test_split_role_changes_are_supported_but_not_used_as_same_role_queries():
    rows = cohort()
    for r in rows:
        if r["id"] == 1 and r["matchid"] in (3, 4):
            r["role"] = "Forward"
            r["minutes"] = 100
    players, d = build_profiles(rows, [1, 2], [3, 4])
    assert by_id(players, 1)["role"] == "Forward"
    assert set(d["roleModels"]) == {"Forward", "Midfielder"}
    assert 1 not in d["testPerformance"]["eligibleIDs"]


def test_neighbor_agreement_sensitivity_and_default_target():
    rows = cohort()
    rows += [row(5 + i, match, style_bin=5 + i, xt=0.3 + i * 0.1,
                 shots=i + 1, pressures=4 - i) for i in range(4) for match in (1, 2, 3, 4)]
    rows[0]["minutes"] = 100
    players, d = build_profiles(rows, [1, 2], [3, 4])
    neighbors = d["neighborhood"]
    assert neighbors["targetID"] == players[0]["id"] == 1
    assert neighbors["status"] == "ok"
    assert len(neighbors["metricNeighborIDs"]) == 5
    assert 1 not in neighbors["candidateIDs"]
    a, b = set(neighbors["metricNeighborIDs"]), set(neighbors["spatialNeighborIDs"])
    assert neighbors["metricSpatialJaccardAt5"] == len(a & b) / len(a | b)
    assert len(neighbors["sensitivity"]) == 5
    weights = feature_weights()
    target = players[0]
    candidates = [p for p in players if p["id"] in neighbors["candidateIDs"]]
    assert sum(weights) == pytest.approx(5)
    for sensitivity in neighbors["sensitivity"]:
        active_weights = feature_weights(sensitivity["groupWeights"])
        ordered = sorted(candidates, key=lambda p: (
            -weighted_cosine([target["z"][f["key"]] for f in FEATURES],
                             [p["z"][f["key"]] for f in FEATURES], active_weights),
            -p["minutes"], p["id"]))
        assert sensitivity["neighborIDs"] == [p["id"] for p in ordered[:5]]
        a, b = set(neighbors["metricNeighborIDs"]), set(sensitivity["neighborIDs"])
        assert sensitivity["jaccardAt5"] == len(a & b) / len(a | b)


def test_output_is_plain_json_deterministic_and_input_is_not_mutated():
    rows = cohort()
    snapshot = deepcopy(rows)
    result = build_profiles(rows, [1, 2], [3, 4])
    assert rows == snapshot
    assert result == build_profiles(list(reversed(rows)), [2, 1], [4, 3])
    json.dumps(result, allow_nan=False)
    players, d = result
    assert d["featureCount"] == 10
    assert set(players[0]) == {"id", "name", "team", "role", "position", "minutes", "appearances",
                               "matches", "metrics", "z", "style", "xtInterval"}


def test_empty_training_data_no_fabricated_model_or_performance():
    players, d = build_profiles([row(1, 2)], [], [2])
    assert players[0]["metrics"]["completion"] == 75
    assert set(players[0]["z"].values()) == {0.0}
    assert d["rolePriors"]["Midfielder"]["scope"] == "unavailable"
    assert d["testPerformance"]["metric"]["top1"] is None
    assert d["neighborhood"]["targetID"] is None
    json.dumps(build_profiles([], [], []), allow_nan=False)


def test_zero_passes_and_empty_style_blocks_are_reported():
    rows = [row(1, passes=0, completed_passes=0), row(2, xt=1)]
    rows[0]["style_counts"] = [0] * 60
    players, d = build_profiles(rows, [1], [])
    assert by_id(players, 1)["metrics"]["completion"] == 0
    assert d["zeroPassPlayerIDs"] == [1]
    assert d["emptyStyleBlocks"] == {"1": ["pass", "carry", "pressure"]}
    assert by_id(players, 1)["style"] == [0] * 60


@pytest.mark.parametrize("case", ["overlap", "duplicate", "negative_minutes", "negative_count",
                                  "nonfinite", "bad_style", "overcompletion"])
def test_invalid_input_rejected(case):
    rows, train, test = [row()], [1], []
    if case == "overlap":
        test = [1]
    elif case == "duplicate":
        rows += deepcopy(rows)
    elif case == "negative_minutes":
        rows[0]["minutes"] = -1
    elif case == "negative_count":
        rows[0]["counts"]["shots"] = -1
    elif case == "nonfinite":
        rows[0]["counts"]["xt"] = np.inf
    elif case == "bad_style":
        rows[0]["style_counts"] = [0] * 59
    else:
        rows[0]["counts"]["completed_passes"] = 21
    with pytest.raises(ValueError):
        build_profiles(rows, train, test)

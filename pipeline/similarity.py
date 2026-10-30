"""Training-only profile transforms and bounded, descriptive similarity checks."""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from numbers import Integral

import numpy as np
from sklearn.preprocessing import StandardScaler


FEATURES: list[dict] = [
    {"key": "xt90", "label": "xT / 90", "group": "Progression", "unit": "/90",
     "description": "Raw net successful-move xT per 90 approximate minutes; not a complete player value."},
    {"key": "progressive_pass90", "label": "Progressive passes / 90", "group": "Progression", "unit": "/90",
     "description": "Source-parser progressive pass count per 90 approximate minutes."},
    {"key": "progressive_carry90", "label": "Progressive carries / 90", "group": "Progression", "unit": "/90",
     "description": "Source-parser progressive carry count per 90 approximate minutes."},
    {"key": "key_pass90", "label": "Key passes / 90", "group": "Creation", "unit": "/90",
     "description": "Source-parser key pass count per 90 approximate minutes."},
    {"key": "box_entry90", "label": "Box entries / 90", "group": "Creation", "unit": "/90",
     "description": "Source-parser box-entry count per 90 approximate minutes."},
    {"key": "pressure90", "label": "Pressures / 90", "group": "Defending", "unit": "/90",
     "description": "Recorded pressure events per 90; not tracking-derived defensive coverage."},
    {"key": "defense90", "label": "Defensive actions / 90", "group": "Defending", "unit": "/90",
     "description": "Source-parser defensive action count per 90; definition depends on event coverage."},
    {"key": "npxg90", "label": "Non-penalty xG / 90", "group": "Finishing", "unit": "/90",
     "description": "Sum of source non-penalty shot xG per 90; opportunity, not finishing skill."},
    {"key": "shot90", "label": "Shots / 90", "group": "Finishing", "unit": "/90",
     "description": "Source-parser shot count per 90 approximate minutes."},
    {"key": "completion", "label": "Pass completion", "group": "Security", "unit": "%",
     "description": "100 times completed / attempted passes; raw zero when no passes were attempted."},
]

RATE_COUNTS = dict(zip(
    [f["key"] for f in FEATURES[:-1]],
    ["xt", "progressive_passes", "progressive_carries", "key_passes", "box_entries",
     "pressures", "defense", "npxg", "shots"],
))
COUNT_KEYS = (*RATE_COUNTS.values(), "passes", "completed_passes", "moves")
GROUPS = tuple(dict.fromkeys(f["group"] for f in FEATURES))
PRIOR_MINUTES = 180.0
PRIOR_PASSES = 50.0
STYLE_PSEUDOCOUNT = 0.01
BOOTSTRAP_DRAWS = 300
BOOTSTRAP_SEED = 42
DEFAULT_MINUTES = 270.0


def feature_weights(group_weights: Mapping[str, float] | None = None) -> list[float]:
    """Divide each nonnegative group weight over its features, in FEATURES order."""
    group_weights = {} if group_weights is None else group_weights
    if set(group_weights) - set(GROUPS):
        raise ValueError("Unknown feature group")
    sizes = Counter(f["group"] for f in FEATURES)
    weights = {group: float(group_weights.get(group, 1.0)) for group in GROUPS}
    if any(not np.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError("Group weights must be finite and nonnegative")
    return [weights[f["group"]] / sizes[f["group"]] for f in FEATURES]


def weighted_cosine(a: Sequence[float], b: Sequence[float],
                    weights: Sequence[float] | None = None) -> float | None:
    """Return cosine in [-1, 1], or None for a nonfinite/zero-norm vector.

    The dot product uses w (equivalent to scaling vectors by sqrt(w)), not w^2.
    """
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.ndim != 1 or a.shape != b.shape or not a.size:
        raise ValueError("Cosine vectors must be nonempty, one-dimensional and equal length")
    w = np.ones(a.size) if weights is None else np.asarray(weights, dtype=float)
    if w.shape != a.shape or not np.isfinite(w).all() or (w < 0).any():
        raise ValueError("Cosine weights must match vectors and be finite and nonnegative")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        return None
    active = w > 0
    if not active.any():
        return None
    a, b, w = a[active], b[active], w[active]
    # Scaling each vector prevents overflow without changing the cosine.
    a = a / max(float(np.max(np.abs(a))), 1.0)
    b = b / max(float(np.max(np.abs(b))), 1.0)
    w = w / max(float(np.max(w)), 1.0)
    aa, bb = float(np.dot(w, a * a)), float(np.dot(w, b * b))
    if aa <= 1e-16 or bb <= 1e-16:
        return None
    return float(np.clip(np.dot(w * a, b) / np.sqrt(aa * bb), -1.0, 1.0))


def normalize_style(counts: Sequence[float]) -> list[float]:
    """Normalize pass/carry/pressure blocks independently, never by event volume."""
    values = np.asarray(counts, dtype=float)
    if values.shape != (60,) or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("style_counts must contain 60 finite nonnegative counts")
    blocks = values.reshape(3, 20).copy()
    for block in blocks:
        if block.sum() > 0:
            block += STYLE_PSEUDOCOUNT
            block /= block.sum()
    return blocks.ravel().tolist()


def bootstrap_xt90(rows: Sequence[dict], draws: int = BOOTSTRAP_DRAWS,
                   seed: int = BOOTSTRAP_SEED) -> list[float] | None:
    """Percentile interval for raw xT/90 by resampling complete player-matches."""
    clusters = defaultdict(lambda: [0.0, 0.0])
    for row in rows:
        minutes, xt = float(row["minutes"]), float(row["counts"]["xt"])
        if not np.isfinite(minutes) or minutes < 0 or not np.isfinite(xt):
            raise ValueError("Bootstrap exposures and xT must be finite, exposures nonnegative")
        if minutes > 0:
            clusters[int(row["matchid"])][0] += minutes
            clusters[int(row["matchid"])][1] += xt
    if len(clusters) < 2:
        return None
    if not isinstance(draws, Integral) or draws < 1:
        raise ValueError("Bootstrap draws must be a positive integer")
    values = np.array([clusters[key] for key in sorted(clusters)])
    rng = np.random.default_rng(seed)
    # Only 300 x number-of-matches indices are held, never event-level samples.
    samples = values[rng.integers(0, len(values), size=(draws, len(values)))].sum(axis=1)
    rates = 90.0 * samples[:, 1] / samples[:, 0]
    return np.quantile(rates, [0.05, 0.95]).tolist()


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    return int(value)


def _is_goalkeeper(row):
    labels = [str(row.get(key, "")).strip().lower().replace(" ", "").replace("-", "")
              for key in ("role", "position")]
    return any(label in {"gk", "goalkeeper", "goalkeepers", "keeper"} for label in labels)


def _prepare(rows, selected_ids):
    prepared, seen = [], set()
    excluded = {"goalkeeperRows": 0, "zeroMinuteRows": 0, "outsideSplitRows": 0}
    for row in rows:
        match_id = _integer(row["matchid"], "matchid")
        if match_id not in selected_ids:
            excluded["outsideSplitRows"] += 1
            continue
        if _is_goalkeeper(row):
            excluded["goalkeeperRows"] += 1
            continue
        player_id = _integer(row["id"], "id")
        key = (player_id, match_id)
        if key in seen:
            raise ValueError(f"Duplicate player-match row: {key}")
        seen.add(key)
        minutes = float(row["minutes"])
        if not np.isfinite(minutes) or minutes < 0:
            raise ValueError("minutes must be finite and nonnegative")
        if minutes == 0:
            excluded["zeroMinuteRows"] += 1
            continue
        labels = {}
        for name in ("name", "team", "role", "position"):
            if not isinstance(row.get(name), str) or not row[name].strip():
                raise ValueError(f"{name} must be a nonempty string")
            labels[name] = row[name].strip()
        counts = {key: float(row["counts"][key]) for key in COUNT_KEYS}
        if any(not np.isfinite(value) or (key != "xt" and value < 0)
               for key, value in counts.items()):
            raise ValueError("Counts must be finite and nonnegative, except net xT may be negative")
        if counts["completed_passes"] > counts["passes"]:
            raise ValueError("completed_passes cannot exceed passes")
        style = np.asarray(row["style_counts"], dtype=float)
        if style.shape != (60,) or not np.isfinite(style).all() or (style < 0).any():
            raise ValueError("style_counts must contain 60 finite nonnegative counts")
        prepared.append({"id": player_id, "matchid": match_id, "minutes": minutes,
                         **labels, "counts": counts, "style_counts": style.tolist()})
    return sorted(prepared, key=lambda row: (row["id"], row["matchid"])), excluded


def _aggregate(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["id"]].append(row)
    aggregates = {}
    for player_id, matches in sorted(grouped.items()):
        def dominant(key):
            exposure = defaultdict(float)
            for row in matches:
                exposure[row[key]] += row["minutes"]
            return min(exposure, key=lambda label: (-exposure[label], label))

        aggregates[player_id] = {
            "id": player_id, **{key: dominant(key) for key in ("name", "team", "role", "position")},
            "minutes": sum(row["minutes"] for row in matches),
            "appearances": len(matches), "matches": [row["matchid"] for row in matches],
            "counts": {key: sum(row["counts"][key] for row in matches) for key in COUNT_KEYS},
            "style_counts": np.sum([row["style_counts"] for row in matches], axis=0).tolist(),
            "rows": matches,
        }
    return aggregates


def _raw_metrics(player):
    counts, minutes = player["counts"], player["minutes"]
    return {**{key: 90.0 * counts[count] / minutes for key, count in RATE_COUNTS.items()},
            "completion": 100.0 * counts["completed_passes"] / counts["passes"]
            if counts["passes"] else 0.0}


def _fit_priors(training, roles):
    priors = {}
    for role in roles:
        members = [p for p in training.values() if p["role"] == role]
        scope = "role"
        if not members:
            members, scope = list(training.values()), "training_outfield"
        minutes = sum(p["minutes"] for p in members)
        counts = {key: sum(p["counts"][key] for p in members) for key in COUNT_KEYS}
        rates = {key: 90.0 * counts[count] / minutes for key, count in RATE_COUNTS.items()} if minutes else {}
        # No training passes means there is no defensible completion prior.
        completion = counts["completed_passes"] / counts["passes"] if counts["passes"] else None
        priors[role] = {"scope": scope if minutes else "unavailable", "minutes": minutes,
                        "playerIDs": [p["id"] for p in members], "rates": rates,
                        "completionFraction": completion, "passes": counts["passes"]}
    return priors


def _shrunk_metrics(player, prior):
    raw = _raw_metrics(player)
    if not prior["rates"]:
        return raw
    minutes, counts = player["minutes"], player["counts"]
    shrunk = {key: (90.0 * counts[count] + PRIOR_MINUTES * prior["rates"][key]) /
              (minutes + PRIOR_MINUTES) for key, count in RATE_COUNTS.items()}
    prior_completion = prior["completionFraction"]
    shrunk["completion"] = (100.0 * (counts["completed_passes"] + PRIOR_PASSES * prior_completion) /
                            (counts["passes"] + PRIOR_PASSES)) if prior_completion is not None else raw["completion"]
    return shrunk


def _vector(metrics):
    return [metrics[f["key"]] for f in FEATURES]


def _fit_models(training, priors, roles):
    models = {}
    for role in roles:
        fit, scope, threshold = [], "unavailable", None
        # Prefer adequately exposed role peers, then relax exposure, then pool TRAIN only.
        for proposed_scope, members, minimum in (
            ("role", [p for p in training.values() if p["role"] == role], 180),
            ("role", [p for p in training.values() if p["role"] == role], 90),
            ("training_outfield", list(training.values()), 180),
            ("training_outfield", list(training.values()), 90),
        ):
            eligible = [p for p in members if p["minutes"] >= minimum]
            if len(eligible) >= 2:
                fit, scope, threshold = eligible, proposed_scope, minimum
                break
        if not fit:
            models[role] = {"scope": scope, "minimumMinutes": None, "playerIDs": [],
                            "mean": {}, "scale": {}, "zeroVarianceFeatures": []}
            continue
        matrix = [_vector(_shrunk_metrics(p, priors[p["role"]])) for p in fit]
        scaler = StandardScaler().fit(matrix)
        models[role] = {
            "scope": scope, "minimumMinutes": threshold, "playerIDs": [p["id"] for p in fit],
            "mean": dict(zip((f["key"] for f in FEATURES), scaler.mean_.tolist())),
            "scale": dict(zip((f["key"] for f in FEATURES), scaler.scale_.tolist())),
            "zeroVarianceFeatures": [f["key"] for f, variance in zip(FEATURES, scaler.var_) if variance <= 1e-16],
        }
    return models


def _profiles(aggregates, priors, models, bootstrap=False):
    profiles = []
    for player in aggregates.values():
        model = models[player["role"]]
        shrunk = _shrunk_metrics(player, priors[player["role"]])
        z = {f["key"]: 0.0 for f in FEATURES}
        if model["scope"] != "unavailable":
            for feature in FEATURES:
                key = feature["key"]
                if key not in model["zeroVarianceFeatures"]:
                    z[key] = (shrunk[key] - model["mean"][key]) / model["scale"][key]
        profiles.append({
            **{key: player[key] for key in ("id", "name", "team", "role", "position", "minutes", "appearances", "matches")},
            "metrics": _raw_metrics(player), "z": z,
            "style": normalize_style(player["style_counts"]),
            "xtInterval": bootstrap_xt90(player["rows"]) if bootstrap else None,
        })
    return sorted(profiles, key=lambda p: (-p["minutes"], p["id"]))


def _score(a, b, mode="metric", group_weights=None):
    if mode == "spatial":
        return weighted_cosine(a["style"], b["style"])
    return weighted_cosine(_vector(a["z"]), _vector(b["z"]), feature_weights(group_weights))


def _rank(query, candidates, mode="metric", group_weights=None):
    scored = [(p, _score(query, p, mode, group_weights)) for p in candidates]
    return [p["id"] for p, _ in sorted(
        ((p, score) for p, score in scored if score is not None),
        key=lambda pair: (-pair[1], -pair[0]["minutes"], pair[0]["id"]),
    )]


def _retrieval(training, testing):
    train_by_id = {p["id"]: p for p in training}

    def eligible(min_apps):
        return [p for p in testing if p["minutes"] >= 90 and p["appearances"] >= min_apps
                and p["id"] in train_by_id and train_by_id[p["id"]]["minutes"] >= 90
                and train_by_id[p["id"]]["appearances"] >= min_apps
                and p["role"] == train_by_id[p["id"]]["role"]
                and sum(peer["role"] == p["role"] and peer["minutes"] >= 90
                        and peer["appearances"] >= min_apps for peer in training) >= 2]

    queries, min_apps = eligible(2), 2
    if not queries:
        queries, min_apps = eligible(1), 1
    performance = {"minimumMinutesEachSplit": 90, "minimumAppearancesEachSplit": min_apps,
                   "relaxedAppearances": min_apps == 1, "eligibleIDs": sorted(p["id"] for p in queries),
                   "interpretation": "Temporal same-player profile stability proxy; NOT transfer quality or recruitment accuracy."}
    for mode in ("metric", "spatial"):
        records, skipped = [], []
        for query in queries:
            candidates = [p for p in training if p["role"] == query["role"] and p["minutes"] >= 90
                          and p["appearances"] >= min_apps]
            ranked = _rank(query, candidates, mode)
            # Undefined vectors must not count as retrieval failures or easy one-player successes.
            if query["id"] not in ranked or len(ranked) < 2:
                skipped.append(query["id"])
                continue
            rank = ranked.index(query["id"]) + 1
            records.append({"id": query["id"], "role": query["role"], "rank": rank,
                            "candidateCount": len(ranked), "top1": rank == 1, "top3": rank <= 3})
        count = len(records)
        performance[mode] = {
            "status": "ok" if count else "unavailable", "queryCount": count,
            "top1": sum(r["top1"] for r in records) / count if count else None,
            "top3": sum(r["top3"] for r in records) / count if count else None,
            "chanceTop1": sum(1.0 / r["candidateCount"] for r in records) / count if count else None,
            "chanceTop3": sum(min(3, r["candidateCount"]) / r["candidateCount"] for r in records) / count if count else None,
            "candidateCounts": [r["candidateCount"] for r in records],
            "eligibleIDs": [r["id"] for r in records], "skippedIDs": skipped, "queries": records,
        }
    return performance


def _jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a or b else None


def _neighborhood_diagnostics(players):
    eligible = [p for p in players if p["minutes"] >= DEFAULT_MINUTES]
    result = {"minimumMinutes": DEFAULT_MINUTES, "eligibleIDs": sorted(p["id"] for p in eligible),
              "targetID": eligible[0]["id"] if eligible else None, "k": 5,
              "effectiveK": 0, "membershipTestInformative": False,
              "status": "unavailable", "candidateIDs": [], "metricNeighborIDs": [],
              "spatialNeighborIDs": [], "metricSpatialJaccardAt5": None,
              "metricSpatialOverlapAt5": None, "sensitivity": []}
    if not eligible:
        return result
    target = eligible[0]
    candidates = [p for p in eligible if p["role"] == target["role"] and p["id"] != target["id"]]
    # Use the same finite-vector pool for both representations, never padded neighbors.
    candidates = [p for p in candidates if _score(target, p) is not None
                  and _score(target, p, "spatial") is not None]
    metric = _rank(target, candidates)[:5]
    spatial = _rank(target, candidates, "spatial")[:5]
    result.update(status="ok" if candidates else "unavailable",
                  effectiveK=min(5, len(candidates)), membershipTestInformative=len(candidates) > 5,
                  candidateIDs=sorted(p["id"] for p in candidates),
                  metricNeighborIDs=metric, spatialNeighborIDs=spatial,
                  metricSpatialJaccardAt5=_jaccard(metric, spatial),
                  metricSpatialOverlapAt5=len(set(metric) & set(spatial)) if candidates else None)
    for group in GROUPS:
        weights = {g: 2.0 if g == group else 1.0 for g in GROUPS}
        ranking = _rank(target, candidates, group_weights=weights)[:5]
        result["sensitivity"].append({"group": group, "multiplier": 2.0, "groupWeights": weights,
                                      "neighborIDs": ranking, "jaccardAt5": _jaccard(metric, ranking)})
    return result


def _evaluation(diagnostics):
    """Presentation-ready Evidence.evaluation entries, derived only from computed values."""
    entries = [{"name": "Profile feature count", "value": diagnostics["featureCount"],
                "detail": "Raw rates are displayed; similarity uses exposure-shrunk, training-fitted z profiles."}]
    performance = diagnostics["testPerformance"]
    for mode, label in (("metric", "Metric-profile"), ("spatial", "Spatial-profile")):
        result = performance[mode]
        detail = (f"{result['queryCount']} evaluated same-role queries; >=90 minutes and "
                  f">={performance['minimumAppearancesEachSplit']} appearance(s) per split. "
                  "Same-player stability proxy, NOT transfer quality. Rates are fractions in [0,1].")
        entries.append({"name": f"{label} retrieval queries", "value": result["queryCount"], "detail": detail})
        for key, suffix in (("top1", "temporal top-1"), ("top3", "temporal top-3"),
                            ("chanceTop1", "chance top-1"), ("chanceTop3", "chance top-3")):
            entries.append({"name": f"{label} {suffix}",
                            "value": result[key] if result[key] is not None else "Unavailable",
                            "detail": detail + (" Chance assumes uniform random ranking within each actual candidate pool."
                                                 if key.startswith("chance") else "")})
    neighbors = diagnostics["neighborhood"]
    detail = (f"Target provider ID {neighbors['targetID']}; >=270 minutes; "
              f"{len(neighbors['candidateIDs'])} common same-role candidates, effective k={neighbors['effectiveK']}. "
              "Jaccard is set overlap, not ranking correlation. Pools of <=5 make membership comparisons trivial.")
    entries.append({"name": "Metric vs spatial Jaccard@5",
                    "value": neighbors["metricSpatialJaccardAt5"]
                    if neighbors["metricSpatialJaccardAt5"] is not None else "Unavailable", "detail": detail})
    for item in neighbors["sensitivity"]:
        entries.append({"name": f"{item['group']} weight x2 Jaccard@5",
                        "value": item["jaccardAt5"] if item["jaccardAt5"] is not None else "Unavailable",
                        "detail": detail + " Only this group weight is doubled; z transforms remain fixed."})
    return entries


def build_profiles(rows: list[dict], train_match_ids: list[int],
                   test_match_ids: list[int]) -> tuple[list[dict], dict]:
    """Return union-split Player objects and plain-JSON, training-only diagnostics.

    Caller supplies the temporal split and upstream count definitions / xT values.
    This module never fits an xT model or infers event / match chronology.
    """
    train_ids = {_integer(value, "train match id") for value in train_match_ids}
    test_ids = {_integer(value, "test match id") for value in test_match_ids}
    if train_ids & test_ids:
        raise ValueError("Train and test match IDs must be disjoint")
    prepared, excluded = _prepare(rows, train_ids | test_ids)
    training = _aggregate([row for row in prepared if row["matchid"] in train_ids])
    testing = _aggregate([row for row in prepared if row["matchid"] in test_ids])
    combined = _aggregate(prepared)
    roles = sorted({p["role"] for cohort in (combined, training, testing) for p in cohort.values()})
    priors = _fit_priors(training, roles)
    models = _fit_models(training, priors, roles)
    train_profiles = _profiles(training, priors, models)
    test_profiles = _profiles(testing, priors, models)
    players = _profiles(combined, priors, models, bootstrap=True)
    neighbors = _neighborhood_diagnostics(players)
    diagnostics = {
        "metrics": [f["key"] for f in FEATURES], "featureCount": len(FEATURES),
        "groups": list(GROUPS), "featureWeights": dict(zip((f["key"] for f in FEATURES), feature_weights())),
        "counts": {"inputRows": len(rows), "usedRows": len(prepared), "players": len(players),
                   "trainingPlayers": len(training), "testPlayers": len(testing), **excluded},
        "parameters": {"priorMinutes": PRIOR_MINUTES, "priorPasses": PRIOR_PASSES,
                       "fitPreferredMinutes": 180, "fitFallbackMinutes": 90, "fitMinimumPlayers": 2,
                       "stylePseudocount": STYLE_PSEUDOCOUNT, "styleBinsPerAction": 20,
                       "styleActionOrder": ["pass", "carry", "pressure"], "styleGrid": [5, 4],
                       "bootstrapDraws": BOOTSTRAP_DRAWS, "bootstrapSeed": BOOTSTRAP_SEED,
                       "bootstrapConfidence": 0.90, "defaultMinimumMinutes": DEFAULT_MINUTES,
                       "neighborK": 5, "sensitivityGroupMultiplier": 2.0},
        "split": {"trainMatchIDs": sorted(train_ids), "testMatchIDs": sorted(test_ids),
                  "missingTrainMatchIDs": sorted(train_ids - {r["matchid"] for r in prepared}),
                  "missingTestMatchIDs": sorted(test_ids - {r["matchid"] for r in prepared}),
                  "chronologyVerified": False,
                  "scope": "Profiles describe train/test union; fit and priors use TRAIN only. Caller must verify chronology."},
        "rolePriors": priors, "roleModels": models,
        "testPerformance": _retrieval(train_profiles, test_profiles),
        "eligibleIDs": neighbors["eligibleIDs"], "neighborhood": neighbors,
        "zeroPassPlayerIDs": [p["id"] for p in combined.values() if p["counts"]["passes"] == 0],
        "emptyStyleBlocks": {str(p["id"]): [action for action, block in
                            zip(("pass", "carry", "pressure"), np.array(p["style"]).reshape(3, 20))
                            if not np.any(block)] for p in players if not np.all(
                                np.any(np.array(p["style"]).reshape(3, 20), axis=1))},
        "interpretation": "Cosine x 100 is signed profile similarity, NOT quality, probability, or transfer suitability.",
    }
    diagnostics["evaluation"] = _evaluation(diagnostics)
    return players, diagnostics

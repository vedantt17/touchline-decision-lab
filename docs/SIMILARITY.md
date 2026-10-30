# Player-profile worker

Ownership: `pipeline/similarity.py`, `tests/test_similarity.py`, and this document.
No downloads, source parsing, xT fitting, UI changes, or file output occur in the worker.

## Integration contract

```python
from pipeline.similarity import FEATURES, build_profiles

players, diagnostics = build_profiles(rows, train_match_ids, test_match_ids)
# FEATURES -> Dataset.features; players -> Dataset.players
# diagnostics["evaluation"] -> append to Evidence.evaluation
# diagnostics -> retain as evidence.profileDiagnostics or a separate audit object
```

`FEATURES` is a `list[dict]` with `key`, `label`, `group`, `unit`, `description`.
Exact group strings for the main pipeline/UI:

| Group | Feature keys |
| --- | --- |
| Progression | `xt90`, `progressive_pass90`, `progressive_carry90` |
| Creation | `key_pass90`, `box_entry90` |
| Defending | `pressure90`, `defense90` |
| Finishing | `npxg90`, `shot90` |
| Security | `completion` |

Each input row is one provider player ID / match ID, with `id`, `name`, `team`,
`role`, `position`, `minutes`, `matchid`, `counts`, and `style_counts`.
All counts are required: `xt`, `progressive_passes`, `progressive_carries`,
`key_passes`, `box_entries`, `pressures`, `defense`, `shots`, `npxg`, `passes`,
`completed_passes`, `moves`. Net xT may be negative; all other counts must be
nonnegative and finite. Completed passes cannot exceed attempts.

`style_counts` has 60 nonnegative finite counts: pass, carry, pressure blocks of
20. Main owns binning on the attacked-left-to-right 105 x 68 m pitch, 5 x 4 grid.
This worker preserves within-block ordering and does not flip axes or infer
events. Main owns the upstream event definitions and training-fitted xT values.

Train/test match ID sets must be disjoint. The worker does not infer chronology
from numeric IDs; the caller must supply and verify a temporal split. It ignores
rows outside the split union, goalkeeper role/position labels, and zero minutes,
with exclusion counts. Duplicate player-match rows or malformed included rows
fail instead of silently doubling exposure. Inputs are never mutated.

Returned Player objects exactly contain `id`, `name`, `team`, `role`, `position`,
`minutes`, `appearances`, `matches`, `metrics`, `z`, `style`, `xtInterval`.
They describe the **train/test union**, sorted by descending minutes, then ID.
Appearances count positive-minute matches. Metadata uses the largest cumulative
minute share per label, with lexical tie-breaking; IDs, not names, join windows.

## Raw metrics and shrinkage

Displayed `metrics` remain raw: `90 * sum(count) / sum(minutes)` for count-rate
features, and `100 * completed / attempted` for `completion` (percentage points,
0-100). No-pass completion is encoded as raw zero to honor the numeric contract,
not as evidence of poor passing; consult `zeroPassPlayerIDs`.

Only the vectors used for z normalization receive shrinkage:

```text
role_rate = 90 * TRAIN role count / TRAIN role minutes
shrunk_rate = (90 * player_count + 180 * role_rate) / (player_minutes + 180)
role_completion = TRAIN role completions / TRAIN role attempts
shrunk_completion = 100 * (player_completions + 50 * role_completion)
                       / (player_attempts + 50)
```

Role priors are exposure-pooled over **all positive-minute TRAIN player
aggregates**, including low-minute players. A player's role is determined within
each window independently. No held-out count or exposure enters a prior. A role
with no training players borrows the pooled TRAIN-outfield prior, explicitly
marked `training_outfield`. No training passes means no completion prior:
completion remains raw. No training observations means no prior at all.

For each role, fit sklearn `StandardScaler` to shrunk **TRAIN player profiles**:

1. Same-role players with >=180 training minutes, if at least two exist.
2. Otherwise same-role players with >=90 minutes, if at least two exist.
3. Otherwise pooled TRAIN outfield players with >=180, then >=90 minutes.
4. Otherwise mark the transform unavailable and emit zero z vectors.

The scaler uses equally weighted player profiles and population variance
(`ddof=0`). Pooled fallback profiles retain their own TRAIN-role shrinkage.
Training variance <=1e-16 disables that feature (z=0), including at inference;
new held-out variation cannot create evidence on a previously constant axis.
The model is shared, not refitted for selected targets, filters, test windows, or
weight sensitivity. `roleModels` exposes fit scope, threshold, IDs, means,
scales, and disabled features; `rolePriors` exposes prior scope and sufficient
statistics. Sparse-role fallback is not a true role-specific fit.

## Similarity and spatial fingerprints

`feature_weights(group_weights)` returns per-feature weights in FEATURES order.
Each group has default weight 1, divided by its feature count; thus each group's
total weight is equal, not its every feature. Weights must be nonnegative.

```text
w_feature = group_weight / number_of_features_in_group
cosine(a,b) = sum(w*a*b) / sqrt(sum(w*a*a) * sum(w*b*b))
```

Multiplying vectors by the full weight before ordinary cosine would square the
weights and is incorrect. `weighted_cosine` returns a signed float in [-1,1],
or `None` for zero norms, all-zero weights, or nonfinite vectors. Negative raw
values are legitimate for centered metric profiles. Display transforms do not
change cosine distance (`1 - cosine`) or neighbor ordering.

### Display mapping handoff

The two possible displays are different contracts:

| Raw cosine | Signed display `100 * cosine` | 0-100 index `50 * (cosine + 1)` |
| --- | --- | --- |
| -1 (opposite) | -100 | 0 |
| 0 (orthogonal) | 0 | 50 |
| 1 (identical direction) | 100 | 100 |

**Integration flag:** the main handoff reported the API's chosen mapping as
`50 * (cosine + 1)`, but the checked-in `api.py` inspected at this handoff uses
`round(score * 100, 2)` for `displaySimilarity`, and its `meaning` field says
signed cosine x 100. The UI table, scout memo, and CSV export in `src/App.tsx`
also use signed cosine x 100. Thus the observed checkout is consistently signed;
it does not implement the reported 0-100 API index. These consumer files are
outside this worker's ownership and were not modified.

If main adopts the 0-100 index, change the API mapping and meaning, UI labels,
score bar, memo, and CSV field name/values together. Keep raw cosine and distance
available; do not remap `weighted_cosine`, stored z vectors, retrieval results,
or Jaccard values. Undefined cosine stays unavailable, not index 50. Nonnegative
spatial vectors have cosine >=0, so their affine index occupies 50-100; 50 does
not mean a 50% chance of anything. Never compare scores from different mappings
as if they were on the same scale.

Neither display is **player quality, a percentile, a probability, or a
transfer-fit forecast**. A 0-100 index is merely an affine transformation of raw
cosine, not a calibrated percentage. Regression tests pin raw cosine endpoints
and their distinct presentation values without changing the model output.

For spatial style, aggregate raw counts first. Add 0.01 to each bin of an
**observed** action block and independently L1-normalize that block. Concatenate
the three blocks, then use ordinary cosine. This is not cosine on raw event
counts and is not a pass/carry/pressure volume mix. An entirely empty block stays
zero rather than inventing locations; see `emptyStyleBlocks`. Missing blocks
still affect vector comparison and require cautious interpretation. The small
pseudocount deliberately smooths sparse bins and has more influence on tiny
samples. There is no learned spatial embedding or SoccerMix reproduction claim.

Rank ties use higher candidate minutes, then lower provider ID, consistently
with the existing frontend. Goalkeepers never enter these comparisons.

## Actual evaluation, not illustrative scores

`testPerformance` separately aggregates TRAIN and TEST; both use the same TRAIN
priors and fitted transforms. Queries must have >=90 minutes in both windows,
the same dominant role in both, and preferably >=2 appearances in each. Use the
two-appearance cohort if any eligible query has at least two potential training
peers; otherwise relax to one appearance and report that relaxation explicitly.

Rank each TEST query against all eligible TRAIN profiles of the same role,
including its own TRAIN identity and training-only players. Report actual top-1
and top-3 identity retrieval separately for metric and spatial representations.
Skip undefined self-vectors and pools with fewer than two rankable candidates;
never report a one-candidate pool as perfect performance. Candidate counts and
skipped/evaluated IDs are retained. Uniform-ranking chance is averaged per query:
`1/N` for top-1 and `min(3,N)/N` for top-3. Tiny pools make top-3 easy or trivial.
No valid queries means `status="unavailable"` and null rates, not zero accuracy.

This is a **same-player temporal style-stability proxy, NOT transfer quality**.
Team tactics, opponents, tournament-stage shifts, and unequal exposure remain
confounders. It does not validate causal quality, cross-league transportability,
replacement success, or suitability for any current club system.

`neighborhood` uses the union-window default target: most minutes among players
with >=270 minutes (ID breaks ties). Its pool is other same-role >=270-minute
players with defined metric and spatial comparisons. No eligible target/pool
means unavailable. For that identical pool it reports:

- Metric vs spatial top-5 neighbor IDs, overlap count, and Jaccard set agreement.
- Five weight perturbations: double one group, leave the other four at 1,
  keep the same z transforms, and compute Jaccard@5 against the default metric set.
- `effectiveK` and `membershipTestInformative`: with <=5 candidates, all top-5
  membership sets coincide regardless of ranking, so Jaccard is uninformative.

Jaccard is intersection / union, not rank correlation. With fewer than five
neighbors it uses the actual sets, never synthetic/padded candidates. Descriptive
union-window neighborhood analysis is distinct from held-out retrieval.

## Match-cluster uncertainty

`xtInterval` is a 90% percentile interval for **raw** xT/90. For each player,
resample complete observed player-matches with replacement, preserving paired
xT and minutes. Calculate `90 * total_xT / total_minutes` for each replicate,
not the mean of per-match rates. Use 300 draws, NumPy `default_rng(42)`, and
linear 5th/95th percentiles. Sort match IDs and restart the RNG per player so
results do not depend on input order or another player's presence.

Fewer than two unique positive-minute matches -> `null`. Identical match rates
can legitimately yield a zero-width interval. These are small-sample descriptive
intervals, not future-performance guarantees: they omit xT fitting uncertainty,
provider error, team/opponent dependence across matches, and exposure error.

## Diagnostics and verification

Diagnostics contain only JSON primitives: `metrics`, numeric `featureCount`,
`groups`, `featureWeights`, measured `counts`, fixed `parameters`, `split`,
`rolePriors`, `roleModels`, `testPerformance`, `eligibleIDs`, `neighborhood`,
`zeroPassPlayerIDs`, `emptyStyleBlocks`, `interpretation`, and `evaluation`.
`eligibleIDs` means union-window >=270-minute players, not verified transfer
candidates. The presentation-ready `evaluation` list matches Evidence's
`{name,value,detail}` schema and derives every numerical result from this call.
Full diagnostics should be retained to audit denominators and fallback scopes.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_similarity.py -q -p no:cacheprovider
```

Tests use clearly synthetic fixtures only: weighted cosine and group weighting,
raw-cosine versus signed/affine presentation endpoints,
shrinkage algebra, count/exposure denominators, exclusions, strict train-only
fitting, sparse-role fallback, constant features, independent spatial blocks,
seeded match-bootstrap ratios, temporal retrieval/chance denominators, role
changes, weight sensitivity, deterministic plain JSON, and invalid inputs.
Test fixture retrieval numbers must never be published as empirical results.

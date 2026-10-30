# Bounded Tracking Worker

`pipeline.tracking.build_tracking(rawdir: Path)` returns `(tracking, metadata)`.
It never writes files. Only SkillCorner supplies public player/frame records.
Metrica is parsed locally and returns aggregate validation and control summaries
under `metadata["metrica"]`; its positions are never returned.

## Inputs and Provenance

- `skillcorner_match.json`: [official match 1899585 metadata](https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches/1899585/1899585_match.json).
- `skillcorner_phases.csv`: [official phases](https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches/1899585/1899585_phases_of_play.csv).
- `skillcorner_tracking.jsonl`: a first-five-minute prefix of [official Git LFS media](https://media.githubusercontent.com/media/SkillCorner/opendata/master/data/matches/1899585/1899585_tracking_extrapolated.jsonl).
- `metrica_metadata.xml`, `metrica_tracking.txt`: [Metrica Sample Game 3](https://github.com/metrica-sports/sample-data/tree/master/data/Sample_Game_3), full input or a consecutive prefix starting at frame 1.
- `vendor/Metrica_PitchControl.py` and `vendor/LAURIE_LICENSE` (or `vendor/LICENSE`): [official LaurieOnTracking reference](https://github.com/Friends-of-Tracking-Data-FoTD/LaurieOnTracking).

The main fetch manifest owns immutable source revisions, URLs and hashes. The
worker does no networking. SkillCorner 1899585 is Auckland FC versus Wellington
Phoenix FC, December 7, 2024, Australian A-League 2024/25. Metrica is a separate
anonymized match. Neither is the match behind any StatsBomb event view. Never
join providers by time, player name or a shared numeric identifier.

## Public Contract

One `Tracking` item is emitted with `source="SkillCorner"`, `dataset="1899585"`,
`fps=2`, `pitch=[104,68]`. Native tracking is 10 Hz. There are exactly 20 frames
at 3.0, 3.5, ..., 12.5 seconds, all inside the first published in-play phase
(source frames 11 through 201). This is a 9.5-second excerpt, not a full match.

All positions are centered **meters**, x along pitch length and y across width.
SkillCorner coordinates are already in that system and are not scaled to 105 m.
The UI can map x to `(x/104 + 0.5)*100` percent. Positive y is up on a conventional
pitch: screen y is `(0.5 - y/68)*100` percent. Velocities are m/s in the same axes.
Player `team` is `Home` or `Away`; team display names live on the Tracking item.
Join source `player_data[].player_id` to metadata `players[].id`, then `team_id`.
Do not use metadata `trackable_object` for this join.

The only required TypeScript addition is `detected: boolean` on
`TrackingPlayer` (or optional for compatibility). False means extrapolated /
not detected, not a missing player. Every emitted player preserves this flag.
`control` has **10 rows by 16 columns**, cell centers left-to-right with x and
bottom-to-top with y. Its value is **Home control**, irrespective of possession.
If rendering with screen y increasing downwards, reverse the heatmap row order.
`massError` is the maximum unrounded per-cell `abs(1 - home - away)`, not a mean.
The separately calculated away surface is used for QA, not published as positions.

`metadata` contains `checks`, `skillcorner`, `sensitivity`, `metrica`,
`methodology`, and `limitations`. Checks use `{name, passed, detail}` for merging
into the existing Evidence contract. Detailed sensitivity and Metrica aggregates
can be kept in the build report or projected into Evidence evaluation rows.

## Model and Numerical Checks

The adapter calls the imported reference `initialise_players` and
`calculate_pitch_control_at_target`. It does not substitute a nearest-distance
or Voronoi proxy. Reference defaults include reaction time 0.7 s and maximum
model running speed 5 m/s. Goalkeepers are identified from source metadata.
Home is always the reference's first/attacking population; Away is the second /
defending population. The implementation's defending-goalkeeper control advantage
is therefore asymmetric. This is a reference-model convention, not observed
possession. **Offside filtering is explicitly disabled.**

Native-rate finite-difference velocities receive a centered five-sample mean.
Segments break at missing frames, period changes, detected/extrapolated changes,
or displacements implying speed greater than 12 m/s. Smoothing never bridges a
break. Unavailable segment velocities fall back to zero, with counts reported.
The 12 m/s preprocessing guard is separate from the reference's 5 m/s model
parameter. Both are assumptions, not player-specific calibrated measurements.

Every grid cell must have finite probabilities in [0,1] for both populations,
and absolute mass residual at most the reference tolerance (0.01). Values are
not clipped or renormalized. Failed identities, ordering, incomplete keyframes
or failed integration raise errors instead of silently producing synthetic data.

Sensitivity uses the 8.0-second reference frame with reaction time changed to
0.5 and 0.9 s, all else fixed. It reports mean and maximum absolute surface
changes plus grid-mean Home control. These are parameter variations, **not
accuracy, predictive validation, or football-model calibration**.

## Metrica Local Checks

`kloppy.metrica.load_tracking_epts` reads at most 5000 native 25 Hz frames using
the `metrica` coordinate system. All source frame IDs are scanned without
retaining rows, with a hard cap of 200000 lines. Counts distinguish available
prefix frames, loaded frames, and expected full-match frames from XML half ends.
Consecutiveness, finite coordinate counts, unpositioned roster entries, invalid
coordinates, missing active-player slots, missing ball frames and outside-pitch
counts are reported separately. Bench players without position channels are
unpositioned roster entries, not corrupt active-player coordinates. Outside-pitch
positions can be legitimate and are not clipped. Normalized points are converted locally to
centered 105 x 68 m coordinates, with y inverted to match the model axes.

A complete ball-observed frame near 10 seconds with valid native velocities
produces one aggregate grid-mean Home/Away control summary where feasible.
It is a different-match implementation comparison, not a paired benchmark.
No Metrica players, positions, ball trajectories or grid arrays are returned.
Missing optional source files or kloppy are explicit `unavailable` statuses;
malformed supplied data are errors. SkillCorner scanning is capped at 4000 lines.

## Publication and Tests

Retain [SkillCorner's MIT notice](https://github.com/SkillCorner/opendata/blob/master/LICENSE)
and credit SkillCorner on the public view. Preserve the LaurieOnTracking MIT
notice for the vendor model. Metrica's [README legal terms](https://github.com/metrica-sports/sample-data#legal-stuff)
request acknowledgement but give no formal redistribution license; this worker
intentionally returns no row-level Metrica data. StatsBomb has its own separate
agreement and must not inherit SkillCorner or code-license permissions.

Run `.venv/Scripts/python.exe -m pytest tests/test_tracking.py -q` from the root.
Synthetic tests cover native velocity estimation, gaps, coordinate/identity
adaptation, strict probability/mass checks, and sensitivity semantics. Optional
integration tests read the existing ignored raw cache and validate the exact
public contract and Metrica aggregate-only boundary. No test downloads data.

## Observed Local Source Run

The supplied cache contained 3011 SkillCorner JSONL frames, including ten initial
null-period frames. The first-phase smoothing context retained 197 native frames
and 4334 player samples. All 20 output frames contain 22 players: 440 output
player samples, of which 388 are detected and 52 extrapolated. No output velocity
needed the zero fallback. Both source goalkeepers were identified. Maximum
cellwise probability-mass residual was 0.00999878583302239 (reference tolerance
0.01); probabilities were not renormalized.

At 8 seconds, reaction-time sensitivity mean absolute control changes were
0.02018462 for 0.5 s and 0.02034864 for 0.9 s. Maximum cell changes were 0.14654161
and 0.13963313 respectively. These are changes in probability, not accuracy.

The Metrica cache was a 5000-frame prefix (200 seconds at native 25 Hz), versus
143761 frames expected for the full source match. All 5000 loaded consecutively,
with 110000 finite player samples, zero missing active-player slots, 65000
unpositioned roster entries, 1611 missing-ball frames and 410 outside-pitch player
samples. A complete valid frame nearest 10 seconds occurred at 14.4 seconds:
mean Home control 0.53085411, mean Away control 0.46527493, maximum cellwise mass
residual 0.00996152. The grid means need not sum exactly to one because the
reference leaves a bounded unresolved integration residual. These numbers
describe separate matches and do not establish calibrated accuracy.

## Remaining Caveats

- Centered differences and centered smoothing use subsequent native samples.
  This is offline analysis, not a causal real-time tracking/control service.
- The model is planar: source ball height is not used for aerial flight,
  headers, interception height or catch feasibility. Constant ball speed and
  shared player parameters are reference assumptions, not fitted observations.
- The defending-goalkeeper advantage applies to Away with Home fixed as the
  first population. Do not describe this display as possession-conditioned
  control or an invariant team comparison.
- Numerical conservation is checked against a 0.01 residual tolerance. Passing
  that check does not establish agreement with football outcomes or tracking
  ground truth; the unresolved residual is not silently assigned to either team.
- The first-phase 20-frame excerpt has no population-level sampling or outcome
  validation. Broadcast extrapolation and unverified identity errors remain.
- Synthetic tests check implementation behavior, not model calibration. Real
  source tests skip when ignored fixtures or the vendor reference are absent;
  the release run must supply them and confirm the integration tests execute.
- Metrica's prefix checks and separate-match aggregate are not full-match QA,
  cross-provider synchronization, or a license to publish its raw trajectories.

# Historical player comparison research

**Decision:** use this tool to choose questions for video review, not to approve a signing. The tournament sample is too short, old, and context-dependent to justify a current recruitment recommendation.

## The question

For a centre-back style comparison, who resembles Nicolas Otamendi in the 2022 World Cup sample? Use the default five equally weighted feature groups, same-role comparisons, and at least 270 stoppage-inclusive minutes. Otamendi has 786 measured minutes across seven appearances. All quantities below are derived from StatsBomb Open Data.

## Initial candidates

| Candidate | Team | Minutes | Signed cosine x 100 | Progressive passes / 90 | Successful-move xT / 90 | 90% match-bootstrap xT interval |
|---|---|---:|---:|---:|---:|---|
| Joe Rodon | Wales | 308 | 80.28 | 3.21 | 0.01798 | 0.01507 to 0.02084 |
| Ruben Dias | Portugal | 400 | 79.92 | 7.65 | 0.02878 | 0.00868 to 0.04798 |
| Walker Zimmerman | United States | 313 | 74.40 | 5.75 | 0.03845 | 0.01229 to 0.05599 |

These are measured-profile neighbors, not the three best defenders. A percentage sign in the UI means cosine multiplied by 100, not an 80% chance of success. The ranking uses shrunken role-normalized metrics; the table's rates and bootstrap intervals are unshrunk. Minutes include stoppage time.

## Why I would not act on the first ranking

Rodon's overall vector resembles the reference, but his progressive passing rate is substantially lower than Dias's. Is that a role difference, a possession/context effect, or a genuine limitation for the intended system? The model cannot answer alone. I would request video of pressured build-up actions and comparable defensive situations before deciding whether either player fits the intended role.

Changing the model changes the question: the top-five metric and spatial lists have **zero overlap** for this reference. Doubling the defending or security group leaves only four of the original five candidates, a Jaccard overlap of 0.667. This is a useful warning against treating a default weighted index as objective truth. The UI exposes both models and weights rather than hiding that sensitivity.

## How much should we trust the methods?

The temporal check attempts to retrieve each player's identity in later matches from earlier measured profiles. There are 76 eligible same-role queries. Metric top-three retrieval is 18.4%, spatial top-three is 31.6%, versus a pool-adjusted random baseline of 3.7%. This supports limited style persistence; it is not an evaluation of recruitment quality. Team progression into knockout rounds changes the population and opponents.

The 16 x 12 xT model's held-out Brier score is 0.017578 versus 0.017675 for a constant baseline. The coarser grid scores 0.017569. That marginal gain does not establish superior predictive performance, and the finer grid is not justified by this diagnostic alone. Successful-move xT also omits the full cost of unsuccessful actions and most defensive value.

## What the tracking view adds

It demonstrates the mechanics of actual positions, native-rate velocities, and competing-arrival control probabilities. It uses a different SkillCorner match and cannot explain Otamendi or validate this shortlist. Twenty keyframes, an uncalibrated model, goalkeeper asymmetry, disabled offside filtering, and extrapolated broadcast positions limit interpretation. Metrica validates a separate adapter, not this match's ground truth.

## Next useful work with a club

Define the intended tactical role with scouts and coaches; obtain authorized multi-season event and tracking coverage; compare league and team-possession adjustments; collect blind video assessments; then evaluate whether the tool improves review efficiency and decision consistency. Those are prospective tests, not claimed business outcomes of this portfolio.

Reproduction: `public/data/workspace.json`, `api.py`, `pipeline/similarity.py`, and `artifacts/evidence.json`. Provider numeric IDs: reference 3090; candidates 11250, 5206, and 12524. See `THIRD_PARTY.md` for attribution and data terms.

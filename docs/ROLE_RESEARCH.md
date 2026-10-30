# Role and project selection

## Target

LA Galaxy Associate Data Scientist, Soccer Operations. Supplied hiring post emphasizes recruitment, opposition preparation, player development, player similarity, tracking data, possession value, and pitch control. Publicly archived full role additionally emphasizes Python/SQL, model testing, reliable data workflows, concise reports for coaches/scouts, and React interfaces. Sponsorship is unavailable. An older public listing is closed; a fresh DM should ask for current details.

## What the public evidence suggests

The [club's Ravi Ramineni biography](https://www.lagalaxy.com/club/coaches/Ravi-Ramineni) describes his remit across coaching, high performance, and Soccer Operations. A [Sounders interview](https://www.soundersfc.com/news/big-data-how-seattle-sounders-use-analytics-driving-field-performance) emphasizes nuanced explanations in coaches' language and translating findings into repeatable actions. A [Barca Innovation Hub interview](https://barcainnovationhub.fcbarcelona.com/blog/ravi-ramineni-and-ashmeet-anand-data-can-lead-to-homogeneity-in-the-game-but-that-enhances-human-creativity/) stresses nonlinear player development and supporting, not automating, judgment. These support an inference about useful portfolio signals; they are not inside knowledge of LA Galaxy systems or hiring criteria.

## Concepts considered

Scores are design judgments, not measured recruiter preferences. Weights: alignment 30, distinctiveness 15, depth 15, demonstrability 15, feasibility 10, evidence 10, data suitability 5.

| Concept | Alignment | Distinctiveness | Depth | Demo | Feasibility | Evidence | Data | Weighted score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Touchline recruitment, xT, and tracking workbench | 5 | 5 | 5 | 5 | 4 | 5 | 4 | 97 |
| Standalone public-data xG prediction notebook | 3 | 2 | 3 | 2 | 5 | 4 | 5 | 62 |
| Broadcast-video player tracker | 3 | 4 | 4 | 4 | 2 | 3 | 2 | 65 |

Selected: Touchline Decision Lab. It closes the domain evidence gap and makes modeling decisions inspectable. A complete historical competition supports role-normalized comparisons; a separate real tracking sample supports a spatial-control laboratory.

## Scope and acceptance

- Reproduce all displayed values from public source data and a versioned build.
- Use established soccer parsing and xT/pitch-control references, with credits and license terms.
- Compare players only within a historical competition and role; expose minutes, shrinkage, feature weights, and small-sample limits.
- Separate successful-move xT from total player quality, match outcome forecasts, and transfer valuation.
- Show supported aggregate passing lanes and actual tracking positions with the correct provider's coordinate conventions. Raw StatsBomb sequences are not redistributed.
- Keep StatsBomb events, Metrica samples, and SkillCorner samples separate. Do not invent cross-provider match links.
- Test coordinate bounds, probability bounds, data joins, model split isolation, and sensitivity.
- Ship a restrained, functional recruitment/match research interface, source documentation, and measured evidence suitable for a public portfolio.

## Architecture

Public sources -> cached ingestion -> validated provider adapters -> SPADL/xT and role features -> reproducible JSON/SQLite -> React research workspace. Python supplies analysis; browser filters and reranks existing measured features. No private keys, private player data, or live paid providers are required.

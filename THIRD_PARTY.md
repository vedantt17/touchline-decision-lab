# Sources and rights

Original integration, analysis, tests, and interface are MIT licensed. That does not relicense data or upstream implementations. No affiliation with LA Galaxy, its employees, or data providers is implied.

| Source | Use | Terms and notice |
|---|---|---|
| [socceraction](https://github.com/ML-KULeuven/socceraction) | StatsBomb parsing, SPADL conversion, expected threat | MIT; installed dependency; upstream license applies |
| [LaurieOnTracking / Friends of Tracking](https://github.com/Friends-of-Tracking-Data-FoTD/LaurieOnTracking) | Laurie Shaw's pitch-control reference implementation, vendored without algorithm changes | MIT; `vendor/Metrica_PitchControl.py` and `vendor/LAURIE_LICENSE` |
| [kloppy](https://github.com/PySport/kloppy) | Local Metrica EPTS adapter | BSD-3-Clause; installed dependency; upstream license applies |
| [soccermix](https://github.com/ML-KULeuven/soccermix) | Inspiration for spatial style profiles | MIT repository; no code copied and not a reproduction of its factorization method |
| [StatsBomb Open Data](https://github.com/hudl/open-data) | 2022 World Cup research aggregates | Noncommercial published analysis, StatsBomb name and logo attribution; raw redistribution prohibited. Original terms in `docs/STATSBOMB_DATA_LICENSE.pdf` |
| [SkillCorner Open Data](https://github.com/SkillCorner/opendata) | Separate historical tracking sample | MIT repository notice in `vendor/SKILLCORNER_LICENSE` |
| [Metrica Sports sample data](https://github.com/metrica-sports/sample-data) | Local loader validation and aggregate diagnostics | No blanket redistribution license assumed. Raw and transformed position rows are not published. |

The StatsBomb logo is a provider credit, not this project's branding. Raw source files and local SQLite/pickle outputs are ignored by Git. Public event displays are coarse, supported aggregates (minimum five moves), not source event exports. Source repository revisions, paths, hashes, and download URLs are recorded in `data/source_manifest.json`. Read provider terms before any commercial use.

The xT framework is credited to [Karun Singh](https://karun.in/blog/expected-threat.html); the control model follows the Spearman-style competing-arrival approach implemented by Laurie Shaw. This project does not claim those algorithms as original research. AI coding tools assisted development and testing; outputs were checked against source data and automated validation.

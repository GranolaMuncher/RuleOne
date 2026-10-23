---
date: 2026-10-23
mode: method
status: fixed-on-branch
workflow: Engineer (method)
branch: engineer/2026-10-23-dossier-marker-lines, engineer/2026-10-23-lender-payback-tencap, engineer/2026-10-23-negative-eps-windage
---
# Method run: all three pending proposals implemented on separate branches

**What happened.** Three Professor proposals were pending in `knowledge/rule1/METHOD.md` (2026-10-09, two from 2026-10-10). None was implemented on the open `engineer/2026-10-18-sane-shares-ni-scale` branch. Each now has its own branch with a test and a separate commit marking the item "(implemented on branch …)".

**Root cause / what each does.**
1. *Dossier marker lines (10-09).* The universe CSV already carries `markers` (`name=1|0|?`), so that half needed no change. `ruleone/rulers.py` now has `marker_gaps()`: `record()` writes `markers_missing` per ticker to `research/rulers/index.json`, and the weekly memo lists dossiers with no ✔/✘/? line for a marker.
2. *Lenders (10-10).* `is_lender()` in `ruleone/valuation.py` matches SIC industries (Personal/Business Credit, Mortgage Bankers, Loan Brokers) plus a ticker list for platforms filed under SIC 6199 (OPFI, QFIN, SOFI, UPST, SYF, LC, MFIN). For these, Payback and Ten Cap are `None` in both the detailed screen and the universe table, so they drop out of "methods agree" and BUY* cannot come from them. A flag explains why. Sticker and MOS were already earnings-based. The ticker list is a judgement call; extend it if you see other platforms.
3. *Negative Street EPS (10-10).* `street_capped_growth()` caps windage at the analysts' current-year EPS growth when it is negative (from `lists/latest/analysts.csv`). The result is no Sticker (growth ≤ 0) and a "rebase needed" flag, instead of 15% history-based growth. It applies to the detailed screen and the RULERS fact pack. The all-stocks FY rows are unchanged.

**Fix.** Tests added: `test_marker_gaps_flags_dossier_without_per_marker_lines`, `test_lenders_get_no_payback_or_ten_cap`, `test_negative_street_eps_growth_caps_windage`. On each branch `python3 -m pytest -q tests` passed (58, 58, 58), and `actionlint` is clean. `site/` was not touched, so no build was run.
- https://github.com/GranolaMuncher/RuleOne/compare/claude/dazzling-knuth-dmucvz...engineer/2026-10-23-dossier-marker-lines?expand=1
- https://github.com/GranolaMuncher/RuleOne/compare/claude/dazzling-knuth-dmucvz...engineer/2026-10-23-lender-payback-tencap?expand=1
- https://github.com/GranolaMuncher/RuleOne/compare/claude/dazzling-knuth-dmucvz...engineer/2026-10-23-negative-eps-windage?expand=1

**Owner action.** Review and merge the three branches. Branches 2 and 3 both edit `analyze()` and the import line in `ruleone/screener.py`, and each marks its own line in `METHOD.md`, so merge one and resolve a small conflict in the other. Nothing else is needed.

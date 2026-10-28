---
date: 2026-10-28
mode: method
status: fixed-on-branch
workflow: engineer
branch: engineer/2026-10-28-sbc-adjusted-prices, engineer/2026-10-28-peak-earnings-rebase, engineer/2026-10-28-debt-extraction
---
# Method run: SBC-adjusted prices, peak-earnings rebase and debt extraction implemented on three branches

**What happened.** Three proposals from the Professor (2026-10-24) were pending. Each is on its own branch, with a test and a second commit marking it implemented in `METHOD.md`. The branches are independent and all start from the default branch. Each edits `tests/test_screening.py` near the end and two edit `screener.py`, so merge them one at a time and expect a trivial conflict.

**Root cause / Fix.**
1. SBC (TTD, ADBE, INTU). The screener now reads `ShareBasedCompensation` and writes `payback_price_sbc`, `ten_cap_price_sbc` and `sbc_pct_ocf`. It flags any name above 10% of operating cash flow. The headline Payback and Ten Cap are unchanged. https://github.com/GranolaMuncher/RuleOne/compare/claude/dazzling-knuth-dmucvz...engineer/2026-10-28-sbc-adjusted-prices?expand=1
2. Peak earnings (PGR, KNSL). When TTM EPS is above 1.5× the 5-year average, the Sticker is computed on the average EPS and windage is capped at 10%. A flag and an `eps_vs_5y_avg` column are added. I chose the 10% cap, since the proposal did not give a number. The insurer combined-ratio test is not in XBRL and was not implemented. https://github.com/GranolaMuncher/RuleOne/compare/claude/dazzling-knuth-dmucvz...engineer/2026-10-28-peak-earnings-rebase?expand=1
3. Debt (SMCI, OPFI). The new `total_debt()` also reads convertible, revolver, secured and short-term borrowing tags. It takes the largest candidate total instead of adding them, to avoid double counting. It feeds `debt`, net debt, the Tier A debt test and the `low_debt` marker. I could not check it against live filings, so the tag list is a best guess. https://github.com/GranolaMuncher/RuleOne/compare/claude/dazzling-knuth-dmucvz...engineer/2026-10-28-debt-extraction?expand=1

Checks on each branch: `python3 -m pytest -q tests` passed (63–64 tests). Workflows and `site/` were not touched, so there was nothing for actionlint or the site build to check. I did not run actionlint against all workflows because the shell blocked the glob.

**Owner action.** Review and merge the three branches. After the next Saturday screen, check SMCI and OPFI `debt` against their 10-Ks.

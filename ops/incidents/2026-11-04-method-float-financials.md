---
date: 2026-11-04
mode: method
status: fixed-on-branch
workflow: -
branch: engineer/2026-11-04-float-financials
---
# Extend the lender rule to insurers and banks (2026-10-31 proposal)

**What happened.** ACGL, PGR, KNSL and AX showed 2 of 3 methods agreeing on Payback and Ten Cap built from operating cash flow that carries float or deposits.
**Root cause.** `is_lender` only covered loan platforms; insurers and banks were not excluded, and windage was not capped at Street growth when Street is positive (ACGL history 15% vs Street +3.9%).
**Fix.** `is_lender` now also matches SIC descriptions with Insurance (not Insurance Agents), Commercial Banks, Savings Institution, plus ticker AX. New `street_cap_float` caps windage at Street EPS growth for those names (never raises it) and adds a flag. Test `test_float_financials_are_lenders_and_capped_at_street`. Checks: pytest 68 passed, actionlint clean; no site change. Branch: https://github.com/GranolaMuncher/RuleOne/compare/claude/dazzling-knuth-dmucvz...engineer/2026-11-04-float-financials?expand=1
**Owner action.** Merge the branch. The proposal's last point, ACGL debt showing 0 against $4.29B in the 10-Q, is not fixed: diagnosing it needs ACGL's XBRL debt tags. Ask a Claude chat to inspect them.

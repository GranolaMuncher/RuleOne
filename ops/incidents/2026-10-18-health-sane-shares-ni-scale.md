---
date: 2026-10-18
mode: health
status: fixed-on-branch
workflow: weekly.yml
branch: engineer/2026-10-18-sane-shares-ni-scale
---
# Health 2026-10-18: `sane_shares` shrank correct share counts when a filer tagged net income in thousands

**What happened.** `share_scale_suspect` and `ten_cap_over_20x_price` were flagged again (ATEX, AVAH, BANR, AIT, CACC, ALTO, ATHS). `actionlint` is clean. Unlike the distressed rows I closed on 2026-10-11, some of these are real scaling errors. ATEX has price $80.48 but a market cap of 1.51 M (it should be about $1.57 B), a Ten Cap price of 5,631 and a Payback price of 4,610.

**Root cause.** The SEC frames give Anterix `NetIncomeLoss` = 90,635 and Aveanna 225,034, so thousands were tagged as USD. The cover-page shares are correct (ATEX 19,498,473; AVAH 218,219,696). `sane_shares` (`ruleone/metrics.py`) saw net income / EPS = 18.8 k, more than 100x below the cover count, and replaced the correct count with that wrong implied one. Market cap, Payback and Ten Cap were then about 1000x off. BANR and CACC show the same symptom (CACC at a 1e6 scale); I did not confirm their frames. AIT also shows it, but I found no cover-page count for AIT in the dei frames. Its fallback count appears to come from weighted average shares tagged in thousands. This fix does not repair AIT.

**Fix.** `sane_shares` now only raises a count that is 100x or more *below* net income / EPS (the Nova 20-F case it was written for). It never shrinks a count. I added a regression assertion with the Anterix shape to `test_sane_shares_fixes_scale_errors_only`. Checks run: `python3 -m pytest -q tests` (56 passed) and `actionlint` (clean). `site/` is untouched, so no build was needed. The next screen will show the effect on ATEX and AVAH. Rows with a corrected Ten Cap or Payback may change status, which is the intended correction.
https://github.com/GranolaMuncher/RuleOne/compare/claude/dazzling-knuth-dmucvz...engineer/2026-10-18-sane-shares-ni-scale?expand=1

**Not fixed.** AIT: both its share count and net income look to be in thousands, so nothing inside the row contradicts them. It is currently BUY* on a bad Payback and Ten Cap, though the sticker uses EPS and is fine. A guard would compare shares and net income against the scale of OCF and revenue. Left as a follow-up. ALTO, ATHS and the NO STICKER rows are real distress or structural cases, as noted on 2026-10-11.

**Owner action.** Open the PR from the link above to merge the fix. Say if you want the AIT-style scale guard.

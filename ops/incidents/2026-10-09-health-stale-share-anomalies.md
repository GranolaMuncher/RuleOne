---
date: 2026-10-09
mode: health
status: no-action
workflow: weekly.yml
branch: -
---
# Health 2026-10-09: weekly.yml failures already fixed; share-scale anomalies predate the `sane_shares` fix

**What happened.** Three problems were reported. (1) `weekly.yml` failed on the 07:22 and 07:29 pushes after 0 s with "likely failed because of a workflow file issue". (2) `share_scale_suspect` and (3) `ten_cap_over_20x_price` recurred for ACH, AHT, ATHS, CHR, CRMT, DDS, CABO, CISS.

**Root cause.**
1. The workflow file was broken when RULERS was wired in (screen job and inputs lost). Commit 8461a09 (07:32) restored it. `actionlint` is clean on all workflows now. No run has happened since, so the "last run failed" flag will persist until the next dispatch or Saturday cron.
2. and 3. The data in `lists/latest/universe.csv` is from the 2026-10-04 screen. `sane_shares` (the fix for mis-scaled share counts, e.g. Nova) only landed in 9cad854 on 2026-10-09 at 07:09. The listed rows show the signature it corrects: DDS has implied shares 15,655 against net income / EPS of 15.65 M, and NVMI has 32,800 against 32.6 M. CHR and CISS have the same ~1000x pattern. These should clear on the next screen. ACH, AHT, CABO, CRMT, PIII and HTZ have consistent shares (net income / EPS matches market cap / price). They are loss-making or distressed small caps, so the flags are real data, not a bug.

**Fix.** None needed. No code branch was created. Checks run: `actionlint` clean. I did not rerun pytest because no code changed.

**Open item for next health check.** ATHS has positive net income (2.7 B) but blank EPS and about 204 k implied shares. `sane_shares` returns early when EPS is missing, so it cannot correct this row. If ATHS is still flagged after the next screen, the fix is to fall back to a share count cross-check without EPS.

**Owner action.** Run "Weekly Rule One run" via workflow_dispatch to confirm the workflow starts and to refresh the data.

---
date: 2026-10-11
mode: health
status: no-action
workflow: weekly.yml
branch: -
---
# Health 2026-10-11: recurring share-scale and Ten Cap flags are real distressed or structural rows, not a scaling bug

**What happened.** The health check flagged `share_scale_suspect` (ACH, AHT, ATHS, CHR, CRMT, EH) and `ten_cap_over_20x_price` (ATHS, CHR, CISS, CRMT, FAMI, GDHG) as recurring. `actionlint` is clean. This screen (2026-10-10) ran after the `sane_shares` fix (9cad854), so the earlier "stale data" explanation no longer applies and I checked the rows in `lists/latest/universe.csv` directly.

**Root cause.** No scaling bug found.
- ACH, AHT, CRMT, EH, GDHG, FAMI: price down 80-95% over a year, net losses, market cap under 2% of sales. Where EPS is present, net income / EPS matches market cap / price, so share counts are consistent. The flags reflect real distress. All sit at `NO STICKER`, tier C, so they cannot reach BUY.
- CHR, CISS: both fell 96-99% over the year with reverse splits, so a high EPS next to a ~$1 price is plausible. CHR shares agree with net income / EPS (1.06 M vs 1.06 M). CISS market cap implies 0.35 M shares against 2.6 M implied by net income / EPS (about 7x), inside the 100x tolerance of `sane_shares`. That is probably a share-count basis mismatch around reverse splits, but it is not a clear bug and it only affects a micro-cap at `NO STICKER`.
- ATHS (Athene Holding): positive net income but blank EPS, about 204 k common shares. Apollo owns the common, and the traded security is a preferred depositary share, so market cap and Ten Cap (399,671) are meaningless. This is structural and not fixable by rescaling shares.

**Fix.** None, and no branch. Any gating would change what the screener concludes, and none of these rows can reach BUY. Checks run: `actionlint` clean (per task.md). pytest was not rerun because no code changed.

**Open item.** To quiet these in the health report, suppress `share_scale_suspect` when `net_income < 0` and `ten_cap_over_20x_price` when status is `NO STICKER`, and flag preferred-only listings such as ATHS. That is a policy decision, so I left it alone.

**Owner action.** None. Say if you want the health-check suppression above implemented.

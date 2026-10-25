---
date: 2026-10-25
mode: health
status: no-action
workflow: weekly.yml
branch: -
---
# Health 2026-10-25: recurring share-scale and Ten Cap flags are still distressed or structural rows, not a bug

**What happened.** `share_scale_suspect` (ACH, AHT, ATHS, BOXL, CHR, CRMT) and `ten_cap_over_20x_price` (ATHS, CABO, CHR, CISS, CRMT, ENLV) were flagged as recurring. `actionlint` is clean, all site pages return 200, and the build is at 32% of the Cloudflare file limit.

**Root cause.** No bug. Most names are the ones I cleared on 2026-10-11 (ACH, AHT, ATHS, CHR, CISS, CRMT). The 2026-10-18 `sane_shares` fix is on `engineer/2026-10-18-sane-shares-ni-scale` and is waiting for the owner to merge it, so the screen has not yet picked it up. I checked the names that are new to the recurring list in `lists/latest/universe.csv`:
- CABO: price $4.83, down 97% over the year, net loss of $357 M. Market cap 27.4 M / price implies about 5.7 M shares, which is right for Cable One, so the shares are not mis-scaled.
- BOXL: price down 96% over the year, net loss of $23.8 M, `NO STICKER`, tier C.
- ENLV: price $0.17, down 99%, a micro-cap, with a reverse-split adjustment already flagged. Its Ten Cap comes from a tiny OCF per share against a collapsed price.

All are tier C and cannot reach BUY.

**Fix.** None, and no branch. No code changed, so pytest and the site build were not rerun.

**Open item.** The 2026-10-11 suggestion still stands: suppress `share_scale_suspect` when net income is negative and `ten_cap_over_20x_price` when the status is `NO STICKER`, which would stop this weekly noise. It is a policy decision, so I left it alone.

**Owner action.** Merge the 2026-10-18 branch if you haven't. Say if you want the suppression implemented.

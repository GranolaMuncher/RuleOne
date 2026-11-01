---
date: 2026-11-01
mode: monthly
status: fixed-on-branch
workflow: -
branch: engineer/2026-11-01-monthly-deps
---
# Monthly dependency update: astro 7.4.4, marked 18.1.2

**What happened.** `npm outdated` listed two minor updates in `site/`: astro 7.3.5 → 7.4.4 and marked 18.0.14 → 18.1.2. `requirements.txt` uses open lower bounds (`requests>=2.31`, `pytest>=7`), so nothing to change there.
**Root cause.** Routine monthly refresh. No major bumps pending.
**Fix.** Bumped both in `site/package.json` and refreshed the lockfile (0 vulnerabilities). Checks: `pytest` 67 passed; `actionlint` clean; `npm run build` built 6,352 pages in ~17s. Branch: https://github.com/GranolaMuncher/RuleOne/compare/claude/dazzling-knuth-dmucvz...engineer/2026-11-01-monthly-deps?expand=1

**GitHub Actions (not changed, needs-owner).** I can't push workflow files. Versions in use: checkout@v4, setup-python@v5, setup-node@v4, cache@v4, upload/download-artifact@v4, claude-code-action@v1, wrangler-action@v3. Newer Node 24 releases may exist; I did not verify them from here, so the owner or a Claude chat should check and bump them if wanted.

**Capacity.** Cloudflare: 6,400 files (32% of the 20,000 limit), 140 MB site, build 16s. Repo: `.git` 16 MB, `lists/archive` 3.8 MB, far under the 200 MB pruning threshold, so no pruning is needed.

**Health items (no code fix this run).** The task's recurring anomalies (share_scale_suspect: ATHS, CHR, TOPS; ten_cap_over_20x_price: LX, TOPS) were not investigated in this monthly run. They are left for the next health run.

**Owner action.** Merge the branch if wanted. Optionally bump the Actions versions listed above.

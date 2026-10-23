---
date: 2026-10-23
mode: method
status: needs-owner
workflow: engineer
branch: engineer/2026-10-23-method-proposal-filter
---
# Method run saw no proposals because the filter matched "Not yet implemented"

**What happened.** The 2026-10-23 method run's `task.md` listed no proposals, but `knowledge/rule1/METHOD.md` has three (2026-10-09 markers per dossier, 2026-10-10 lenders/Payback, 2026-10-10 negative-EPS windage cap), each ending "Not yet implemented."
**Root cause.** `.github/workflows/engineer.yml` used `grep -v 'implemented'` (and `grep -vc` for the pending count), which also drops "Not yet implemented" lines. No proposal could ever be listed.
**Fix.** Both filters now match `implemented on branch`. pytest 57 passed, actionlint clean. No proposals were implemented this run, because `task.md` did not list them; the next method run will pick them up once this is merged. The branch `engineer/2026-10-23-method-proposal-filter` was committed locally but **the push was rejected**: GitHub refuses to let the app update `.github/workflows/*` without the `workflows` permission, so the branch is not on the remote.
**Owner action.** Apply the change by hand in `.github/workflows/engineer.yml` (lines ~111 and ~137): replace `grep -v 'implemented'` with `grep -v 'implemented on branch'` and `grep -vc 'implemented'` with `grep -vc 'implemented on branch'`. Then re-run the Engineer in method mode to implement the three proposals.

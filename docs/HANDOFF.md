# Handoff: continuing RuleOne in a new chat

Read this first in any new or forked Claude session, then `knowledge/MAP.md`.

- **Full conversation log** (private to the owner): https://claude.ai/artifact/VM51Nue4ALW6Ehprz1PowN. A new Claude Code session can read it with the Artifact tool's `read` action.
- **Original session:** https://claude.ai/code/session_011DSDHKWaPHXdGY3qpb3Mqj
- **Repo:** GranolaMuncher/RuleOne. The only branch is `claude/dazzling-knuth-dmucvz`, which is also the default. Push only there.
- **Site:** https://ruleone.pages.dev (Astro on Cloudflare Pages; `deploy-site.yml`)

## Standing rules from the owner
- Not investment advice. The repo and site are public.
- Never commit book text or podcast transcripts; transcripts stay in `.work/`.
- **No options strategies.** "Reduce basis" means equal-dollar tranche buying only.
- The agents never track private holdings. The Holdings page uses browser `localStorage` only.
- **No push or email notifications.** GitHub issues and PRs are opt-in via repo variables `EDITOR_ISSUES=true` and `ENGINEER_PRS=true`.
- *The Intelligent Investor*: use only the owner's own recordings, in the private repo `GranolaMuncher/ruleone-library` (see `docs/RECORDING.md` and `docs/LIBRARY.md`). Never use the pirated PDF or the Spotify audiobook. `LIBRARY_TOKEN` is a read-only token for that repo.
- **Commits:** no model IDs. End messages with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and a `Claude-Session:` line.
- **Local dev:** don't run `pkill -f "astro preview"`; it kills the shell. Kill the preview server by its port's PID instead.

## What exists
| Part | Code | Prompt | Workflow and schedule (UTC) |
|---|---|---|---|
| Screener (Big Five, Sticker/MOS, Payback, Ten Cap on owner earnings, methods agree, flags, 10 markers) | `ruleone/screener.py`, `marketwide.py`, `metrics.py`, `valuation.py` | – | `weekly.yml`, Saturday |
| Professor: InvestED (all 498 episodes noted) and book chapters | `ruleone/podcast.py`, `book.py`, `knowledge.py` | `agents/professor/PROMPT.md`, `CURATE.md`, `BOOK.md` | `professor.yml` daily 09:41; `professor-book.yml` daily 03:23 |
| Professor weekly review: marks dossiers, writes LESSONS, proposes method changes | `ruleone/scorecard.py` | `agents/professor/REVIEW.md` | `review.yml` (in the weekly chain) |
| Radar: news, filings, 13F guru moves, dossier sell triggers, analyst downgrades | `ruleone/radar.py` | `agents/radar/PROMPT.md` | `radar.yml`, weekdays 22:22 |
| Analyst consensus: low/mean/high targets, ratings, revisions; agree / contrarian / crowded | `ruleone/analysts.py` | – (feeds Radar, RULERS, Editor) | inside `radar.yml` (daily) and `weekly.yml` (broad pass) |
| RULERS analyst: living dossiers in `research/rulers/` | `ruleone/rulers.py` | `agents/rulers/PROMPT.md` | `rulers.yml` (in the weekly chain) |
| Editor: weekly brief, conflicts, decisions | `ruleone/editor.py` | `agents/editor/PROMPT.md` | `editor.yml` (in the weekly chain) |
| Engineer: failures, health, monthly upgrades, implements METHOD proposals on branches | `ruleone/health.py` | `agents/engineer/PROMPT.md` | `engineer.yml` Sunday 14:07 and on any workflow failure |
| CI | `tests/` (pytest), actionlint | – | `ci.yml` on push |

**Weekly chain (Saturday):** screen → analyst broad refresh → RULERS → Professor review → Editor → deploy.

**Knowledge relay:** `knowledge/MAP.md` lists who writes and reads each file. The method lives in `knowledge/rule1/METHOD.md`, `MARKERS.md`, `LESSONS.md` and `CHECKLIST.md`; the company → episode index is in `knowledge/index/`.

**Site pages:** Screen, All stocks, Radar, RULERS, Street, Holdings, Learn (podcast and book), Rule #1, Research, Archive, Ops. Stock pages show the markers, InvestED episodes, the analyst consensus and the dossier.

## Open items and known limits
- The owner is still recording *The Intelligent Investor*. 22 chapter previews are waiting for recordings.
- The three dossiers (ADBE, KNSL, LULU) predate the Markers section. The first Professor review flagged this, and next Saturday's RULERS run should add it.
- Banks and insurers fit the cash-flow markers poorly. IFRS (foreign) filers aren't covered.
- Analyst data comes from Yahoo Finance; TipRanks and MarketBeat forbid scraping. Yahoo no longer gives a 5-year growth estimate, only this year and next.
- The scorecard needs months of graded calls before it says much.
- If Claude usage limits are hit, agent runs stop cleanly and resume on the next schedule.

## Checks before any push
```bash
python -m pytest -q tests
actionlint -shellcheck= .github/workflows/*.yml
cd site && npm ci && npm run build
```

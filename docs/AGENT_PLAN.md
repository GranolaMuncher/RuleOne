# RuleOne agent stack: plan

Status: **proposed**, not yet built. This file is the hand-off spec, so any session or agent can implement it without this conversation's context.

## Design principles

1. **No "boss" LLM.** Orchestration is deterministic: GitHub Actions schedules and job dependencies decide what runs when. An LLM manager adds cost, latency and a new failure mode, and does nothing a workflow graph can't. The one coordinating role is an **Editor** step at the end of the weekly run. It reads every agent's output, reconciles conflicts and writes the weekly brief. It does not control the other agents.
2. **Agents are stateless; the repo is the memory.** Each run starts fresh, reads its inputs from files, writes its outputs to its own folder and exits. No run depends on a long conversation, which removes context-window limits. Knowledge accumulates in `knowledge/`, dossiers in `research/`.
3. **One folder per agent.** An agent may *read* anything but *writes* only its own folder. Code changes (`ruleone/`, `site/`, workflows) go through pull requests from the Engineer, never straight to the default branch.
4. **Python does the math; LLMs do the judgement.** Screening, valuation, prices and filings stay in deterministic code (`ruleone/`). Agents interpret, research and write.
5. **Research, not advice.** Nothing places trades. Every output carries the not-investment-advice line.

## The stack

| # | Agent | Role | Trigger | Model (suggested) | Writes to |
|---|---|---|---|---|---|
| 0 | **Data engine** (exists, no LLM) | Whole-market screen, valuation, prices, dividends, sectors | Sat 11:17 UTC | none | `lists/` |
| 1 | **News & Events: "Radar"** | Daily news, filings and earnings digest for the watchlist; classifies each event as temporary or moat-damaging | Mon–Fri ~22:30 UTC (after close), plus Saturday weekly roll-up | Haiku 4.5 for triage, Sonnet 5.5 for the digest | `research/news/` |
| 2 | **RULERS analyst** | Applies the RULERS framework to the top candidates; maintains one living dossier per stock; runs the valuation engine | Saturday, after Data engine and Radar | Sonnet 5.5 (Opus 5.5 for new deep dives) | `research/rulers/`, `reports/config/` |
| 3 | **Methodology professor: "Professor"** | Builds and maintains the knowledge base (InvestED, Rule #1, Buffett/Munger, *The Intelligent Investor*); reviews RULERS dossiers for methodology errors | Sunday ingest; Saturday review step | Opus 5.5 | `knowledge/`, review notes in `research/reviews/` |
| 4 | **Site & repo engineer: "Engineer"** | Keeps the pipeline green, checks data quality, fixes bugs, keeps the site building, and updates dependencies | On any workflow failure; weekly health check; monthly dependency check | Sonnet 5.5 | Pull requests only; `ops/health/` |
| 5 | **Editor** (coordinator) | Reconciles agents 1–3, resolves disagreements, writes the weekly brief and the action list, decides escalations | Saturday, last step before deploy | Sonnet 5.5 | `reports/weekly/` |
| 6 | **Holdings page** (not an agent) | You enter tickers and buy prices on [/holdings/](https://ruleone.pages.dev/holdings/); the page checks each one against the weekly data and shows dangers and insights. Stored only in your browser. No alerts, no push or email | Every page load | none | browser `localStorage` |

### Weekly flow (Saturday)

```
Data engine ──► Radar weekly roll-up ──► RULERS analyst ──► Professor review ──► Editor brief ──► Deploy site
   (lists/)        (research/news/)       (research/rulers/)  (research/reviews/)  (reports/weekly/)
                                                   ▲
                         Professor ingest (Sunday) ┘  knowledge/ feeds every Saturday run
Engineer: on failure of any step, and a health check after deploy
```

Weekdays: Radar runs nightly and appends to `research/news/<date>.md`. If an event hits a stock already in buy range or on deck, it opens a GitHub issue labelled `event` No push or email notifications for now.

## Agent specs

### 1. Radar: news and events

**Watchlist:** everything in `lists/latest/{buy_range,buy_range_alt_methods,on_deck,event_watch}.csv`, all tier A names more than 20% off their high, plus `research/watchlist.txt` (your manual adds).

**Each run:**
1. For each watchlist name, gather new information since the last run:
   - 8-K items and Form 4s (from the EDGAR submissions data the screener already pulls)
   - earnings releases, guidance changes, analyst rating and target changes
   - management changes, litigation, regulatory actions, and macro items that directly affect the business
2. Classify each event as `temporary` (cyclical, one-off, sentiment), `structural` (moat or management damage), or `unclear`, with a one-line reason and a source link.
3. Write `research/news/<date>.md`, a human digest grouped by severity, and `research/news/<date>.json`, structured records: ticker, date, type, class, headline, source, price reaction.
4. Saturday: a weekly roll-up `research/news/week-<date>.md` that the RULERS analyst reads.

**Guardrails:** cite every claim and prefer primary sources (SEC, company IR). Never infer events without a source. Keep it short: the nightly digest stays under one page.

### 2. RULERS analyst

**Input:** screen lists, Radar roll-up, `knowledge/` (methodology), existing dossiers, `reports/config/*.json`.
**Scope per week:** top ~10 by `rank_score` in buy range plus alternate methods, any watchlist name with a new `structural` or `temporary` event, and anything you add to `research/watchlist.txt`.

**Per stock, maintain `research/rulers/<TICKER>.md`**, a living dossier updated in place with a dated changelog at the bottom:

| Section | Content |
|---|---|
| **R: Radar** | Why it's on the list (screen tier, Big Five, price vs Sticker/MOS, drawdown, flags) |
| **U: Understanding** | The business in three sentences; how it makes money; circle-of-competence score 1–5, with what you would need to learn |
| **L: Love** | Meaning test: products, mission, management integrity, ESG issues. Would you own the whole company? Yes/no, with reasons |
| **E: Event** | The current event (from Radar), temporary vs structural, evidence for each side, what would prove it temporary |
| **R: Reduce basis** | Tranche plan: starter, add and full-position prices tied to the MOS, Ten Cap and Payback levels; when to stop buying. **Tranche buying only: no options strategies.** |
| **S: Story** | The thesis in one paragraph, three things that must stay true, and the sell-if-wrong triggers |
| **Numbers** | Sticker / MOS / Payback / Ten Cap (adjusted growth with reasoning), DCF summary from `python -m ruleone.deepdive`, dividend and total return |
| **Verdict** | BUY / ACCUMULATE / WATCH / AVOID, entry and trim levels, confidence 1–5 |

It creates `reports/config/<TICKER>.json` and runs the deep-dive engine for any new top-3 idea.

### 3. Professor: methodology expert

**Knowledge base:** `knowledge/`, kept small, structured and cited.

| Path | Content |
|---|---|
| `knowledge/rule1/` | The Rule #1 method: Big Five, 4Ms, Sticker/MOS, Payback Time, Ten Cap, windage growth, events, tranches, RULERS definitions |
| `knowledge/invested/episodes/<n>.md` | One note per InvestED episode: date, topics, key takeaways, any rule changes or nuances, quotes under fair-use length, link |
| `knowledge/buffett_munger/` | Principles from the Berkshire letters, Munger talks, mental models, the inversion checklist, each with a source |
| `knowledge/intelligent_investor/` | Graham's principles (Mr. Market, margin of safety, defensive vs enterprising investor, the net-net and defensive criteria), **in your own words or from your notes** |
| `knowledge/CHECKLIST.md` | The single consolidated checklist the RULERS analyst must apply. Every item links to its source note |
| `knowledge/CONFLICTS.md` | Places where the schools disagree, e.g. Town's 50% MOS vs Graham's margin of safety, or Buffett's "wonderful company at a fair price" vs Graham's cigar butts, and which one this repo follows |

**InvestED ingest (built):** [`professor.yml`](../.github/workflows/professor.yml) runs four times a day. `python -m ruleone.podcast prepare` downloads the next six episodes **in order** from the RSS feed and transcribes them on the runner with faster-whisper (`base.en`, about 4 minutes per 40-minute episode). Claude then follows [`agents/professor/PROMPT.md`](../agents/professor/PROMPT.md) and writes one study note per episode, with key ideas and timestamps, a RuleOne mapping, Buffett/Munger/Graham links, an exercise and a quiz. It also folds each episode into `knowledge/invested/course.json` (11 modules with a running lesson synthesis, plus a glossary). `record` marks progress in `progress.json`. Transcripts never leave the runner. The site renders the course at `/learn/`, where you can mark episodes studied (saved in your browser). The back catalogue (498 episodes, about 307 hours) takes about three weeks. After that, each run picks up new episodes. Update `CHECKLIST.md` when an episode adds or changes a rule.

**Saturday review:** read each new or changed RULERS dossier and flag methodology errors, for example:
- a growth rate above the lower of history and analyst estimates
- a MOS that ignores a structural event
- a "wonderful" label on a company with Big Five failures
- a Story with no sell triggers

It writes `research/reviews/<date>.md`. It answers "what would Buffett, Munger, Graham or Town say" questions with citations.

**Copyright:** do not commit book text or full podcast transcripts. The repo and site are public. Store summaries, short quotes and links only. Full texts (e.g. your ebook or transcripts) can sit in a **private** location the agent reads, but never in `knowledge/`.

### 4. Engineer: site and repo upkeep

**On workflow failure:** read the failed job log, reproduce locally, fix it, run `pytest` plus a site build, and open a PR with the root cause. Never skip tests or force-push. If the cause is an expired secret or an outside outage, open an issue explaining what you need to do.

**Weekly health check** (after deploy), written to `ops/health/<date>.md`:
- universe row count
- share of stocks with prices, Sticker and sectors
- new anomalies: P/E < 4, yield > 25%, total return > 100%/yr, Sticker jumps > 50% week on week, rows missing price
- site build time and page count
- live checks of the homepage, `/stocks/` and a sample of stock pages

It turns recurring anomaly patterns into a PR with a fix and a test.

**Monthly:** update dependencies in `requirements.txt` and `site/package.json` via PR, plus GitHub Actions versions (Node 20 deprecation). Watch the Cloudflare file count (20k limit) and repo size; propose pruning `lists/archive` if it grows large.

**Guardrails:** PRs only, never direct pushes to the default branch for code. Lists and research commits from the pipeline stay automatic.

### 5. Editor: coordinator and weekly brief

Runs last on Saturday. It reads the screen, the Radar roll-up, the RULERS dossiers changed this week and the Professor's review, then:
- resolves disagreements, e.g. the RULERS analyst says BUY but the Professor flags a structural event
- writes `reports/weekly/<date>_brief.md`: top actions, new names, names that left, upcoming earnings, watchlist alerts
- opens or updates GitHub issues for decisions only you can make

This is the only "manager" role, and it works on *outputs*, not on the other agents.

## Does an agent need to manage the agents?

**No, not an LLM one.** Use deterministic orchestration (the GitHub Actions job graph) plus the **Editor** as a final reconciling step.

Reasons:
- The order is fixed: data → news → analysis → review → brief → deploy. A workflow graph runs that reliably for free; an LLM manager would decide the same thing every week at a cost, with a chance of getting it wrong.
- Failures are handled by the Engineer, triggered by the failure itself, not by a supervisor polling.
- Agents never call each other, so there is nothing to route. They communicate through files with fixed formats, which keeps each one testable and swappable.

Revisit this only if you later want agents to *choose* work dynamically, for example the RULERS analyst requesting a deeper news pull mid-run. Even then, a small "dispatcher" that turns structured requests into workflow runs beats a free-form manager.

## Implementation notes

- **Runtime:** each agent is a job using `anthropics/claude-code-action@v1`, with `github_token` and the whitespace-stripped `CLAUDE_CODE_OAUTH_TOKEN` (see `.github/workflows/weekly.yml`). Each prompt lives in its own file (`agents/<name>/PROMPT.md`), like `scout/PROMPT.md` today.
- **Workflows:**
  - `weekly.yml` extends to screen → radar-weekly → rulers → professor-review → editor → deploy.
  - New `radar-daily.yml` (Mon–Fri) and `professor-ingest.yml` (Sunday).
  - New `engineer.yml`, triggered `on: workflow_run` with conclusion failure, plus a weekly schedule.
- **The existing scout:** it becomes the RULERS analyst. `scout/PROMPT.md` is superseded by `agents/rulers/PROMPT.md`.
- **Budget** (rough, per week, on a Pro/Max subscription token there is no per-token bill, only usage limits; with an API key):
  - Radar: 5 × ~$0.30
  - Data engine: none
  - RULERS: ~$3–6
  - Professor: ~$2–4
  - Editor: ~$1
  - Engineer: ~$1 when nothing breaks
  - Total about **$10–15/week** on an API key.
- **Turn budgets:** cap `--max-turns` per agent: Radar 40, RULERS 120, Professor 80, Editor 40, Engineer 80.
- **Concurrency:** one concurrency group per workflow; the Saturday chain runs sequentially so agents never edit the same files at once.

## Build order

1. **Radar daily + weekly roll-up.** Highest value; independent of the others.
2. **RULERS analyst.** Replaces the current scout prompt with the RULERS dossier format.
3. **Professor knowledge base.** Seed `knowledge/rule1` and `CHECKLIST.md` first, then the InvestED episode ingest and the Saturday review.
4. **Editor.** Once there are three outputs to reconcile.
5. **Engineer.** On-failure trigger first, then the health check, then the monthly dependency check.
6. ~~Portfolio and alerts~~ → the Holdings page (built, browser-only).

## Decisions (2026-10-04)

- **InvestED:** the agent transcribes every episode itself, in order, and teaches it as a structured course (see Professor above). Built.
- ***The Intelligent Investor*:** no book text in the public repo. The ingestion options are in [`LIBRARY.md`](LIBRARY.md).
- **Holdings:** no private tracking by any agent. The [Holdings page](https://ruleone.pages.dev/holdings/) keeps your tickers and buy prices in your own browser, with export and import. Built.
- **Notifications:** none for now (no push or email). Events surface in the weekly memo, on the site and on the Holdings page.
- **Reduce basis:** tranche buying only. This is value investing, so no options.

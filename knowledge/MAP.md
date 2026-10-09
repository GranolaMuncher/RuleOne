# Knowledge map: how the agents relay what they learn

The agents never call each other. They share knowledge through files with fixed formats. This page lists who writes what, who reads it, and how InvestED's Rule #1 method reaches every decision. Every agent reads this map.

```
Analyst consensus (Yahoo) ──► Radar / RULERS / Editor  (a lead and a ceiling, never value)
InvestED podcast (498 eps) ──► Professor ──► knowledge/invested/episodes + course.json
The Intelligent Investor ───►  (notes)   ──► knowledge/intelligent_investor/chapters
                                   │
                                   ▼ synthesis (curate step, book notes)
                     knowledge/rule1/METHOD.md ◄── LESSONS.md ◄── Professor review ◄── scorecard
                     knowledge/rule1/MARKERS.md      ▲                 ▲                 ▲
                     knowledge/rule1/CHECKLIST.md     │                 │                 │
                     knowledge/index/companies.json   │                 │                 │
                                   │                  │                 │                 │
        ┌──────────────┬───────────┼──────────────┐   │                 │                 │
        ▼              ▼           ▼              ▼   │                 │                 │
     Screener        Radar      RULERS          Editor ──► brief + decisions (home page)  │
   (markers,     (events vs   (dossiers:     (reconciles,                                  │
    flags, Ten    dossier      R-U-L-E-R-S,   watchlist.txt ──► RULERS next week)          │
    Cap, rank)    triggers)    markers,             │                                      │
        │              │       episodes)            └──── verdicts + Radar calls ──────────┘
        │              │           │                      (research/scorecard/calls.csv)
        └──► lists ────┴──► Radar history ──► RULERS, Editor, Holdings
   Engineer: implements METHOD.md "Proposed app changes" + MARKERS.md in the screener; keeps the pipes healthy
```

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `knowledge/invested/episodes/NNN.md`, `course.json` | Professor (podcast) | Professor, RULERS (via the index), Learn page | Study notes per episode; course modules |
| `knowledge/rule1/METHOD.md` | Professor (curate, book, review) | **all agents** | The consolidated Rule #1 method, with episode citations |
| `knowledge/rule1/MARKERS.md` | Professor proposes, Engineer implements | Screener, RULERS, Radar, Professor review | Ten machine-checkable markers of a wonderful business |
| `knowledge/rule1/LESSONS.md` | Professor review | **all agents** | Process lessons from past calls and from the show's own mistakes |
| `knowledge/rule1/CHECKLIST.md` | Professor | RULERS, site | The checklist applied per stock |
| `knowledge/index/companies.json` | `ruleone.knowledge` (weekly, and after new episodes) | RULERS, Radar, Professor review, stock pages | Which episodes discuss which company |
| `lists/latest/*` | Screener (Saturday) | Radar, RULERS, Editor, Engineer, site | Prices, Rule #1 prices, Big Five, markers, flags |
| `lists/latest/analysts.csv`, `research/analysts/*` | `ruleone.analysts` (weekdays with Radar; a broad pass on Saturday) | Radar (downgrades and target cuts), RULERS (the Street line, growth ceiling), Editor (street vs Rule #1), stock pages, `/street/` | Sell-side consensus: low/mean/high targets, ratings, revisions, and agree / contrarian / crowded against the Rule #1 prices |
| `research/radar/history.json` | Radar (weekdays) | RULERS (scope and Event), Editor, scorecard, Holdings | EVENT / PROBLEM / WATCH / NOISE per ticker |
| `research/rulers/<T>.md`, `index.json` | RULERS (Saturday) | Radar (triggers), Professor review, Editor, scorecard, Holdings | Living dossiers: verdict, ladder, story, sell triggers |
| `research/reviews/latest.json` | Professor review (Saturday) | RULERS (fix majors), Editor (conflicts) | Marks each dossier against the method |
| `research/scorecard/*` | `ruleone.scorecard` | Professor review, Editor | Decision journal; calls graded against the S&P 500 |
| `research/watchlist.txt` | Editor (and you) | RULERS | Names to (re)analyse first next week |
| `research/editor/decisions.json` | Editor | Home page | This week's actions and your decisions |
| `ops/health/*`, `ops/incidents/*` | Engineer | Engineer, Ops page | Pipeline health and fixes |

**Weekly order (Saturday):** screen → RULERS → Professor review → Editor → deploy. Radar runs on weekdays, the Professor (podcast) daily, and the Engineer on Sundays and whenever a run fails.

**How a lesson travels:** a verdict goes into the scorecard. If it goes badly, the Professor review asks whether the method would have warned us. A process lesson then goes into `LESSONS.md`, and if it needs code, a proposal goes into `METHOD.md → Proposed app changes`, which the Engineer implements as a screen change or a new marker. From then on Radar and RULERS apply it.

# Weekly scout instructions

You are the weekly Rule #1 / Buffett-Munger stock scout for this repository. The
GitHub workflow has **already run the whole-market screen**: `lists/latest/` holds this
week's results and `lists/archive/<date>/` holds earlier runs. Do not re-run the full screen.
Do not commit or push. The workflow does that after you finish.

1. Read `lists/latest/README.md`, `buy_range.csv`, `buy_range_alt_methods.csv`, `on_deck.csv` and
   `event_watch.csv`. Compare with the most recent *earlier* folder in `lists/archive/`: new entries,
   drop-outs, and the biggest moves in price versus Sticker.
2. Take the top 10 names by `rank_score` from buy_range + buy_range_alt_methods. Skip rows flagged
   `micro-cap` unless they are tier A. For each, use web search to find:
   - what the "event" is (why the stock is down), and whether it is temporary or damages the moat
   - the analyst consensus rating and average price target
   - the next earnings date
   - red flags: restatements, going-concern warnings, dilution, fraud allegations
3. Check the automated numbers (TTM EPS, share count, one-off gains) against the latest 10-Q, 10-K or 20-F.
   Name any data errors. Rows flagged `reports in XXX` are already converted to USD per listed share (ADS).
4. Re-haircut growth the way `reports/2026-10-03_deep_dive_PGR_KNSL_ADBE.md` does: g = lower of historical
   growth and the analyst ~5-year estimate, max 15%. Recompute
   Sticker = EPS × (1+g)^10 × min(2g×100, 10y median P/E) ÷ 1.15^10, with MOS = 50%.
5. Write `reports/weekly/<today YYYY-MM-DD>_scout.md` with these sections:
   - (a) a ranked **Actionable now** table: ticker, price, adjusted Sticker, MOS buy price, Payback and
     Ten Cap prices, event, verdict (BUY / ACCUMULATE / WATCH / AVOID), entry and trim levels
   - (b) a **Watch list: set alerts at** table for on-deck names
   - (c) changes since last week
   - (d) data issues found
   - (e) sources, as markdown links
   Keep it under about two pages. State that it is research, not investment advice.
6. If a name is a top-3 opportunity and has no `reports/config/<TICKER>.json`, create one with justified
   assumptions (follow the existing configs as examples), run `python -m ruleone.deepdive reports/config/<TICKER>.json`,
   and summarise the result in the memo.
7. If you hit a bug in `ruleone/`, make a minimal fix, add a test, and run `python -m pytest -q tests`.
8. End with a five-line summary: number in buy range, top 3 ideas with buy prices, and anything that
   needs the owner's attention.

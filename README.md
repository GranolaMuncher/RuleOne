# RuleOne: a Rule #1 / Buffett-Munger stock screener and valuation toolkit

This repo has two parts:

1. **A screener that runs on a schedule.** It scans every NYSE and Nasdaq common stock (about 5,800 SEC registrants), keeps the "wonderful companies" (Phil Town's Big Five), values each one (Sticker Price, Margin-of-Safety buy price, Payback Time, Ten Cap) and checks for **events**: drawdowns, insider buying, activist 13Ds and negative 8-Ks. It writes ranked lists to [`lists/`](lists/). A GitHub Action re-runs it every Saturday and publishes the results to a website (Astro + Cloudflare Pages) built from [`site/`](site/).
2. **A deep-dive engine** (`ruleone.deepdive`). It builds a full valuation of one company from a JSON assumptions file: a 10-year DCF with both perpetuity and exit-multiple terminal values, a CAPM WACC, a sensitivity grid, a peer comps table with implied values, DDM/Gordon models and the Rule #1 prices. Finished research reports are in [`reports/`](reports/).

Everything comes from free primary sources, with no API keys:

| Data | Source |
|---|---|
| Audited financials: 10-K and 10-Q XBRL, TTM figures | SEC EDGAR [XBRL frames](https://www.sec.gov/edgar/sec-api-documentation) and companyfacts APIs |
| Filings, 8-K items, Form 4 insider trades, 13D | SEC EDGAR submissions API and Archives |
| Prices, 52-week range, 10y monthly history, beta | Yahoo Finance chart API |
| 10-year Treasury (risk-free rate) | Yahoo `^TNX` |

> **Not investment advice.** These are screening outputs built from automated XBRL extraction. Companies sometimes tag items in unusual ways, so check the numbers against the filing before you act on any of them.

## Using the lists

| File (`lists/latest/`) | What it holds |
|---|---|
| `README.md` | A readable summary of every list |
| `buy_range.csv` | Price ≤ **MOS price** (50% of Sticker). The strict Rule #1 buy signal. |
| `buy_range_alt_methods.csv` | Price ≤ the Payback Time or Ten Cap price, but not yet below MOS |
| `on_deck.csv` | Price below Sticker but above the buy price: watch these and set alerts |
| `event_watch.csv` | Tier A/B companies with a current event (≥20% drawdown, insider buys, 13D, negative 8-K) |
| `wonderful_companies.csv` | All Tier A businesses with their valuation |
| `all_candidates.csv` | Every company that passed the quality screen |
| `universe.csv` | **Every** NYSE/Nasdaq listing (~5,800): price moves (1w–1y, YTD, % off 52-week high), P/E, Sticker, buy price, Payback, Ten Cap and Big Five. Names outside the quality screen are valued on last-fiscal-year SEC data and get a valuation label (below MOS / below Sticker / above Sticker), not a buy signal |

Each run is also archived at `lists/archive/YYYY-MM-DD/`. `lists/history.csv` adds one row per run for every name in buy range or on deck, so you can see how prices move against Sticker over time.

## Methodology

**Stage 1: the quality screen across the whole market.** SEC XBRL *frames* return one concept for one period for every filer in a single request. About 650 requests rebuild 14 years of annual Revenue, EPS, equity, operating cash flow, capex, operating income, tax and long-term debt for every listed company in about 90 seconds. Per-share history is restated for stock splits. The **Big Five** tests are:

* Sales, EPS, BVPS and operating cash flow growth of at least 10%/yr over 10, 5 and 1 years
* ROIC of at least 10%, averaged over 10, 5 and 1 years. ROIC = NOPAT ÷ (equity + long-term debt).

A company moves to stage 2 if it passes at least 60% of the tests it has data for, has a 10y or 5y ROIC of at least 10%, is profitable, has filed recently and has revenue of at least $50M.

**Quality tiers.** **A** means at least 80% of tests passed, every ROIC window at or above 10%, and long-term debt that free cash flow could repay in 3 years or less. **B** means at least 67% of tests passed with ROIC at or above 10%. **C** covers the remaining stage-2 companies.

**Stage 2: valuation.** This stage uses companyfacts with TTM figures (FY + YTD − prior YTD), diluted share counts (with a Yahoo fallback for multi-class filers), 10 years of monthly prices and EDGAR filings.

* **Windage growth g** = min(median EPS growth, max(median BVPS growth, median sales growth), 15%), using the 10y and 5y windows. Rule #1 normally takes the lower of equity growth and analysts' estimates. Using max(BVPS, sales) stops large buybacks, which shrink book value, from disqualifying great compounders.
* **Sticker Price** = TTM EPS × (1+g)^10 × future P/E ÷ 1.15^10. Future P/E is the lower of 2 × g (as a percentage) and the 10-year **median** P/E, capped at 50. The median keeps one-off years, such as a near-zero-EPS year, from inflating it.
* **Buy (MOS) price** = 50% of Sticker.
* **Payback Time price** is the price at which 8 years of FCF, growing at g, adds up to the purchase price.
* **Ten Cap price** = (10 × TTM owner earnings − net debt) ÷ shares. Owner earnings = OCF − *maintenance* capex + tax provision, where maintenance capex is depreciation (capped at capex) or, without D&A, half of capex. This follows Town's refinements in InvestED 278, 341 and 467.
* **Methods agree** counts how many of the three prices (Ten Cap, Payback, MOS) the stock trades under. The method says to triangulate, so 2–3 of 3 is the strongest signal.
* **Synthesis flags:** cash not real (after-tax owner earnings < 75% of net income), debt > 3 years of FCF, ROIC falling, and cheap without an event (a buy signal within 10% of the 52-week high, so check for a value trap).

**Events** mean the temporary bad news Rule #1 investors wait for: a drawdown from the 52-week high, open-market Form 4 purchases ("P" codes, last 120 days), SC 13D filings (180 days), and 8-K items such as restructuring, impairment, officer departures, restatements and cyber incidents (60 days). The next report date is estimated from the last 10-Q or 10-K.

**All stocks table.** Every listing is priced with Yahoo's batch quote endpoint (1-year weekly and 10-year monthly closes). The monthly closes are saved to `lists/latest/prices_monthly.csv` and drive each stock page's **price history chart**, which has 1Y, 5Y and 10Y views, a log-scale toggle, hover/keyboard readouts and buy-price and Sticker reference lines. For dividend payers the chart adds a **total return** line (dividends reinvested). It comes from Yahoo's dividend-adjusted closes, fetched per stock (about 15 minutes a week), which also give trailing-12-month dividend, yield, 5-year dividend growth and 5- and 10-year annualised total return. Adjusted series that are negative or above the actual price (broken by reverse splits) are discarded, yields above 25% are flagged as special or return-of-capital payouts, and a trailing dividend that includes a one-off special is labelled. It is valued from the last fiscal year of SEC XBRL frames, with the share count from the latest 10-Q cover page, so stock splits after the 10-K are corrected. Non-US filers are flagged because their per-share figures may be per ordinary share rather than per ADS. Names that pass the quality screen use the detailed TTM, currency-adjusted numbers instead. **Industry** is the SEC's SIC description and **sector** maps SIC codes onto 11 GICS-style sectors, plus "Funds & BDCs" for closed-end funds and BDCs, which have no SIC code. Codes are kept in `lists/reference/sic.csv`, and each run fetches new listings plus the 300 oldest entries.

**Rank score** = 2 × Big Five pass rate + 2 × discount to Sticker + a tier bonus + 0.25 × event score.

**Foreign filers.** 20-F filers that report under US GAAP in another currency (CNY, HKD, ...) are detected from their XBRL units. Their figures are converted to USD at spot (TTM) and at fiscal-year-end rates (history), restated per ADS using the ADS ratio implied by share counts, and use Yahoo trailing EPS because they file no XBRL 10-Qs. Big Five growth is measured in the reporting currency, so FX swings do not distort it.

**Known limitations.** Banks and insurers do not fit the Big Five well: operating cash flow and debt mean something different for them, and ROIC is better replaced with ROE. IFRS filers (TSM, NVO and others) are not covered yet. Forward/analyst estimates are not part of the automated screen. The deep-dive config accepts them.

## Running it

```bash
pip install -r requirements.txt
export SEC_USER_AGENT="Your Name you@domain.com"   # required by SEC fair-access policy
python -m ruleone.screener                          # full market (~15-25 min on a cold cache)
python -m ruleone.screener --tickers MSFT,V,MA      # just these names
python -m ruleone.deepdive reports/config/MSFT.json # full valuation model -> reports/model/
python -m pytest -q tests
```

### Weekly pipeline and website

[`.github/workflows/weekly.yml`](.github/workflows/weekly.yml) runs every **Saturday at 11:17 UTC**, after Friday's close. You can also start it from **Actions → Weekly Rule One run → Run workflow**. Each run does three things:

1. **Screen:** runs the whole-market screen and commits `lists/`.
2. **Scout** (optional): Claude Code, through [`anthropics/claude-code-action`](https://github.com/anthropics/claude-code-action), follows [`scout/PROMPT.md`](scout/PROMPT.md). It researches the top buy-range names and writes `reports/weekly/<date>_scout.md`, and the workflow commits the memo.
3. **Deploy:** builds the Astro site in [`site/`](site/) and publishes it to **Cloudflare Pages** through [`deploy-site.yml`](.github/workflows/deploy-site.yml). The same workflow also runs whenever `lists/`, `reports/` or `site/` change.

**Professor** ([`professor.yml`](.github/workflows/professor.yml), four times a day) works through the InvestED podcast in episode order. It transcribes each episode on the runner with faster-whisper, then Claude writes study notes and updates a structured course in [`knowledge/invested/`](knowledge/invested/), which the site shows under **Learn**. Transcripts are never committed. It uses the same Claude secret as the scout. The agent roadmap is in [`docs/AGENT_PLAN.md`](docs/AGENT_PLAN.md), and the options for *The Intelligent Investor* are in [`docs/LIBRARY.md`](docs/LIBRARY.md).

**Radar** ([`radar.yml`](.github/workflows/radar.yml), weekdays after the close) sweeps filings, headlines, price moves and value investors' 13F changes for ~150 watch-list names. Claude judges each item EVENT / PROBLEM / WATCH / NOISE against the Rule #1 method synthesised from the podcast ([`knowledge/rule1/METHOD.md`](knowledge/rule1/METHOD.md), shown on the site at `/rule1/`).

The site has a **Holdings** page, where you enter tickers and buy prices per tranche, stored only in your browser, and get dangers and insights against the latest screen. It also has a sortable, filterable screen with CSV downloads, an **All stocks** page (every listing, with filters for sector, industry, drawdown, 1-month move, Big Five, P/E, Price/Sticker and market cap, quick presets, and a CSV export of the filtered view), a page per stock with its price against the Rule #1 levels, the Big Five and its run history, plus the research reports, the archive of every run and the methodology. Preview it locally with `cd site && npm install && npm run dev`.

**One-time setup** (Settings → Secrets and variables → Actions):

| Kind | Name | Value |
|---|---|---|
| Variable | `SEC_USER_AGENT` | Your name and email. SEC requires this. |
| Secret | `CLOUDFLARE_API_TOKEN` | A Cloudflare API token with **Account → Cloudflare Pages → Edit** |
| Secret | `CLOUDFLARE_ACCOUNT_ID` | Your Cloudflare account ID (in the dashboard sidebar) |
| Variable (optional) | `CLOUDFLARE_PAGES_PROJECT` | Pages project name. The default is `ruleone`, which publishes to `ruleone.pages.dev` if the name is free. |
| Secret (optional) | `ANTHROPIC_API_KEY` **or** `CLAUDE_CODE_OAUTH_TOKEN` | Turns on the weekly Claude scout memo. Create the OAuth token with `claude setup-token`. |

Also set **Settings → Actions → General → Workflow permissions** to **Read and write**. Without the Cloudflare secrets, the site still builds but the deploy step is skipped with a warning. Without a Claude secret, the scout step is skipped.

The site is **public** by default. To restrict it to you, add a Cloudflare Access policy (Zero Trust → Access → Applications) for the Pages domain.

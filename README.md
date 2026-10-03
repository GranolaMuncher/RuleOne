# RuleOne: a Rule #1 / Buffett-Munger stock screener and valuation toolkit

This repo has two parts:

1. **A screener that runs on a schedule.** It scans every NYSE and Nasdaq common stock (about 5,800 SEC registrants), keeps the "wonderful companies" (Phil Town's Big Five), values each one (Sticker Price, Margin-of-Safety buy price, Payback Time, Ten Cap) and checks for **events**: drawdowns, insider buying, activist 13Ds and negative 8-Ks. It writes ranked lists to [`lists/`](lists/). A GitHub Action re-runs it after every US trading day.
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
* **Ten Cap price** = 10 × TTM owner earnings per share. Owner earnings are approximated as OCF − total capex, which treats all capex as maintenance and is conservative.

**Events** mean the temporary bad news Rule #1 investors wait for: a drawdown from the 52-week high, open-market Form 4 purchases ("P" codes, last 120 days), SC 13D filings (180 days), and 8-K items such as restructuring, impairment, officer departures, restatements and cyber incidents (60 days). The next report date is estimated from the last 10-Q or 10-K.

**Rank score** = 2 × Big Five pass rate + 2 × discount to Sticker + a tier bonus + 0.25 × event score.

**Known limitations.** Banks and insurers do not fit the Big Five well: operating cash flow and debt mean something different for them, and ROIC is better replaced with ROE. Foreign IFRS filers (20-F) are not covered yet. Forward/analyst estimates are not part of the automated screen. The deep-dive config accepts them.

## Running it

```bash
pip install -r requirements.txt
export SEC_USER_AGENT="Your Name you@domain.com"   # required by SEC fair-access policy
python -m ruleone.screener                          # full market (~15-25 min on a cold cache)
python -m ruleone.screener --tickers MSFT,V,MA      # just these names
python -m ruleone.deepdive reports/config/MSFT.json # full valuation model -> reports/model/
python -m pytest -q tests
```

### Running it on a schedule

[`.github/workflows/screener.yml`](.github/workflows/screener.yml) runs Tuesday to Saturday at 11:17 UTC, after each US trading day. It commits refreshed lists, and you can also start it by hand from **Actions → Rule One screener → Run workflow**. Before the first run:

1. Merge this branch into the default branch, since scheduled workflows only run there.
2. Under **Settings → Secrets and variables → Actions → Variables**, add `SEC_USER_AGENT`, set to your name and email.
3. Under **Settings → Actions → General → Workflow permissions**, allow **Read and write**.

# Markers of a wonderful business

This file is the shared contract between the screener, the agents and the site. Each marker below comes from the InvestED synthesis ([METHOD.md](METHOD.md)). The screener computes it from up to 11 years of SEC filings (`ruleone/metrics.py: wonderful_markers`). The RULERS analyst confirms it, or overrides it with reasons, and Radar and the Editor watch for it breaking.

**Marker score** is the share of known markers passed (needs ≥5 known). It is shown on stock pages and added to the rank score. Markers are *evidence that a moat existed*: numbers look out the back window [023, 110]. They never replace understanding why the moat will last.

| Marker | Test | Why it matters | Episodes |
|---|---|---|---|
| `roic_consistent` | ROIC ≥10% in ≥8 of the last 10 years | The first proof of a moat: ten years is long enough for rivals to attack | 004, 021, 022, 270 |
| `roic_not_falling` | Latest 3-year average ROIC ≥ 75% of the 10-year average | Falling ROIC after deals means capital was misallocated and the story may have changed | 270, 271, 432 |
| `growth_coherent` | Sales, net income and OCF 10-year growth within 10 points of each other and all positive | The big growth rates should move together; tangled lines (GM) mean too hard | 019, 020 |
| `margin_stable` | Gross margin (else operating margin) standard deviation ≤ 3 points over 10 years, with the latest not below the median | Pricing power: steady margins through inflation and recessions | 178, 318, 332, 362–365, 460 |
| `fcf_margin` | Free cash flow ≥ 10% of revenue | One of Phil's two numbers tests of a moat (FCF ÷ revenue) | 081, 082 |
| `cash_real` | After-tax owner earnings ≥ 75% of net income | Earnings can be tweaked; cash can't (Ackman's 75% rule) | 271, 273, 274, 476 |
| `low_debt` | Total debt ≤ 2 years of free cash flow | Debt turns a scare into bankruptcy; Ackman's test is ~2 years and Phil's is 2–3 | 075, 089, 260, 428 |
| `no_dilution` | Share count grew ≤ 0.5%/yr over 5 years | Dilution transfers value away from owners; buybacks only help below value | 100, 226, 227 |
| `predictable` | Revenue rose in ≥8 of the last 10 years | "Simple and predictable" (Ackman #1); the ten-cap only needs "it will be bigger" | 274, 343, 467 |
| `recession_tested` | Profitable, with ROIC ≥10%, in 2020 | Wait for ten years of data *and* a recession to see the business and management when the tide goes out | 390, 442, 443 |

**Interpretation:**
- 9–10 of 10: the numbers of a wonderful business. Now prove the moat and price.
- 6–8: good, but find which markers fail and why.
- Below 6: not a Rule #1 business on the numbers. Too hard unless there is a specific reason.
- Banks and insurers: the OCF-based markers (`fcf_margin`, `cash_real`) mean little (float). Use ROE and book value growth instead [411].

**Changing a marker:** the Professor proposes changes in `METHOD.md → Proposed app changes`. The Engineer implements them with a test and updates this table.

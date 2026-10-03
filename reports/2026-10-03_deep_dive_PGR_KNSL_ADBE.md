# Rule #1 / Buffett-Munger deep dive: Progressive (PGR), Kinsale Capital (KNSL), Adobe (ADBE)

**Date:** 3 October 2026. **Prices:** NYSE/Nasdaq close on 2 October 2026 (PGR $210.31, KNSL $329.72, ADBE $237.69).
**How these were chosen:** the [whole-market screen](../lists/latest/README.md) covered 5,774 NYSE and Nasdaq stocks. 4,602 had SEC XBRL history, 270 passed the Big Five quality test, and 15 traded below the automated 50% margin-of-safety price. Of those 15, these three are the large, liquid, analyst-covered businesses with a long record (PGR 15/15 Big Five tests, KNSL 12/13, ADBE 11/15), and each has an identifiable **event** behind its fall: a softening auto-insurance cycle, a softening excess & surplus (E&S) market, and fear of AI disruption.

> This is research and education, not personalised investment advice. Financials come from SEC XBRL filings, extracted programmatically. Every model can be re-run with `python -m ruleone.deepdive reports/config/<TICKER>.json`, and the full model output is in [`reports/model/`](model/).

---

## 0. Executive summary

| | **KNSL** | **PGR** | **ADBE** |
|---|---|---|---|
| Price (2 Oct 2026) | $329.72 | $210.31 | $237.69 |
| DCF, perpetuity / exit multiple | $402 / $409 | $260 / $238 | $339 / $398 |
| Comps (peer-median P/E, EV/EBITDA) | $290–$302 | $178–$252 | $438–$515 |
| DDM (Gordon / 2-stage) | n/m ($12 / $23; payout ~3%) | $128 / $168 (variable dividend, poor fit) | n/a, no dividend |
| Town Sticker Price (formula) | $538 | $278 | $230 |
| **Sticker Price used here** = avg(Town Sticker, DCF midpoint) | **$471** | **$263** | **$299** |
| **Buy price** (50% margin of safety) | **$236** | **$132** | **$150** |
| Payback Time (8-yr) price / Ten Cap price | $629 / $437 ✅ | $375 / $272 ✅ | $331 / $263 ✅ |
| Price ÷ Sticker | 0.70 | 0.80 | 0.80 |
| Intrinsic-value range (central) | $290–$540 (≈$400) | $180–$280 (≈$250) | $230–$420 (≈$340) |
| Wonderful company? | **Yes**: widest moat per dollar, owner-operator | **Yes**: scale and cost moat, cyclical | **Yes**, but the moat is being questioned |
| **Recommendation** | **BUY (scale in)** | **ACCUMULATE** | **HOLD / watch** |

**Bottom line.** None of the three trades at the strict 50% margin-of-safety price, so a by-the-book Rule #1 investor would put all three on the watch list and wait. All three do pass Phil Town's two alternative buy tests, Payback Time and Ten Cap. **Kinsale is the most compelling.** It has the highest returns on capital, a founder-CEO with about 3.8% ownership, and the largest discount to DCF value (about 22%), and a soft E&S market is the kind of temporary event Rule #1 looks for. **Progressive** is a best-in-class compounder priced near fair value for a soft cycle: buy in tranches. **Adobe** looks cheap on every multiple, but its moat is exactly what the market is debating and its CEO and CFO seats are both in transition, so it falls outside a conservative circle of competence until the AI picture is clearer.

---

## 1. Macro and market context (applies to all three)

| Factor | Current reading | Effect |
|---|---|---|
| 10-yr Treasury | **5.27%** (2 Oct). It touched 5.34% this week, the highest since 2002 ([Trading Economics](https://tradingeconomics.com/united-states/government-bond-yield), [Fed H.15](https://www.federalreserve.gov/releases/h15/)) | Raises every discount rate: Rf is 5.27% in all WACCs. Insurers benefit because reinvestment yields rise (KNSL portfolio yield 4.5%). Long-duration software (ADBE) is penalised. |
| Fed | Fed funds 3.75–4.00% after a hike, the first since 2023; market prices ~26% odds of another ([search summary of Fed/Schwab coverage](https://www.schwab.com/learn/story/fomc-meeting)) | Tighter financial conditions; risk of a growth slowdown |
| Inflation / GDP | CPI ~2.5–3.0%, real GDP ~1.7–2.5%, unemployment ~4.1–4.5% ([Philadelphia Fed SPF Q2-26](https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/survey-of-professional-forecasters/2026/spfQ226.pdf)) | Sticky inflation keeps auto-repair and medical **claim severity** high (PGR) and supports insurance pricing. Slower nominal growth weighs on seat-based software. |
| Geopolitics | US–Iran exchanges of fire; Brent ~$97–106 in September; Middle East shut-ins of 6.7 mb/d ([NST](https://www.nst.com.my/amp/business/economy/2026/09/1528051/oil-rises-risks-prolonged-mideast-conflict-heighten-supply-worries), [Hellenic Shipping/EIA](https://www.hellenicshippingnews.com/eia-raises-oil-price-forecasts-as-middle-east-supply-drops/)) | Higher fuel prices mean fewer miles driven and lower claim frequency (good for PGR in the short run) but also an inflation shock. Marine and energy specialty lines harden (KNSL is a small participant). |
| Equity valuation | S&P 500 forward P/E ~22.5x; equity risk premium ~2.1–2.25%, near dot-com lows ([StockWire](https://stockwirex.com/?p=44108), [Fed ERP warning coverage](https://eciks.org/25353-fed-equity-risk-premium-warning)) | I use a **normalised ERP of 4.5%**, not the depressed implied 2.1%. That is deliberately conservative and lowers every DCF value. |

---

## 2. Methodology and global assumptions

* **Financial data:** SEC EDGAR XBRL (10-K and 10-Q). TTM = last fiscal year + current year-to-date − prior year-to-date. Per-share history is split-adjusted. The code is in `ruleone/companyfacts.py`.
* **WACC:** Ke = Rf (5.27%, ^TNX) + β × ERP (4.5%) [+ a size premium where noted]. β is a 5-year monthly regression against the S&P 500, Blume-adjusted (0.67 × raw + 0.33), unless overridden with a stated reason. Kd = interest expense ÷ debt (or a stated market yield) × (1 − effective tax rate). Weights are market values.
* **DCF:** 10-year explicit forecast, mid-year discounting. FCFF = EBIT × (1 − t) + D&A − capex − reinvestment. Terminal value uses both (a) Gordon growth at g = 3.0% and (b) an EV/EBITDA exit multiple. Each method reports the multiple or growth rate it implies so the two can be checked against each other. A WACC × g sensitivity grid is in `reports/model/`.
* **Insurer adaptation:** revenue = premiums + investment income, "EBIT" = pre-tax income + interest, and "reinvestment" = the statutory capital that growth requires (premium ÷ surplus leverage). FCFF for an insurer is close to distributable earnings.
* **Comps:** TTM multiples come from the same XBRL pipeline (`snapshot()` in `ruleone/deepdive.py`). Forward P/E uses next-fiscal-year consensus EPS where a source was found. Peers without one show n/a.
* **Rule #1:** Sticker = TTM EPS × (1+g)^10 × min(2g, 10-yr **median** P/E) ÷ 1.15^10. The MOS (buy) price is 50% of Sticker. Payback Time is the price recovered by 8 years of growing FCF. Ten Cap is 10 × owner earnings (OCF − all capex). The growth rate g is a judgement call, stated and justified for each company.
* **Sticker Price used for the decision:** the brief asks for the Sticker to be based on intrinsic-value work, so I average the Town formula Sticker with the DCF midpoint and apply a **50% margin of safety**. That is Town's standard MOS, and it is justified here by (a) cycle risk at both insurers, (b) the AI-disruption uncertainty at Adobe, and (c) a market-wide ERP near historic lows.

---

## 3. Progressive Corporation (NYSE: PGR)

### 3.1 Financials (SEC 10-K FY2025, 10-Q Q2-2026; $B except per share)

| | FY2022 | FY2023 | FY2024 | FY2025 | TTM Jun-26 |
|---|---|---|---|---|---|
| Revenue | 49.6 | 62.1 | 75.4 | 87.7 | 91.1 |
| Pre-tax + interest ("EBIT") | – | – | – | – | 15.1 |
| Net income | 0.7 | 3.9 | 8.5 | 11.3 | 11.7 |
| Operating cash flow | 6.8 | 10.6 | 15.1 | 17.5 | 16.3 |
| Capex | 0.3 | 0.3 | 0.3 | 0.3 | 0.4 |
| Diluted EPS | $1.18 | $6.58 | $14.40 | $19.23 | $19.93 |

Balance sheet: equity $34.3B (BVPS ≈ $58.5, so P/B ≈ 3.6x), debt ~$2.7B on XBRL tags (company-reported total debt is higher, about $6–7B; leverage stays modest either way), diluted shares 586M, market cap $123B. **Latest monthly data (August 2026):** net premiums written +6% to $7.61B, policies in force +7% to 40.5M, combined ratio **89.3** vs 83.1 a year earlier (hit by a Midwest derecho and Hurricane Lala flooding), net income −22% ([Insurance Business](https://www.insurancebusinessmag.com/us/news/breaking-news/progressives-combined-ratio-jumps-6-2-points-as-net-income-falls-22-590384.aspx), [Seeking Alpha](https://seekingalpha.com/news/4644323-progressive-reports-6-august-premium-growth-net-income-drops-22-to-951m)). Shares fell 9% on 15 July 2026 after slower June premium growth ([source](https://eciks.org/14197-20835-insurance-progressive-shares-pricing-pressure)).

### 3.2 DCF

**WACC 8.8%:** Rf 5.27% + β 0.80 × 4.5% → Ke 8.9%. The 5-year regression beta is only 0.24, which understates underwriting-cycle risk, so I override it with a P&C-industry beta of about 0.80. Kd 5.8% pre-tax, 4.6% after tax. Weights E 97.9% / D 2.1%.

| Assumption | Value | Rationale |
|---|---|---|
| Revenue growth | 5%, 7%, 8%, 8%, 7%, 6.5%, 6%, 5%, 4.5%, 4% | Soft-market slowdown in 2027, then share gains (agency auto +7%) and a normal cycle |
| Pre-tax margin | 13.0% falling to 10.5% | TTM 16.6% is a cycle peak (combined ratio ~87). The 96 combined-ratio target plus a ~4–5% investment margin gives ~10–11% through the cycle. |
| Tax | 20.9% (effective) | |
| Reinvestment | 30% of incremental revenue | About 3:1 premium-to-surplus |
| Terminal | g = 3.0% / exit 10.0x EBITDA | Peer median EV/EBITDA is 9.7x |

10-year PV of FCF is $64.5B. **Perpetuity method:** TV $209.5B → EV $154.7B → **$260/share** (implies 11.7x EBITDA). **Exit-multiple method:** TV $179.3B → EV $141.7B → **$238/share** (implies g = 2.1%). Across the WACC × g grid (7.8–9.8% × 2–4%) the range is $205–$372.

### 3.3 Comparable companies

Peers are **ALL, TRV, CB, HIG, CINF and WRB**: the large US P&C carriers with heavy personal-auto or commercial-lines overlap and similar capital intensity. Allstate is the closest personal-lines competitor, Travelers and Hartford are multiline, Chubb is a scale peer, and Cincinnati Financial and W.R. Berkley are disciplined commercial underwriters.

| | P/E TTM | P/E fwd | EV/EBITDA | P/S | P/FCF |
|---|---|---|---|---|---|
| **PGR** | **10.6x** | **12.8x** (2027E EPS $16.39) | **8.2x** | **1.4x** | **7.7x** |
| Peer median | 8.9x | 12.6x | 9.7x | 1.7x | 7.3x |
| Peer range | 4.5–14.2x | 11.8–13.5x | 4.7–19.6x | 0.8–2.1x | 4.8–8.6x |
| Implied PGR value (median) | $178 | $207 | $252 | $265 | $201 |

PGR trades about **in line with peers on most multiples**, even though its 10-year ROIC is 23%, its 10-year book-value growth is 15%, and it has grown policies faster than the industry for a decade. Peer P/Es are depressed by Allstate's 4.5x, which reflects a catastrophe-light quarter. Historically PGR has traded at a premium (10-year median P/E 18.2x), so the current discount reflects expected EPS **declines** (consensus 2026E $16.91, 2027E $16.39 vs TTM $19.93; [Barchart](https://www.barchart.com/story/news/2643950/here-s-what-to-expect-from-progressive-corporation-s-next-earnings-report)).

### 3.4 Dividends (DDM)

PGR pays $0.10/quarter plus a large **annual variable dividend** sized to excess capital. For FY2025 that was $13.50, declared on 5 December 2025 ([PGR IR](https://investors.progressive.com/financials/financial-news-releases/news-details/2025/Progressive-Announces-Dividend-Information-And-2026-Annual-Meeting-Record-Date/default.aspx)). Total DPS was FY23 $1.15, FY24 $4.90 and FY25 $13.90. I normalise D0 to the 3-year average of **$6.65**, about 33% of TTM EPS. **Gordon** (g 3.5%, Ke 8.9%): **$128**. **Two-stage** (7% for 10 years, then 3.5%): **$168**. The DDM understates value because PGR keeps capital for growth and pays variable dividends, so I treat it as a floor and do not weight it.

### 3.5 Growth drivers, competition, management, ESG

* **Growth drivers:** 40.5M policies in force (passed 40M in Q2). The property turnaround is "substantially complete" and 41 states are open for growth ([Q2-26 call summary](https://finance.biggo.com/news/US_PGR_2026-08-04)). Snapshot telematics and segmentation, bundling (auto plus home), the commercial-auto franchise, and higher reinvestment yields on a ~$90B+ portfolio.
* **Competitive landscape:** No. 2 in US personal auto behind State Farm, and the lowest-cost, most data-driven pricer. The threats are a soft cycle (State Farm and Allstate cutting rates to regain share; [BMO](https://finance.yahoo.com/news/bmo-trims-progressive-corporation-pgr-191535959.html)), advertising cost wars, and over the long term, autonomous vehicles moving liability to manufacturers.
* **Management and strategy:** CEO Tricia Griffith (since 2016) runs a culture that puts growth first but only at a 96 combined ratio or better. The strategy is to grow as fast as possible at that target, return excess capital through the variable dividend, and repurchase opportunistically.
* **ESG:** Catastrophe and climate exposure in property (Florida and the Gulf; mitigated through reinsurance and the property de-risking of 2023–25). Telematics raises data-privacy and fairness scrutiny. Governance is strong, with a long record of transparent monthly reporting, rare in the industry.
* **Analysts:** **Hold** consensus from 22 analysts (7 Buy, 13 Hold, 2 Sell). Average target **$234.89** (range $200–$308). Recent targets: Raymond James $245, KBW $250, Mizuho $230, Goldman $230, BMO $208 ([MarketBeat](https://www.marketbeat.com/stocks/NYSE/PGR/forecast/)). My DCF midpoint ($249) is a little above consensus.

### 3.6 Rule #1 / Buffett-Munger assessment

* **Understandable?** Yes. It collects premiums, prices risk better than rivals, and invests the float. Insurance accounting (reserves) needs care, but the model is simple.
* **Moat: wide and durable.** (1) **Cost advantage:** an expense ratio about 5–8 points below agency-based peers through direct distribution and scale. (2) **Data and pricing IP:** decades of rating data plus Snapshot, an advantage that compounds. (3) **Brand:** "Flo", the No. 1 or 2 advertiser in insurance. The weak spot is low switching costs: auto policies reprice every six months, so the moat is about running costs and pricing skill rather than locking customers in.
* **Management:** High integrity, with monthly disclosure and compensation tied to growth at a 96 combined ratio. Competence: **10-year ROIC 22.9%, 5-year 22.5%; sales +15.4%/yr over 10 years; EPS +24.5%; BVPS +15.3%; OCF +22.6%.** All 15 Big Five tests pass.
* **Margin of safety:** Sticker $263 (avg of Town $278 and DCF $249) → **buy price $132**. At $210.31 the stock is at **0.80× Sticker**, above the buy price. It passes **Ten Cap** ($272) and **Payback Time** ($375), but insurers' OCF-based tests are flattered by growth in float, so I place less weight on them. With consensus 2027E EPS ($16.39) in place of TTM, the Town Sticker falls to about $228.
* **Business, not stock:** I would be comfortable owning the whole business. **Long term:** auto insurance is compulsory, the pie grows with prices and population, and PGR keeps taking share. **Capital allocation:** good. It pays out the excess through variable dividends instead of making empire-building acquisitions. The ARX/home business has been mixed, but the company has fixed it.

### 3.7 Key risks
1. **Soft-market duration:** rate cuts and rising severity could push the combined ratio into the mid-90s for 2–3 years (2027E EPS is already −18% vs TTM).
2. **Catastrophe and climate:** August's 89.3 combined ratio shows how much weather matters. Property remains volatile.
3. **Reserve adequacy:** inflation in medical and legal costs (social inflation) could force prior-year reserve strengthening.
4. **Regulatory pressure on rates and affordability** in California, New York and Florida, plus scrutiny of telematics data.
5. **Long-dated disruption:** autonomous vehicles and embedded OEM insurance (Tesla) shrinking the personal-auto pool.

### 3.8 Conclusion: PGR

**Intrinsic value ≈ $250 (range $180–$280). Sticker $263, buy price $132; Town-strict MOS $139.** **ACCUMULATE.** Start a position now (Ten Cap is met and the price is about 16% below DCF), add aggressively below **$185**, and treat **≤ $139** as the full Rule #1 buy. Trim above **$280**. It is a wonderful business at a fair price in a soft cycle.

---

## 4. Kinsale Capital Group (NYSE: KNSL)

### 4.1 Financials ($B except per share)

| | FY2022 | FY2023 | FY2024 | FY2025 | TTM Jun-26 |
|---|---|---|---|---|---|
| Revenue | 0.8 | 1.2 | 1.6 | 1.9 | 2.0 |
| Pre-tax + interest | – | – | – | – | 0.7 |
| Net income | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 |
| Operating cash flow | 0.6 | 0.9 | 1.0 | 1.0 | 1.0 |
| Diluted EPS | $6.88 | $13.22 | $17.78 | $21.65 | $24.64 |

**Q2-2026** ([8-K / press release](https://ir.kinsalecapitalgroup.com/news/news-details/2026/Kinsale-Capital-Group-Reports-Second-Quarter-2026-Results/default.aspx)): gross written premium −5.0% to $527.6M. That was driven by a **−32.7% drop in Commercial Property**; gross written premium excluding property grew +3.7%. Net written premium −1.4%. **Combined ratio 75.5%** (losses 53.8%, expenses 21.7%). Net income $175.9M ($7.72/share, +31%). Operating EPS $5.54 (+16%). Net investment income +19.9% to $55.7M, with a 4.5% portfolio yield and 4.3-year duration. Book value per share **$89.34** (P/B ≈ 3.7x). Annualised operating ROE for the first half was **24.4%**. It repurchased $100M of stock and added a new $250M authorisation. The dividend is $0.25/quarter.

### 4.2 DCF

**WACC 9.6%:** Rf 5.27% + β 0.88 (raw 0.83) × 4.5% + 0.5% size premium → Ke 9.8%. Kd 5.4%, 4.3% after tax. E 97% / D 3%.

| Assumption | Value | Rationale |
|---|---|---|
| Growth | 4%, 8%, 11%, 12%, 11%, 10%, 8%, 7%, 6%, 5% | Soft E&S in 2027, then the cycle turns. History is 30%+ a year. |
| Pre-tax margin | 33% falling to 27% | Combined ratio drifts from about 75 to about 82, still best-in-class |
| Reinvestment | 50% of Δrevenue | E&S carriers run lower premium leverage |
| Terminal | g 3.0% / exit 11.0x EBITDA | Peer median is 9.1x; a premium for superior ROE |

PV of FCF is $4.0B. **Perpetuity:** EV $9.2B → **$402/share** (implies 10.7x). **Exit:** EV $9.4B → **$409/share** (implies g 3.2%). Grid range $346–$544. The two terminal methods agree closely, which is a good consistency check.

### 4.3 Comparable companies

Peers are **RLI, WRB, MKL, PLMR, SKWD and ACGL**: specialty and E&S underwriters with similar small-commercial or specialty mixes. RLI is the closest in its underwriting-first culture; Markel and Berkley are E&S leaders; Palomar and Skyward are fast-growing specialty carriers; Arch is a specialty and reinsurance benchmark.

| | P/E TTM | P/E fwd | EV/EBITDA | P/S | P/FCF |
|---|---|---|---|---|---|
| **KNSL** | **13.4x** | **15.3x** (2027E $21.52) | **10.4x** | **3.8x** | **7.6x** |
| Peer median | 12.3x | 13.5x (WRB only) | 9.1x | 1.8x | 8.0x |
| Implied KNSL (median) | $302 | $291 | $290 | $154 | $346 |

KNSL trades at only a **small premium** to peers on earnings multiples. That is unusual: its 10-year median P/E is **37x**, against 13.4x now. P/S looks expensive only because its margins are roughly double the peers', so P/S is not meaningful for insurers with very different margins. A justified P/B cross-check, (ROE − g) ÷ (Ke − g) with 22% ROE, 7% growth and 9.8% Ke, gives about 5.4x book, or roughly $480.

### 4.4 Dividends (DDM)

DPS rose from $0.28 (2018) to $0.68 (2025), a 13.6% 5-year CAGR, but the **payout is only ~3%** of EPS. Gordon gives $12 and two-stage gives $23. **The DDM does not fit:** Kinsale reinvests nearly everything at ~24% ROE, which is the outcome a Rule #1 investor wants.

### 4.5 Growth drivers, competition, management, ESG

* **Growth drivers:** E&S keeps taking share from the admitted (standard) market as standard carriers withdraw from hard-to-place risks, such as wildfire, coastal, social-inflation-heavy casualty and small contractors. Kinsale is pure E&S, focused on **small accounts**, with a proprietary underwriting and policy system that gives it the industry's lowest expense ratio (~21–22%). Higher yields are lifting investment income by about 20% a year.
* **Competition:** the E&S market is softening. Commercial property is the most competitive line (−33%), and MGAs plus new capital are crowding in. Kinsale's answer is to **walk away** from underpriced business, which shows up as declining premium but rising profit.
* **Management:** founder, Chairman and CEO **Michael Kehoe** founded the company in 2009. He owns about **888k shares, ~3.8% of the company (~$290M)**, held directly and through M.P. Kehoe LLC ([Form 4](https://www.secform4.com/filings/1669162/0001334940-24-000007.htm)). The strategy is underwriting profit first, a low-cost technology platform, no reliance on MGAs, and only modest buybacks.
* **ESG:** Catastrophe exposure in property, now reduced. Governance is strong: founder-led, simple capital structure, conservative reserving (consistent favourable prior-year development has been a hallmark). Social: small-business coverage availability.
* **Analysts:** **"Reduce/Hold"** consensus from 10 analysts (1 Buy, 7 Hold, 2 Sell). Average target **$368.78** (range $280–$442). Morgan Stanley $390, JPMorgan $390, Wells Fargo $377; Jefferies Underperform at $312 ([MarketBeat](https://www.marketbeat.com/stocks/NYSE/KNSL/forecast/)). Sentiment has fallen from 5 Buys a year ago to 1, which is classic Rule #1 "event" territory. Consensus EPS: 2026E about $21.12, 2027E about $21.50 ([MarketBeat/Zacks](https://www.marketbeat.com/instant-alerts/zacks-research-issues-pessimistic-outlook-for-knsl-earnings-2026-08-05/)).

### 4.6 Rule #1 / Buffett-Munger assessment

* **Understandable?** Yes, although E&S underwriting and reserving are specialised. The core idea is simple: price odd risks well and keep costs lowest.
* **Moat: wide.** (1) **Cost advantage:** an expense ratio about 8–10 points below E&S peers, from its in-house technology, which is very hard to replicate. (2) **Underwriting data and discipline:** full control of underwriting (no delegated authority) produces combined ratios in the 70s through cycles. (3) **Broker relationships** in a segment where speed and certainty of quote matter. Durability is high, but the business is cyclical in growth.
* **Management:** Excellent. ROIC is 17.6% (10y), 21.9% (5y) and 23.1% (1y). Sales have grown 37%/yr over 10 years, 5-year EPS 41%/yr, 5-year BVPS 27%/yr. Founder alignment, conservative reserving.
* **Margin of safety:** Sticker **$471** (avg of Town $538 and DCF $405) → **buy price $236**. Town-strict MOS is **$269**. At $329.72 the stock is at **0.70× Sticker**. It passes **Ten Cap ($437)** and **Payback Time ($629)**. The price is 32% below its 52-week high, and there was an insider purchase in the last 120 days (screen).
* **Business, not stock:** yes, a compounder you could own outright. **Long term:** the E&S share shift is secular and the cycle is temporary. **Capital allocation:** reinvests at ~24% ROE, with a token dividend and opportunistic buybacks. That is close to ideal.

### 4.7 Key risks
1. **A prolonged soft market:** premium could keep shrinking and erode operating leverage (2027E EPS growth is only ~2%).
2. **Reserve risk on casualty lines** (social inflation). Small-account casualty is long-tailed.
3. **Key-person risk:** the culture is closely tied to Kehoe.
4. **Catastrophe:** large property or wildfire events, although the reduced property book now limits this.
5. **Multiple compression:** the market may never pay 30x+ again. Even so, the DCF value does not depend on a high P/E.

### 4.8 Conclusion: KNSL

**Intrinsic value ≈ $400 (range $290–$540). Sticker $471, buy price $236 (Town-strict $269).** **BUY, scaling in.** Take one-third now (Ten Cap and Payback are met, the price is about 18% below DCF and at a cyclically low multiple), add the second third at **≤ $270**, and complete at **≤ $236**. Reassess above **$470**. **Of the three, this is the best Rule #1 fit.**

---

## 5. Adobe Inc. (Nasdaq: ADBE)

### 5.1 Financials ($B except per share; FY ends late November)

| | FY2022 | FY2023 | FY2024 | FY2025 | TTM Aug-26 |
|---|---|---|---|---|---|
| Revenue | 17.6 | 19.4 | 21.5 | 23.8 | 26.0 |
| Gross profit | 15.4 | 17.1 | 19.1 | 21.2 | 23.2 (89% margin) |
| Operating income (GAAP) | 6.1 | 6.7 | 6.7* | 8.7 | 9.3 (36%) |
| Net income | 4.8 | 5.4 | 5.6 | 7.1 | 7.3 |
| Operating cash flow | 7.8 | 7.3 | 8.1 | 10.0 | 10.8 |
| Free cash flow | 7.4 | 6.9 | 7.9 | 9.9 | 10.6 |
| Diluted EPS (GAAP) | $10.10 | $11.82 | $12.36 | $16.70 | $17.91 |

\*FY2024 includes the $1B Figma termination fee. Balance sheet: cash $4.4B, debt $6.4B, equity $11.8B (heavy buybacks), diluted shares 403M, market cap $95.8B, EV $97.8B.
**Q3 FY26** ([8-K](https://www.sec.gov/Archives/edgar/data/0000796343/000079634326000147/adbeex991q326.htm)): revenue **$6.76B (+13%)**, GAAP EPS $4.62, non-GAAP EPS $6.13, record OCF of $2.52B, ARR **$27.50B**, RPO $22.16B, and 9.5M shares repurchased in the quarter. **FY26 guidance was raised** to revenue $26.58–26.63B, GAAP EPS $18.12–18.17 and non-GAAP EPS $24.45–24.50. AI-first ending ARR is above $650M (+150%). Monthly active users are above 1B.

### 5.2 DCF

**WACC 10.5%:** Rf 5.27% + β 1.26 (raw 1.39) × 4.5% → Ke 10.9%. Kd 5.3%, 4.1% after tax. E 93.8% / D 6.2%.

| Assumption | Value | Rationale |
|---|---|---|
| Growth | 10%, 9%, 8.5%, 8%, 7%, 6.5%, 6%, 5%, 4.5%, 4% | FY26 is about +12%. Fades as generative-AI tools pressure low-end seats and freemium takes time to monetise. |
| GAAP operating margin | 36% falling to 33% | Stock-based compensation is treated as a real cost. AI compute and freemium mix weigh on margins. |
| Capex | 1.0% rising to 1.5% of revenue | AI infrastructure |
| ΔNWC | 0 | Deferred revenue funds working capital |
| Terminal | g 3.0% / exit 14.0x EBITDA | Software peer median is about 17x but compressing |

PV of FCF is $69.2B. **Perpetuity:** EV $138.5B → **$339/share** (implies 10.4x EBITDA). **Exit:** EV $162.3B → **$398/share** (implies g 4.8%, which is aggressive, so I lean towards the perpetuity value). Grid range $299–$433.

### 5.3 Comparable companies

Peers are **INTU, CRM, NOW, ADSK, PTC and WDAY**: large-cap application-software companies with subscription models, 80%+ gross margins and seat-based pricing exposed to the same AI debate. Autodesk and PTC are design-software analogues, Intuit is a prosumer and SMB franchise, and Salesforce, ServiceNow and Workday are enterprise SaaS.

| | P/E TTM | P/E fwd | EV/EBITDA | P/S | P/FCF |
|---|---|---|---|---|---|
| **ADBE** | **13.3x** | **9.0x** (FY27E non-GAAP $26.41) | **9.7x** | **3.7x** | **9.0x** |
| Peer median | ~21.5x | n/a | ~19.3x | ~5.8x | ~15.8x |
| Implied ADBE (median) | $438 | – | $515 | $333 | $423 |

Adobe is the **cheapest name in its peer group on every multiple**, at about 45–50% below peer medians, despite 30% ROIC and 89% gross margins. The gap reflects (a) fears of terminal decline, specifically that tools such as Claude Design, Canva and Figma commoditise creative work ([FX Leaders](https://www.fxleaders.com/news/2026/06/11/adobe-adbe-stock-drops-33-in-2026-amid-ai-competition-earnings-uncertainty/), [Yahoo](https://finance.yahoo.com/markets/stocks/articles/adobe-now-down-37-2026-164456666.html)), and (b) leadership turnover. ServiceNow's 84x P/E inflates the peer mean, so medians are used.

### 5.4 Dividends

Adobe pays no dividend. It returns capital through buybacks (a $25B authorisation; [TIKR](https://www.tikr.com/blog/adobe-stock-2026-outlook-q2-earnings-on-june-11-and-a-25-billion-buyback-in-place)). **The DDM does not apply.** A shareholder-yield view (buybacks plus FCF) gives an FCF yield of about 11%.

### 5.5 Growth drivers, competition, management, ESG

* **Growth drivers:** Firefly and generative AI built into Creative Cloud, an AI-first ARR line growing 150%+, the Acrobat AI Assistant, the Express freemium funnel (1B+ monthly active users), and GenStudio for enterprise content supply chains.
* **Competition:** Canva and Figma at the low and mid end, plus AI-native generation (OpenAI, Google, Anthropic's Claude Design, Midjourney). Adobe's defensible core is professional workflows, file formats (PDF, PSD), enterprise rights management, and commercially safe, indemnified models.
* **Management and strategy:** CEO **Shantanu Narayen** announced in March 2026 that he will step down once a successor is named and will remain Chair ([Fortune](https://www.fortune.com/2026/03/12/adobe-ceo-shantanu-narayen-stepping-down-after-18-years-pressure-deliver-ai)). CFO **Dan Durn left** in June 2026 and Steve Day is interim CFO ([Bloomberg Law](https://news.bloomberglaw.com/financial-accounting/adobes-cfo-departs-leaving-company-seeking-top-executives)). Internal CEO candidates are David Wadhwani and Anil Chakravarthy, and an external search is under way. The strategy is freemium user growth first, then monetisation through AI credits and agentic workflows.
* **ESG:** Positive: the Content Authenticity Initiative and Content Credentials, and models trained on licensed data. Negative: DOJ/FTC litigation (filed 2024) over subscription early-termination fees and cancellation practices, plus AI copyright and creator-relations risk. Governance: a succession vacuum at both CEO and CFO.
* **Analysts:** **Hold** consensus from 33 analysts (7 Buy, 21 Hold, 5 Sell). Average target **$282.68** (range $190–$440). DA Davidson Buy $290, Wells Fargo Overweight $270, UBS Neutral $255, Morgan Stanley Underweight $240, BofA Underperform $220 ([MarketBeat](https://www.marketbeat.com/stocks/NASDAQ/ADBE/forecast/)). **Opinion is unusually split**, with a high/low target spread of 2.3x.

### 5.6 Rule #1 / Buffett-Munger assessment

* **Understandable?** The business model (subscriptions for creative and document software) is easy to understand. **Predicting its moat 10 years out is not.** That is the heart of the circle-of-competence problem.
* **Moat: historically wide, now contested.** (1) **Switching costs:** professional skills, workflows, file formats and plug-ins. (2) **Standards and network effects:** PDF/Acrobat and PSD as industry norms. (3) **Brand and enterprise IP indemnity.** Generative AI lowers the skill barrier that sustained those switching costs, so Munger would call this "too hard" until the data settles. Evidence so far is mixed: revenue +13%, ARR and MAU rising, but net seat expansion slowing.
* **Management:** Historically excellent. ROIC is 24.9% (10y), 29.8% (5y) and 39.9% (1y); 10-year sales +17%/yr and 10-year EPS +30%/yr. BVPS growth is about 0% only because of heavy buybacks (11/15 Big Five tests pass). The Figma bid ($20B) was a capital-allocation misstep that cost a $1B break fee. Buybacks at today's prices are accretive. **The succession gap is a current negative.**
* **Margin of safety:** With a 10% growth assumption (not the 15% the data shows) and future P/E = 2 × g = 20, the **Town Sticker is only $230** (MOS $115). The blended Sticker is **$299**, giving a **buy price of $150**. At $237.69 the stock is at 0.80× Sticker. It passes **Ten Cap ($263)** and **Payback Time ($331)**: on today's cash flows it is cheap, provided those cash flows hold up.
* **Business, not stock:** a high-quality cash machine, but I would want clarity on AI economics before owning it outright. **Long term:** creative demand is exploding; the question is who captures it. **Capital allocation:** buybacks are sensible at around 9x forward earnings; the Figma attempt counts against it.

### 5.7 Key risks
1. **AI commoditisation** of creative tools leading to seat attrition and price compression. This is the main risk.
2. **Freemium monetisation lag:** user growth that does not convert to ARR.
3. **Leadership transition:** CEO search, interim CFO, possible strategy reset.
4. **Regulatory and legal:** subscription-practice litigation (FTC/DOJ), AI copyright suits, EU DMA/AI Act.
5. **Rates:** at a 5.3% risk-free rate, long-duration equity is penalised. Every +50bp of WACC costs about $20/share.

### 5.8 Conclusion: ADBE

**Intrinsic value ≈ $340 (range $230–$420). Sticker $299, buy price $150; Town-strict MOS $115.** **HOLD / WATCH LIST.** It is statistically cheap (9x forward, 11% FCF yield) but fails the "durable moat I can understand" test today. A speculative starter position is reasonable only at **≤ $200**, where the price is about 40% below DCF. Make it a full Rule #1 buy **≤ $150**, or once a permanent CEO is in place and two quarters of net-new ARR re-acceleration confirm that the moat is intact.

---

## 6. Comparative summary and ranking

| Rank | Company | Why |
|---|---|---|
| **1** | **KNSL: BUY** | Highest-quality underwriter in the US. 22–24% ROE, 75 combined ratio, founder owns 3.8%. Temporary event (soft E&S). Largest discount to DCF (−18%), and the two terminal methods agree. Smallest and least liquid of the three; insurance-cycle risk. |
| **2** | **PGR: ACCUMULATE** | Perfect 15/15 Big Five, wide cost moat, scale. Priced near fair value with EPS expected to fall about 18%. Upside to DCF about 18%; downside cushioned by a 12.8x forward P/E and capital returns. |
| **3** | **ADBE: HOLD** | The most statistically cheap, but its moat durability is uncertain and both CEO and CFO seats are in transition. Rule #1 discipline: if you can't value the moat, don't buy it, however low the multiple. |

**Portfolio view:** KNSL and PGR are both P&C insurers with partly correlated cycles but different end-markets (specialty commercial vs personal auto). Owning both is reasonable; cap combined P&C exposure.

---

## 7. Sources

**Primary filings (SEC EDGAR XBRL, via `data.sec.gov` companyfacts/frames APIs):** Progressive 10-K FY2025 ([exhibit](https://www.sec.gov/Archives/edgar/data/80661/000008066126000086/pgr-20251231exhibit99.htm)) and 2026 10-Qs and monthly 8-Ks ([May 2026 8-K](https://www.sec.gov/Archives/edgar/data/0000080661/000008066126000210/pgr202605ex992newsrelease.htm)). Kinsale 10-K FY2025, Q1-26 ([8-K](https://www.sec.gov/Archives/edgar/data/0001669162/000166916226000025/earningsrelease1q2026.htm)) and Q2-26 ([8-K](https://www.sec.gov/Archives/edgar/data/0001669162/000166916226000039/earningsrelease2q2026.htm)). Adobe 10-K FY2025, Q3-26 10-Q ([10-Q](https://www.sec.gov/Archives/edgar/data/0000796343/000079634326000156/adbe-20260828.htm)), Q3-26 8-K ([exhibit 99.1](https://www.sec.gov/Archives/edgar/data/0000796343/000079634326000147/adbeex991q326.htm)) and Q2-26 8-K ([exhibit 99.1](https://www.sec.gov/Archives/edgar/data/0000796343/000079634326000109/adbeex991q226.htm)). Form 4s and 13Ds from EDGAR submissions.
**Market data:** Yahoo Finance chart API (prices, ^TNX, ^GSPC monthly for beta), retrieved 3 Oct 2026.
**Analyst consensus:** MarketBeat ([PGR](https://www.marketbeat.com/stocks/NYSE/PGR/forecast/), [KNSL](https://www.marketbeat.com/stocks/NYSE/KNSL/forecast/), [ADBE](https://www.marketbeat.com/stocks/NASDAQ/ADBE/forecast/)); Barchart ([PGR EPS](https://www.barchart.com/story/news/2643950/here-s-what-to-expect-from-progressive-corporation-s-next-earnings-report)); TickFlow ([ADBE FY27E](https://www.tickflow.io/stock/ADBE/forecast)); Zacks via MarketBeat ([KNSL](https://www.marketbeat.com/instant-alerts/zacks-research-issues-pessimistic-outlook-for-knsl-earnings-2026-08-05/), [CB/WRB](https://www.marketbeat.com/instant-alerts/zacks-research-weighs-in-on-chubbs-q3-earnings-nysecb-2026-08-05/)).
**News and context:** [Insurance Business (PGR August)](https://www.insurancebusinessmag.com/us/news/breaking-news/progressives-combined-ratio-jumps-6-2-points-as-net-income-falls-22-590384.aspx), [BMO on PGR](https://finance.yahoo.com/news/bmo-trims-progressive-corporation-pgr-191535959.html), [PGR dividend](https://investors.progressive.com/financials/financial-news-releases/news-details/2025/Progressive-Announces-Dividend-Information-And-2026-Annual-Meeting-Record-Date/default.aspx), [Kinsale Q2-26](https://ir.kinsalecapitalgroup.com/news/news-details/2026/Kinsale-Capital-Group-Reports-Second-Quarter-2026-Results/default.aspx), [Kehoe Form 4](https://www.secform4.com/filings/1669162/0001334940-24-000007.htm), [Fortune (Adobe CEO)](https://www.fortune.com/2026/03/12/adobe-ceo-shantanu-narayen-stepping-down-after-18-years-pressure-deliver-ai), [Bloomberg Law (Adobe CFO)](https://news.bloomberglaw.com/financial-accounting/adobes-cfo-departs-leaving-company-seeking-top-executives), [Investing.com (ADBE Q3)](https://uk.investing.com/news/stock-market-news/adobe-q3-fy2026-slides-ai-revenue-soars-stock-falls-on-caution-93CH-4865585), [Trading Economics (10y)](https://tradingeconomics.com/united-states/government-bond-yield), [Philadelphia Fed SPF](https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/survey-of-professional-forecasters/2026/spfQ226.pdf), [EIA via Hellenic Shipping](https://www.hellenicshippingnews.com/eia-raises-oil-price-forecasts-as-middle-east-supply-drops/), [StockWire (ERP)](https://stockwirex.com/?p=44108).
**Method reference:** Phil Town, *Rule #1* (2006) and *Payback Time* (2010); Damodaran, *Investment Valuation* (3rd ed.) for insurer valuation and the Blume beta adjustment.

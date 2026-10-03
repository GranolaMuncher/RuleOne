"""Single-company deep dive: DCF (perpetuity + exit multiple), CAPM WACC,
peer comps, DDM, Rule #1 Sticker / MOS / Payback / Ten Cap.

    python -m ruleone.deepdive reports/config/MSFT.json

The JSON config holds every judgement-based assumption so the valuation is
auditable and re-runnable; anything omitted falls back to data-driven defaults.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from statistics import mean, median

from .companyfacts import load_company
from .http import Fetcher
from .metrics import big_five, fcf, normalize_splits, windage_growth
from .prices import beta, load_prices, load_share_fallback, price_near
from .universe import load_universe
from .valuation import (DCFInputs, WACC, dcf, dcf_sensitivity, gordon, historical_pe, payback_price,
                        sticker_price, ten_cap_price, two_stage_ddm)


def fade(start: float, end: float, n: int) -> list[float]:
    if n == 1:
        return [end]
    return [start + (end - start) * i / (n - 1) for i in range(n)]


def snapshot(fetcher: Fetcher, listing, today: date) -> dict:
    """Financials + market data used by comps and the DCF."""
    cf = load_company(fetcher, listing.cik)
    px = load_prices(fetcher, listing.ticker)
    t, L = cf["ttm"], cf["latest"]
    if t.get("op_income") is None and t.get("pretax") is not None:
        # insurers/financials report no operating-income line: EBIT ~= pre-tax + interest
        t["op_income"] = t["pretax"] + (t.get("interest") or 0)
    shares = L.get("diluted_shares") if L.get("diluted_shares_date") and \
        (today - date.fromisoformat(L["diluted_shares_date"])).days < 460 else None
    eps = t.get("eps")
    if not shares or not eps:
        yf = load_share_fallback(fetcher, listing.ticker)
        shares = shares or yf.get("quarterlyDilutedAverageShares")
        eps = eps or yf.get("trailingDilutedEPS")
    price = px["price"]
    mcap = price * shares
    debt = (L.get("lt_debt") or 0) + (L.get("debt_current") or 0)
    cash = L.get("cash") or 0
    ebitda = (t.get("op_income") or 0) + (t.get("da") or 0)
    f = fcf(t)
    return {"ticker": listing.ticker, "name": cf["name"], "cf": cf, "px": px, "price": price,
            "shares": shares, "eps_ttm": eps, "mcap": mcap, "debt": debt, "cash": cash,
            "ev": mcap + debt - cash, "ebitda": ebitda, "revenue": t.get("revenue"), "fcf": f,
            "pe_ttm": price / eps if eps and eps > 0 else None,
            "ev_ebitda": (mcap + debt - cash) / ebitda if ebitda > 0 else None,
            "ps": mcap / t["revenue"] if t.get("revenue") else None,
            "pfcf": mcap / f if f and f > 0 else None}


def _m(v, k=""):
    if v is None:
        return "n/a"
    if k == "%":
        return f"{v*100:.1f}%"
    if k == "$":
        return f"${v:,.2f}"
    if k == "B":
        return f"${v/1e9:,.1f}B"
    if k == "x":
        return f"{v:.1f}x"
    return f"{v:,.2f}"


def run(cfg: dict, fetcher: Fetcher, today: date | None = None) -> tuple[str, dict]:
    today = today or date.today()
    uni = {l.ticker: l for l in load_universe(fetcher).values()}
    tgt = snapshot(fetcher, uni[cfg["ticker"]], today)
    cf, t, L = tgt["cf"], tgt["cf"]["ttm"], tgt["cf"]["latest"]
    annual = normalize_splits(cf["annual"])
    b5 = big_five(cf["annual"])
    fwd = cfg.get("forward_eps", {})

    # ---------------- WACC
    tnx = load_prices(fetcher, "^TNX", rng="5d", interval="1d")
    rf = cfg.get("rf") or (tnx["price"] / 100 if tnx else 0.043)
    mkt = load_prices(fetcher, "^GSPC", rng="10y", interval="1mo")
    b_raw = beta(tgt["px"]["series"], mkt["series"]) if mkt else None
    b_adj = cfg.get("beta") or (0.67 * b_raw + 0.33 if b_raw else 1.0)    # Blume adjustment
    erp = cfg.get("erp", 0.045)
    interest = t.get("interest")
    kd = cfg.get("pre_tax_cost_of_debt") or (min(max(interest / tgt["debt"], rf), rf + 0.04)
                                            if interest and tgt["debt"] else rf + 0.01)
    tax = cfg.get("tax_rate") or (min(max(t["tax"] / t["pretax"], 0.10), 0.30)
                                  if t.get("tax") and t.get("pretax") else 0.21)
    w = WACC(rf=rf, beta=b_adj, erp=erp, pre_tax_cost_of_debt=kd, tax_rate=tax,
             equity_value=tgt["mcap"], debt_value=tgt["debt"], size_premium=cfg.get("size_premium", 0.0))
    wacc = cfg.get("wacc_override") or w.wacc

    # ---------------- DCF
    n = cfg.get("years", 10)
    rev0 = t["revenue"]
    m0 = t["op_income"] / rev0
    d = cfg.get("dcf", {})
    growth = d.get("growth") or fade(d.get("g_start", 0.10), d.get("g_end", 0.04), n)
    margin = d.get("margin") or fade(d.get("margin_start", m0), d.get("margin_end", m0), n)
    da0 = (t.get("da") or 0) / rev0
    cx0 = abs(t.get("capex") or 0) / rev0
    da = fade(d.get("da_start", da0), d.get("da_end", da0), n)
    cx = fade(d.get("capex_start", cx0), d.get("capex_end", max(da0, cx0 * 0.8)), n)
    inp = DCFInputs(revenue0=rev0, growth=growth, ebit_margin=margin, tax_rate=d.get("dcf_tax", tax),
                    da_pct=da, capex_pct=cx, nwc_pct_of_delta_rev=d.get("nwc_pct", 0.05), wacc=wacc,
                    terminal_growth=d.get("terminal_growth", 0.03), exit_multiple=d.get("exit_multiple", 15.0),
                    net_debt=tgt["debt"] - tgt["cash"], shares=tgt["shares"])
    res = dcf(inp)
    sens_w = [wacc - 0.01, wacc - 0.005, wacc, wacc + 0.005, wacc + 0.01]
    sens_g = [inp.terminal_growth - 0.01, inp.terminal_growth - 0.005, inp.terminal_growth,
              inp.terminal_growth + 0.005, inp.terminal_growth + 0.01]
    sens = dcf_sensitivity(inp, sens_w, sens_g)

    # ---------------- Comps
    peers = [snapshot(fetcher, uni[p], today) for p in cfg.get("peers", []) if p in uni]
    for s in [tgt] + peers:
        fe = fwd.get(s["ticker"])
        s["pe_fwd"] = s["price"] / fe if fe else None
    keys = [("pe_ttm", "eps_ttm"), ("pe_fwd", None), ("ev_ebitda", "ebitda"), ("ps", "revenue"), ("pfcf", "fcf")]
    stats, implied = {}, {}
    for k, base in keys:
        vals = [p[k] for p in peers if p[k] and 0 < p[k] < 150]
        if not vals:
            continue
        stats[k] = {"min": min(vals), "max": max(vals), "mean": mean(vals), "median": median(vals)}
        if k == "pe_ttm":
            per = lambda m: m * tgt["eps_ttm"]
        elif k == "pe_fwd" and fwd.get(tgt["ticker"]):
            per = lambda m: m * fwd[tgt["ticker"]]
        elif k == "ev_ebitda":
            per = lambda m: (m * tgt["ebitda"] - tgt["debt"] + tgt["cash"]) / tgt["shares"]
        elif k == "ps":
            per = lambda m: m * tgt["revenue"] / tgt["shares"]
        elif k == "pfcf" and tgt["fcf"] and tgt["fcf"] > 0:
            per = lambda m: m * tgt["fcf"] / tgt["shares"]
        else:
            continue
        implied[k] = {s: per(stats[k][s]) for s in ("min", "median", "mean", "max")}

    # ---------------- DDM
    dps_hist = {y: r["dps"] for y, r in annual.items() if r.get("dps")}
    ddm = None
    dd = cfg.get("ddm", {})
    if dps_hist and not dd.get("skip"):
        ys = sorted(dps_hist)
        d0 = L.get("dps_latest") if dd.get("use_latest_dps") else dps_hist[ys[-1]]
        d0 = dd.get("d0", d0)
        g5 = (dps_hist[ys[-1]] / dps_hist[ys[-6]]) ** (1 / 5) - 1 if len(ys) >= 6 and dps_hist[ys[-6]] > 0 else None
        g10 = (dps_hist[ys[-1]] / dps_hist[ys[-11]]) ** (1 / 10) - 1 if len(ys) >= 11 and dps_hist[ys[-11]] > 0 else None
        ke = w.cost_of_equity
        g1, g2, yrs = dd.get("g1", g5 or 0.05), dd.get("g2", 0.04), dd.get("years", 10)
        ddm = {"d0": d0, "g5": g5, "g10": g10, "ke": ke, "g1": g1, "g2": g2, "years": yrs,
               "payout": (d0 / tgt["eps_ttm"]) if tgt["eps_ttm"] else None,
               "gordon": gordon(d0, g2, ke), "two_stage": two_stage_ddm(d0, g1, yrs, g2, ke)["value"],
               "history": {y: dps_hist[y] for y in ys[-11:]}}

    # ---------------- Rule #1
    eps_by_end = {r["end"]: r["eps"] for r in annual.values() if r.get("eps")}
    hpe = historical_pe(eps_by_end, lambda dd_: price_near(tgt["px"]["series"], dd_))
    g_hist = windage_growth(b5)
    g_r1 = cfg.get("rule1_growth", g_hist)
    st = sticker_price(tgt["eps_ttm"], g_r1, hpe["median"])
    pb = payback_price(tgt["fcf"], tgt["shares"], g_r1)
    tc = ten_cap_price(tgt["fcf"], tgt["shares"])

    out = {"ticker": tgt["ticker"], "price": tgt["price"], "price_date": tgt["px"]["as_of"],
           "wacc": wacc, "ke": w.cost_of_equity, "beta_raw": b_raw, "beta": b_adj, "rf": rf, "erp": erp,
           "kd": kd, "tax": tax, "we": w.we, "wd": w.wd,
           "dcf_perp": res.per_share_perpetuity, "dcf_exit": res.per_share_exit,
           "implied_exit_from_perp": res.implied_exit_multiple_from_perp,
           "implied_g_from_exit": res.implied_growth_from_exit,
           "comps": implied, "comp_stats": stats, "ddm": ddm, "sticker": st, "payback": pb, "ten_cap": tc,
           "hist_pe": hpe, "g_hist": g_hist, "g_r1": g_r1, "big5": b5}

    # ---------------- Markdown
    md = [f"### Model output: {tgt['name']} ({tgt['ticker']}), price {_m(tgt['price'],'$')} as of {tgt['px']['as_of']}\n"]
    md.append("\n**Financial snapshot** (SEC XBRL; FY = fiscal year, TTM through " + str(t.get("_end")) + ")\n\n")
    yrs = sorted(annual)[-4:]
    md.append("| Metric | " + " | ".join(f"FY{y}" for y in yrs) + " | TTM |\n|---|" + "---|" * (len(yrs) + 1) + "\n")
    for lab, k in (("Revenue", "revenue"), ("Gross profit", "gross_profit"), ("Operating income", "op_income"),
                   ("Net income", "net_income"), ("Operating cash flow", "ocf"), ("CapEx", "capex")):
        md.append(f"| {lab} | " + " | ".join(_m(annual[y].get(k), "B") for y in yrs) + f" | {_m(t.get(k),'B')} |\n")
    md.append("| Free cash flow | " + " | ".join(_m(fcf(annual[y]), "B") for y in yrs) + f" | {_m(tgt['fcf'],'B')} |\n")
    md.append("| Diluted EPS | " + " | ".join(_m(annual[y].get("eps"), "$") for y in yrs) + f" | {_m(tgt['eps_ttm'],'$')} |\n")
    md.append(f"\nBalance sheet (latest): cash {_m(tgt['cash'],'B')}, debt {_m(tgt['debt'],'B')}, equity "
              f"{_m(L.get('equity'),'B')}; diluted shares {tgt['shares']/1e9:,.3f}B; market cap {_m(tgt['mcap'],'B')}; "
              f"EV {_m(tgt['ev'],'B')}.\n")
    md.append(f"\n**WACC**: Rf {_m(rf,'%')} (10y UST, ^TNX) + β {b_adj:.2f} (raw 5y monthly vs S&P 500 "
              f"{_m(b_raw)}; Blume-adjusted) × ERP {_m(erp,'%')} = Ke **{_m(w.cost_of_equity,'%')}**. "
              f"Kd {_m(kd,'%')} pre-tax × (1 − {_m(tax,'%')}) = {_m(w.after_tax_cost_of_debt,'%')}. "
              f"Weights E {_m(w.we,'%')} / D {_m(w.wd,'%')} → **WACC {_m(wacc,'%')}**.\n")
    md.append(f"\n**DCF ({n}-yr, mid-year convention)** — $B\n\n| Yr | Revenue | Growth | EBIT margin | NOPAT | D&A | CapEx | ΔNWC | FCF | PV |\n|---|---|---|---|---|---|---|---|---|---|\n")
    for r in res.rows:
        md.append(f"| {r['year']} | {r['revenue']/1e9:,.1f} | {r['growth']*100:.1f}% | {r['margin']*100:.1f}% | "
                  f"{r['nopat']/1e9:,.1f} | {r['da']/1e9:,.1f} | {r['capex']/1e9:,.1f} | {r['dnwc']/1e9:,.1f} | "
                  f"{r['fcf']/1e9:,.1f} | {r['pv']/1e9:,.1f} |\n")
    md.append(f"\nPV of FCF {_m(res.pv_fcf,'B')}. Terminal value — perpetuity (g = {_m(inp.terminal_growth,'%')}): "
              f"TV {_m(res.tv_perpetuity,'B')}, PV {_m(res.pv_tv_perpetuity,'B')} → EV {_m(res.ev_perpetuity,'B')} → "
              f"**{_m(res.per_share_perpetuity,'$')}/share** (implies {res.implied_exit_multiple_from_perp:.1f}x terminal EBITDA). "
              f"Exit multiple ({inp.exit_multiple:.1f}x EBITDA): TV {_m(res.tv_exit,'B')}, PV {_m(res.pv_tv_exit,'B')} → "
              f"EV {_m(res.ev_exit,'B')} → **{_m(res.per_share_exit,'$')}/share** (implies g = {_m(res.implied_growth_from_exit,'%')}). "
              f"Net debt {_m(inp.net_debt,'B')}.\n")
    md.append("\nSensitivity, perpetuity method ($/share): rows WACC, columns terminal g\n\n| WACC \\ g | "
              + " | ".join(f"{g*100:.1f}%" for g in sens_g) + " |\n|---|" + "---|" * len(sens_g) + "\n")
    for wv, row in zip(sens_w, sens):
        md.append(f"| {wv*100:.1f}% | " + " | ".join(f"${v:,.0f}" for v in row) + " |\n")
    md.append("\n**Comparable companies** (TTM; forward P/E uses next-FY consensus EPS supplied in config)\n\n"
              "| Company | Price | Mkt cap | P/E TTM | P/E fwd | EV/EBITDA | P/S | P/FCF |\n|---|---|---|---|---|---|---|---|\n")
    for s in [tgt] + peers:
        bold = "**" if s is tgt else ""
        md.append(f"| {bold}{s['ticker']}{bold} | {_m(s['price'],'$')} | {_m(s['mcap'],'B')} | {_m(s['pe_ttm'],'x')} | "
                  f"{_m(s['pe_fwd'],'x')} | {_m(s['ev_ebitda'],'x')} | {_m(s['ps'],'x')} | {_m(s['pfcf'],'x')} |\n")
    for lab, k in (("Peer median", "median"), ("Peer mean", "mean"), ("Peer low", "min"), ("Peer high", "max")):
        md.append(f"| _{lab}_ | | | " + " | ".join(_m(stats.get(c, {}).get(k), "x")
                                                     for c in ("pe_ttm", "pe_fwd", "ev_ebitda", "ps", "pfcf")) + " |\n")
    md.append("\nImplied value per share from peer multiples:\n\n| Multiple | Low | Median | Mean | High |\n|---|---|---|---|---|\n")
    for k, lab in (("pe_ttm", "P/E TTM"), ("pe_fwd", "P/E fwd"), ("ev_ebitda", "EV/EBITDA"), ("ps", "P/S"), ("pfcf", "P/FCF")):
        if k in implied:
            v = implied[k]
            md.append(f"| {lab} | {_m(v['min'],'$')} | {_m(v['median'],'$')} | {_m(v['mean'],'$')} | {_m(v['max'],'$')} |\n")
    if ddm:
        md.append(f"\n**Dividends**: DPS history " + ", ".join(f"FY{y} ${v:.2f}" for y, v in ddm["history"].items())
                  + f". 5y DPS CAGR {_m(ddm['g5'],'%')}, 10y {_m(ddm['g10'],'%')}; payout {_m(ddm['payout'],'%')} of TTM EPS. "
                  f"Ke {_m(ddm['ke'],'%')}. Gordon (D0 {_m(ddm['d0'],'$')}, g {_m(ddm['g2'],'%')}): **{_m(ddm['gordon'],'$')}**; "
                  f"two-stage ({ddm['years']}y at {_m(ddm['g1'],'%')}, then {_m(ddm['g2'],'%')}): **{_m(ddm['two_stage'],'$')}**.\n")
    else:
        md.append("\n**Dividends**: no common dividend; DDM not applicable.\n")
    g = b5
    md.append(f"\n**Rule #1 Big Five** (10y / 5y / 1y): ROIC {_m(g.get('roic10'),'%')} / {_m(g.get('roic5'),'%')} / {_m(g.get('roic1'),'%')}; "
              f"Sales {_m(g.get('sales_g10'),'%')} / {_m(g.get('sales_g5'),'%')} / {_m(g.get('sales_g1'),'%')}; "
              f"EPS {_m(g.get('eps_g10'),'%')} / {_m(g.get('eps_g5'),'%')} / {_m(g.get('eps_g1'),'%')}; "
              f"BVPS {_m(g.get('bvps_g10'),'%')} / {_m(g.get('bvps_g5'),'%')} / {_m(g.get('bvps_g1'),'%')}; "
              f"OCF {_m(g.get('ocf_g10'),'%')} / {_m(g.get('ocf_g5'),'%')} / {_m(g.get('ocf_g1'),'%')}. "
              f"Tests passed {g['tests_passed']}/{g['tests_total']}. LT debt / FCF = {_m(g.get('debt_payoff_years'))} yrs.\n")
    if st:
        md.append(f"\n**Sticker Price**: EPS {_m(tgt['eps_ttm'],'$')} × (1 + {_m(g_r1,'%')})^10 = {_m(st['future_eps'],'$')} "
                  f"× future P/E {st['future_pe']:.1f} (min of 2×g = {2*g_r1*100:.1f} and 10y median P/E {_m(hpe['median'])}; avg {_m(hpe['avg'])}) = "
                  f"{_m(st['future_price'],'$')} ÷ 1.15^10 = **{_m(st['sticker'],'$')}**; MOS (50%) **{_m(st['mos_price'],'$')}**. "
                  f"Payback-Time (8y) price {_m(pb,'$')}; Ten Cap price {_m(tc,'$')}. "
                  f"Data-driven windage growth was {_m(g_hist,'%')}.\n")
    return "".join(md), out


def main(argv=None):
    argv = argv or sys.argv[1:]
    cfg = json.loads(Path(argv[0]).read_text())
    md, out = run(cfg, Fetcher(".cache"))
    dest = Path(argv[1]) if len(argv) > 1 else Path("reports/model") / f"{cfg['ticker']}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(md)
    dest.with_suffix(".json").write_text(json.dumps(out, indent=2, default=str))
    print(md)


if __name__ == "__main__":
    main()

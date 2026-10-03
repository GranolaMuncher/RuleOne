"""Catalyst / "event" detection from SEC EDGAR.

In Rule #1 an *event* is usually temporary bad news that knocks a wonderful
company's price below its margin-of-safety price. We surface:
  * recent 8-K items (flagging negative ones: restructuring, impairment,
    exec departures, restatements, cyber incidents, delisting notices)
  * insider open-market purchases (Form 4, transaction code "P")
  * activist stakes (SC 13D)
  * price drawdown from the 52-week high
  * estimated next earnings date (last 10-Q/10-K + ~91 days)
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .http import Fetcher

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"

ITEM_NAMES = {
    "1.01": "Material agreement", "1.02": "Agreement terminated", "1.03": "Bankruptcy",
    "1.05": "Cybersecurity incident", "2.01": "Acquisition/disposition", "2.02": "Earnings release",
    "2.03": "New debt obligation", "2.04": "Debt acceleration", "2.05": "Restructuring/exit costs",
    "2.06": "Material impairment", "3.01": "Delisting notice", "3.02": "Unregistered equity sale",
    "4.01": "Auditor change", "4.02": "Prior financials unreliable", "5.01": "Change in control",
    "5.02": "Director/officer change", "5.03": "Charter/bylaw amendment", "5.07": "Shareholder vote",
    "7.01": "Reg FD disclosure", "8.01": "Other event", "9.01": "Exhibits",
}
NEGATIVE_ITEMS = {"1.02", "1.03", "1.05", "2.04", "2.05", "2.06", "3.01", "4.01", "4.02"}
ROUTINE_ITEMS = {"9.01", "5.07", "5.03"}


def _recent(sub: dict):
    r = sub.get("filings", {}).get("recent", {})
    keys = ["form", "filingDate", "accessionNumber", "primaryDocument", "items"]
    cols = [r.get(k, []) for k in keys]
    for vals in zip(*cols):
        yield dict(zip(keys, vals))


def _form4_purchases(fetcher: Fetcher, cik: int, f: dict) -> tuple[float, int]:
    """(dollars bought, shares bought) for open-market 'P' transactions in a Form 4."""
    doc = re.sub(r"^xsl[^/]+/", "", f["primaryDocument"])
    url = ARCHIVE_URL.format(cik=cik, acc=f["accessionNumber"].replace("-", ""), doc=doc)
    try:
        xml = fetcher.get_text_cached(url) or ""
    except Exception:
        return 0.0, 0
    dollars, shares = 0.0, 0
    for tx in re.findall(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", xml, re.S):
        code = re.search(r"<transactionCode>\s*(\w)\s*</transactionCode>", tx)
        if not code or code.group(1) != "P":
            continue
        sh = re.search(r"<transactionShares>\s*<value>\s*([\d.]+)", tx)
        px = re.search(r"<transactionPricePerShare>\s*<value>\s*([\d.]+)", tx)
        if sh:
            n = float(sh.group(1))
            shares += int(n)
            dollars += n * float(px.group(1)) if px else 0.0
    return dollars, shares


def load_events(fetcher: Fetcher, cik: int, prices: dict | None = None, today: date | None = None,
                lookback_8k: int = 60, lookback_f4: int = 120, max_form4: int = 12) -> dict:
    today = today or date.today()
    sub = fetcher.get_json(SUBMISSIONS_URL.format(cik=cik), ttl_hours=12) or {}
    ev = {"8k": [], "negative_8k": [], "insider_buy_usd": 0.0, "insider_buys": 0,
          "activist_13d": [], "last_periodic": None, "next_earnings_est": None, "sic": sub.get("sicDescription")}
    f4_checked = 0
    for f in _recent(sub):
        fd = date.fromisoformat(f["filingDate"])
        age = (today - fd).days
        form = f["form"]
        if form in ("20-F", "40-F", "6-K"):
            ev["foreign_filer"] = True
        if form in ("10-Q", "10-K", "20-F", "40-F") and ev["last_periodic"] is None:
            ev["last_periodic"] = f"{form} {f['filingDate']}"
            nxt = fd + timedelta(days=91 if form == "10-Q" else 70)
            while nxt < today:          # filing overdue in our estimate: roll to next quarter
                nxt += timedelta(days=91)
            ev["next_earnings_est"] = nxt.isoformat()
        if form == "8-K" and age <= lookback_8k:
            items = [i.strip() for i in (f.get("items") or "").split(",") if i.strip()]
            named = [f"{i} {ITEM_NAMES.get(i, '')}".strip() for i in items if i not in ROUTINE_ITEMS]
            if named:
                ev["8k"].append(f"{f['filingDate']}: " + "; ".join(named))
            neg = [ITEM_NAMES.get(i, i) for i in items if i in NEGATIVE_ITEMS]
            if neg:
                ev["negative_8k"].append(f"{f['filingDate']}: " + "; ".join(neg))
        # 13Ds the company itself filed (about other issuers) share its CIK prefix
        if form in ("SC 13D", "SC 13D/A", "SCHEDULE 13D", "SCHEDULE 13D/A") and age <= 180 \
                and int(f["accessionNumber"].split("-")[0]) != cik:
            ev["activist_13d"].append(f"{form} {f['filingDate']}")
        if form == "4" and age <= lookback_f4 and f4_checked < max_form4:
            f4_checked += 1
            usd, sh = _form4_purchases(fetcher, cik, f)
            if sh:
                ev["insider_buys"] += 1
                ev["insider_buy_usd"] += usd
    if prices and prices.get("price") and prices.get("high52"):
        ev["drawdown_52w"] = prices["price"] / prices["high52"] - 1
    return ev


def event_summary(ev: dict) -> str:
    parts = []
    dd = ev.get("drawdown_52w")
    if dd is not None and dd <= -0.20:
        parts.append(f"{dd:.0%} off 52w high")
    if ev.get("insider_buys"):
        parts.append(f"insider buying ({ev['insider_buys']} Form 4s, ${ev['insider_buy_usd']/1e6:.2f}M)")
    if ev.get("negative_8k"):
        parts.append("neg 8-K: " + " | ".join(ev["negative_8k"][:2]))
    if ev.get("activist_13d"):
        parts.append("13D: " + ", ".join(ev["activist_13d"][:2]))
    other = [x for x in ev.get("8k", []) if x not in ev.get("negative_8k", [])]
    if other and not ev.get("negative_8k"):
        parts.append("8-K: " + other[0])
    if ev.get("next_earnings_est"):
        parts.append(f"next report ~{ev['next_earnings_est']}")
    return "; ".join(parts)


def event_score(ev: dict) -> float:
    """Higher = more of a Rule #1 style opportunity signal."""
    s = 0.0
    dd = ev.get("drawdown_52w")
    if dd is not None:
        s += min(max(-dd - 0.10, 0.0), 0.5) * 4        # up to +2 for a 60% drawdown
    if ev.get("insider_buys"):
        s += 1.0 + min(ev.get("insider_buy_usd", 0) / 5e6, 1.0)
    if ev.get("activist_13d"):
        s += 0.5
    if ev.get("negative_8k"):
        s += 0.5                                         # bad news = possible over-reaction
    return round(s, 2)

"""The investable universe: every SEC registrant with a NYSE or Nasdaq listing."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .http import Fetcher

TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"

# Shell companies / blank checks rarely have a meaningful record to screen.
_SPAC_RE = re.compile(r"\b(acquisition|capital) corp(oration)?\b.*\b(i{1,3}|iv|v|vi{0,3}|\d+)?\b|"
                      r"\bacquisition (corp|co|company|inc|ltd)\b", re.I)


@dataclass
class Listing:
    cik: int
    ticker: str
    name: str
    exchange: str


def _is_common(ticker: str) -> bool:
    """Keep share classes (BRK-B, BF-B); drop preferreds (BAC-PL, ETI-P), units
    (KCAC-UN), warrants/rights and 5-letter Nasdaq unit/warrant suffixes."""
    if "-" in ticker:
        suffix = ticker.split("-", 1)[1]
        if len(suffix) != 1 or suffix == "P":
            return False
    if len(ticker) == 5 and ticker[-1] in "WURZ":
        return False
    return True


def load_universe(fetcher: Fetcher, exchanges=("NYSE", "Nasdaq")) -> dict[int, Listing]:
    """One primary common-stock listing per CIK (the SEC file is market-cap ordered,
    so the first ticker seen for a CIK is its primary line)."""
    data = fetcher.get_json(TICKERS_URL, ttl_hours=24)
    out: dict[int, Listing] = {}
    for cik, name, ticker, exch in data["data"]:
        if exch not in exchanges or not ticker or cik in out:
            continue
        if not _is_common(ticker) or _SPAC_RE.search(name or ""):
            continue
        out[cik] = Listing(cik=cik, ticker=ticker, name=name, exchange=exch)
    return out

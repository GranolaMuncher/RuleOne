from ruleone.health import anomalies, coverage


def test_anomalies_catch_extraction_bugs():
    rows = [
        {"ticker": "OK", "price": "100", "pe": "20", "div_yield": "0.02", "sticker": "120", "market_cap": "5e9",
         "revenue": "1e9", "ten_cap_price": "90"},
        {"ticker": "NOVA", "price": "396", "pe": "50", "market_cap": "1.3e7", "revenue": "8.8e8", "ten_cap_price": "66437"},
        {"ticker": "JUMP", "price": "10", "sticker": "40"},
        {"ticker": "NOPX", "price": ""},
        {"ticker": "TR", "price": "5", "tr_10y": "1.4", "pe": "3", "div_yield": "0.4"},
    ]
    prev = [{"ticker": "JUMP", "sticker": "20"}, {"ticker": "OK", "sticker": "110"}]
    a = anomalies(rows, prev)
    assert a["share_scale_suspect"] == ["NOVA"] and a["ten_cap_over_20x_price"] == ["NOVA"]
    assert a["sticker_jump_50pct"] == ["JUMP"] and a["missing_price"] == ["NOPX"]
    assert a["total_return_above_100pct"] == ["TR"] and a["pe_below_4"] == ["TR"] and a["yield_above_25pct"] == ["TR"]
    c = coverage(rows)
    assert c["rows"] == 5 and c["with_price"] == 0.8

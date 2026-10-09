from ruleone.radar import parse_13f, watch_list

XML = """<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
<infoTable><nameOfIssuer>ALLY FINL INC</nameOfIssuer><cusip>02005N100</cusip><value>500</value>
<shrsOrPrnAmt><sshPrnamt>10</sshPrnamt></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>ALLY FINL INC</nameOfIssuer><cusip>02005N100</cusip><value>100</value>
<shrsOrPrnAmt><sshPrnamt>2</sshPrnamt></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><cusip>037833100</cusip><value>900</value>
<shrsOrPrnAmt><sshPrnamt>5</sshPrnamt></shrsOrPrnAmt><putCall>Put</putCall></infoTable>
</informationTable>"""


def test_parse_13f_merges_rows_and_skips_options():
    h = parse_13f(XML)
    assert set(h) == {"02005N100"}
    assert h["02005N100"]["value"] == 600 and h["02005N100"]["shares"] == 12


def test_watch_list_puts_actionable_names_first():
    def row(t, status, tier, qp="yes", mcap="1e9"):
        return {"ticker": t, "status": status, "tier": tier, "quality_pass": qp, "market_cap": mcap}
    uni = [row("X", "ABOVE STICKER", "C"), row("A", "ON DECK", "B"), row("B", "BUY", "C"),
           row("C", "ABOVE STICKER", "A"), row("G", "ABOVE STICKER", "B", qp="")]
    gurus = {"by_ticker": {"G": [{"weight": 0.05}]}}
    assert [r["ticker"] for r in watch_list(uni, gurus)] == ["B", "A", "C", "G"]

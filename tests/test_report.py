"""Tests for solguard.report -- the self-contained HTML report generator.

Keeps the project's discipline: pure function, deterministic on a fixed risk
record, asserting on semantic structure rather than exact bytes."
"""
import pytest

from solguard.report import check_verdict, rationale, rationale_for_all_ids, render_html

FAIL = {"id": "mint_authority", "label": "Mint authority disabled",
        "pass": False, "detail": "LIVE: abc can mint unlimited tokens"}
WARN = {"id": "holder_concentration", "label": "Holder concentration (top-10)",
        "pass": None, "unknown": False, "detail": "top-10 hold 40.0% of supply"}
UNK = {"id": "holder_concentration", "label": "Holder concentration (top-10)",
       "pass": None, "unknown": True, "detail": "could not verify (RPC throttled)"}
PASS = {"id": "supply_sane", "label": "Supply is sane (>0)", "pass": True,
        "detail": "circulating supply 1e9"}

RISK = {
    "checks": [FAIL, WARN, UNK, PASS],
    "score": 65,
    "clean": False,
    "failed": 1,
    "warned": 1,
    "unknown": 1,
    "mint": {"address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"},
    "supply": {"amount": "1000000", "ui_amount": 1000000.0},
    "top_holders": None,
    "top10_pct": None,
}


def test_html_is_complete_document():
    html = render_html(RISK, market=None, mint_addr="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    assert html.startswith("<!DOCTYPE html>")
    assert html.rstrip().endswith("</html>")
    assert "<title>solguard due-diligence" in html


def test_html_shows_addr_and_score():
    html = render_html(RISK, mint_addr="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    assert "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" in html
    assert "65" in html  # score


def test_html_renders_all_verdict_badges():
    html = render_html(RISK)
    for badge in ("PASS", "WARN", "FAIL", "?"):
        assert badge in html


def test_html_surfaces_unknown_as_not_scored():
    html = render_html(RISK)
    assert "NOT scored as passed" in html
    assert "incomplete" in html.lower()


def test_html_includes_market_when_provided():
    market = {"dex": "orca", "price_usd": 0.0039, "liquidity_usd": 21700000.0,
              "volume_24h_usd": 5000000.0, "fdv_usd": 3300000000.0,
              "market_cap_usd": 3300000000.0}
    html = render_html(RISK, market=market)
    assert "orca" in html
    assert "$21,700,000" in html or "21700000" in html


def test_html_omits_market_when_absent():
    html = render_html(RISK, market=None)
    assert "Market depth" not in html


def test_check_verdict_labels():
    assert check_verdict(FAIL) == "FAIL"
    assert check_verdict(WARN) == "WARN"
    assert check_verdict(UNK) == "UNKNOWN"
    assert check_verdict(PASS) == "PASS"


def test_rationale_covers_all_scored_ids():
    known = rationale_for_all_ids()
    for c in (FAIL, WARN, UNK, PASS):
        assert c["id"] in known
        assert len(rationale(c["id"])) > 0


def test_rationale_fallback_for_unknown_id():
    assert "on-chain detail" in rationale("no_such_check")

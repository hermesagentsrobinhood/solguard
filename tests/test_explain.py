"""Unit tests for the plain-language verdict narrative (src/solguard/explain.py)."""
import pytest

from solguard.explain import explain, _tag, _plural


def _risk(checks, score=100, failed=0, warned=0, unknown=0, clean=True):
    return {
        "checks": checks,
        "score": score,
        "clean": clean,
        "failed": failed,
        "warned": warned,
        "unknown": unknown,
    }


def test_clean_narrative_mentions_clean_and_no_fail():
    r = _risk([
        {"id": "mint_authority", "label": "Mint authority disabled",
         "pass": True, "unknown": False},
        {"id": "freeze_authority", "label": "Freeze authority disabled",
         "pass": True, "unknown": False},
        {"id": "supply_sane", "label": "Supply is sane (>0)",
         "pass": True, "unknown": False},
    ])
    t = explain(r)
    assert t.startswith("CLEAN")
    assert "100/100" in t
    assert "FAILS" not in t


def test_fail_narrative_names_rug_vector():
    r = _risk([
        {"id": "mint_authority", "label": "Mint authority disabled",
         "pass": False, "unknown": False},
    ], score=75, failed=1, clean=False)
    t = explain(r)
    assert "CAUTION" in t
    assert "rug vector" in t
    assert "unlimited number of tokens" in t


def test_unknown_is_never_scored_passed():
    r = _risk([
        {"id": "holder_concentration", "label": "Holder concentration (top-10)",
         "pass": None, "unknown": True},
    ], score=100, unknown=1, clean=False)
    t = explain(r)
    assert "could NOT be verified" in t
    assert "not scored as passed" in t


def test_warning_pluralisation():
    warns = [{"id": "x", "label": "Some check", "pass": None, "unknown": False}]
    assert _plural(warns, "is a warning", "are warnings") == "is a warning"
    assert _plural([warns[0], warns[0]], "is a warning", "are warnings") == "are warnings"


def test_market_depth_injected():
    r = _risk([
        {"id": "mint_authority", "label": "Mint authority disabled",
         "pass": True, "unknown": False},
    ])
    t = explain(r, market={"liquidity_usd": 571000, "volume_24h_usd": 1_250_000,
                           "price_usd": 0.012, "dex": "Orca"})
    assert "$571,000" in t
    assert "Orca" in t


def test_tag_mapping():
    assert _tag(_risk([], clean=True)) == "CLEAN"
    assert _tag(_risk([], clean=False, failed=1)) == "CAUTION"
    assert _tag(_risk([], clean=False, unknown=1)) == "INCOMPLETE"
    assert _tag(_risk([], clean=False)) == "WATCH"


def test_risk_note_always_present():
    t = explain(_risk([]))
    assert "buy/sell recommendation" in t

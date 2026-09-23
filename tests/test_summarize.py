"""Unit tests for the portfolio summariser (no RPC, deterministic mocks)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from solguard.summarize import risk_tag, summarize, render_table


def _risk(score, failed=0, warned=0, unknown=0, mint="mint"):
    clean = failed == 0 and warned == 0 and unknown == 0
    return {
        "mint_addr": mint,
        "score": score,
        "failed": failed,
        "warned": warned,
        "unknown": unknown,
        "clean": clean,
    }


def test_risk_tag_classification():
    assert risk_tag(_risk(100)) == "CLEAN"
    assert risk_tag(_risk(30, failed=1, unknown=2)) == "CAUTION"   # a fail dominates
    assert risk_tag(_risk(90, warned=1)) == "WATCH"
    assert risk_tag(_risk(40, unknown=3)) == "INCOMPLETE"         # no fail, some unknown


def test_summarize_sorts_riskiest_first_and_counts():
    s = summarize([
        _risk(100, mint="a"),
        _risk(25, failed=3, mint="b"),
        _risk(70, warned=3, mint="c"),
    ])
    assert s["scanned"] == 3
    # riskiest (lowest score) first
    assert [r["mint"] for r in s["rows"]] == ["b", "c", "a"]
    assert s["by_tag"]["CAUTION"] == 1
    assert s["by_tag"]["WATCH"] == 1
    assert s["by_tag"]["CLEAN"] == 1


def test_render_table_contains_counts_and_tags():
    out = render_table(summarize([_risk(25, failed=2, mint="abc")]))
    assert "abc" in out
    assert "FAIL" in out
    assert "Scanned 1 mint(s)" in out
    assert "CAUTION=1" in out


if __name__ == "__main__":
    for fn in (test_risk_tag_classification, test_summarize_sorts_riskiest_first_and_counts,
               test_render_table_contains_counts_and_tags):
        fn()
        print(f"ok {fn.__name__}")
    print("3 passed")

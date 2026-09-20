"""Unit tests for the risk model. Live RPC is flaky/throttled, so these
exercise the scoring & verdict logic with deterministic in-memory fixtures.
"""
import sys
import unittest
from unittest import mock

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from solguard import risk  # noqa: E402


def fake_chain(chain_mod, mint_auth_live=False, freeze_auth_live=False,
               supply_ui=1_000_000, holders=None):
    """Patch solguard.risk's chain lookups with a controllable fixture."""

    def _mint_info(mint, url=None):
        return {
            "mint": mint, "decimals": 6, "supply_raw": int(supply_ui * 1e6),
            "is_initialized": True,
            "mint_authority_live": mint_auth_live,
            "freeze_authority_live": freeze_auth_live,
            "mint_authority": "AAAA" if mint_auth_live else None,
            "freeze_authority": "BBBB" if freeze_auth_live else None,
        }

    def _token_supply(mint, url=None):
        return {"amount": str(int(supply_ui * 1e6)), "decimals": 6, "ui_amount": supply_ui}

    def _top10(mint, limit=10, url=None):
        if holders is None:
            raise risk.RpcError("throttled")
        return [{"address": f"W{i}", "ui_amount": amt, "amount": int(amt * 1e6)}
                for i, amt in enumerate(holders)]

    chain_mod.mint_info = _mint_info
    chain_mod.token_supply = _token_supply
    chain_mod.top_holders = _top10


class TestRiskModel(unittest.TestCase):
    @mock.patch.object(risk, "mint_info")
    @mock.patch.object(risk, "token_supply")
    @mock.patch.object(risk, "top_holders")
    def test_clean_token(self, top10, supply, mint_info):
        mint_info.return_value = {
            "mint": "X", "mint_authority_live": False, "freeze_authority_live": False}
        supply.return_value = {"amount": str(1_000_000 * 10**6), "decimals": 6,
                               "ui_amount": 1_000_000}
        top10.return_value = [{"ui_amount": 100_000}, {"ui_amount": 90_000},
                              {"ui_amount": 80_000}, {"ui_amount": 70_000},
                              {"ui_amount": 60_000}, {"ui_amount": 50_000},
                              {"ui_amount": 40_000}, {"ui_amount": 30_000},
                              {"ui_amount": 20_000}, {"ui_amount": 10_000}]
        r = risk.run_rug_checks("X")
        by_id = {c["id"]: c for c in r["checks"]}
        self.assertIs(by_id["mint_authority"]["pass"], True, "mint auth should pass")
        self.assertIs(by_id["freeze_authority"]["pass"], True)
        self.assertEqual(by_id["holder_concentration"]["pass"], None)  # 55% -> WARN
        self.assertEqual(r["failed"], 0)
        self.assertGreaterEqual(r["score"], 80)

    @mock.patch.object(risk, "mint_info")
    @mock.patch.object(risk, "token_supply")
    @mock.patch.object(risk, "top_holders")
    def test_rug_vectors_flag(self, top10, supply, mint_info):
        mint_info.return_value = {
            "mint": "X", "mint_authority_live": True, "freeze_authority_live": True,
            "mint_authority": "AAAA", "freeze_authority": "BBBB"}
        supply.return_value = {"amount": "1000000", "decimals": 6, "ui_amount": 1.0}
        top10.return_value = [{"ui_amount": 0.9}]  # 90% single holder -> FAIL
        r = risk.run_rug_checks("X")
        by_id = {c["id"]: c for c in r["checks"]}
        self.assertIs(by_id["mint_authority"]["pass"], False)
        self.assertIs(by_id["freeze_authority"]["pass"], False)
        self.assertIs(by_id["holder_concentration"]["pass"], False)
        self.assertEqual(r["failed"], 3)
        self.assertEqual(r["score"], 25)

    @mock.patch.object(risk, "mint_info")
    @mock.patch.object(risk, "token_supply")
    @mock.patch.object(risk, "top_holders")
    def test_unverifiable_holder_is_unknown_not_pass(self, top10, supply, mint_info):
        mint_info.return_value = {
            "mint": "X", "mint_authority_live": False, "freeze_authority_live": False}
        supply.return_value = {"amount": "1000000", "decimals": 6, "ui_amount": 1.0}
        top10.side_effect = risk.RpcError("throttled")
        r = risk.run_rug_checks("X")
        holder = [c for c in r["checks"] if c["id"] == "holder_concentration"][0]
        self.assertTrue(holder.get("unknown"))
        self.assertIs(holder["pass"], None)
        self.assertEqual(r["unknown"], 1)
        self.assertFalse(r["clean"], "an unresolved check must block CLEAN")


if __name__ == "__main__":
    unittest.main()

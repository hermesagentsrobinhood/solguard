"""Tests for on-chain RPC endpoint resolution (SOLGUARD_RPC_URL / --rpc)."""
import os
import unittest

from solguard.chain import PUBLIC_RPC, resolve_rpc


class TestResolveRpc(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("SOLGUARD_RPC_URL", None)

    def test_defaults_to_public(self):
        os.environ.pop("SOLGUARD_RPC_URL", None)
        self.assertEqual(resolve_rpc(), PUBLIC_RPC)

    def test_explicit_arg_wins_over_env(self):
        os.environ["SOLGUARD_RPC_URL"] = "https://env.example.com"
        self.assertEqual(resolve_rpc("https://arg.example.com"), "https://arg.example.com")

    def test_env_var_used_when_no_explicit(self):
        os.environ["SOLGUARD_RPC_URL"] = "https://helius-mainnet.xyz/abc"
        self.assertEqual(resolve_rpc(), "https://helius-mainnet.xyz/abc")

    def test_empty_env_falls_through_to_public(self):
        os.environ["SOLGUARD_RPC_URL"] = ""
        self.assertEqual(resolve_rpc(), PUBLIC_RPC)


if __name__ == "__main__":
    unittest.main()

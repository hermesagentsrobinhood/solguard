"""Unit tests for Token-2022 extension-trap detection.

The decoder is exercised with synthetic Token-2022 mint account buffers built
exactly per the on-chain TLV layout (82-byte base + u16 type, u16 len, value).
No live RPC needed -- deterministic, from the spec.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from solguard import token2022  # noqa: E402

BASE = bytes(82)  # Token-2022 mint base is 82 bytes


def ext_bytes(etype: int, body: bytes) -> bytes:
    return etype.to_bytes(2, "little") + len(body).to_bytes(2, "little") + body


def account(*entries: bytes) -> bytes:
    return BASE + b"".join(entries)


def transfer_fee_body(bps: int) -> bytes:
    # TransferFeeConfig: authority(36) + withdraw(36) + withheld u64(8)
    # + older TransferFee(18) + newer TransferFee(18). The newer fee is the
    # LAST 18 bytes: epoch(8) + maximum(8) + basis_points(2), so the fee's
    # basis points sit in the final 2 bytes of the whole 116-byte body.
    head = bytes(36 + 36 + 8 + 18)  # through the end of the older fee
    return head + bytes(16) + bps.to_bytes(2, "little")


class TestDecodeExtensions(unittest.TestCase):
    def assert_checks(self, exts, wanted_ids, unexpected=None):
        checks = token2022.extension_checks(exts)
        ids = {c["id"]: c for c in checks}
        for wid in wanted_ids:
            self.assertIn(wid, ids, f"expected check {wid}")
        if unexpected:
            for u in unexpected:
                self.assertNotIn(u, ids)
        return ids

    def test_no_extensions(self):
        self.assertEqual(token2022.decode_extensions(BASE), [])
        self.assertEqual(token2022.extension_checks([]), [])

    def test_uninitialized_stops_walk(self):
        # garbage after the base followed by zero padding -> stops at type 0
        data = account(ext_bytes(9, bytes(14)), bytes(64))
        exts = token2022.decode_extensions(data)
        self.assertEqual([e["type"] for e in exts], [token2022.NON_TRANSFERABLE])

    def test_non_transferable_flags(self):
        exts = token2022.decode_extensions(account(ext_bytes(9, bytes(14))))
        ids = self.assert_checks(exts, ["token2022_transferable"])
        self.assertIs(ids["token2022_transferable"]["pass"], False)

    def test_permanent_delegate_flags(self):
        # PermanentDelegate body = COption (4+32)
        exts = token2022.decode_extensions(account(ext_bytes(12, bytes(36))))
        ids = self.assert_checks(exts, ["token2022_no_permanent_delegate"])
        self.assertIs(ids["token2022_no_permanent_delegate"]["pass"], False)

    def test_transfer_fee_positive_flags(self):
        exts = token2022.decode_extensions(
            account(ext_bytes(1, transfer_fee_body(125))))
        ids = self.assert_checks(exts, ["token2022_transfer_fee"])
        c = ids["token2022_transfer_fee"]
        self.assertIs(c["pass"], False)
        self.assertIn("1.25%", c["detail"])

    def test_transfer_fee_zero_passes(self):
        exts = token2022.decode_extensions(
            account(ext_bytes(1, transfer_fee_body(0))))
        ids = self.assert_checks(exts, ["token2022_transfer_fee"])
        self.assertIs(ids["token2022_transfer_fee"]["pass"], True)

    def test_transfer_hook_flags(self):
        exts = token2022.decode_extensions(account(ext_bytes(14, bytes(68))))
        ids = self.assert_checks(exts, ["token2022_no_transfer_hook"])
        self.assertIs(ids["token2022_no_transfer_hook"]["pass"], False)

    def test_pausable_paused_flags(self):
        # PausableConfig: authority(36) + paused bool at byte 36
        exts = token2022.decode_extensions(account(ext_bytes(26, bytes(36) + b"\x01")))
        ids = self.assert_checks(exts, ["token2022_not_pausable"])
        self.assertIs(ids["token2022_not_pausable"]["pass"], False)
        self.assertIn("PAUSED", ids["token2022_not_pausable"]["detail"])

    def test_pausable_unpaused_passes(self):
        exts = token2022.decode_extensions(account(ext_bytes(26, bytes(36) + b"\x00")))
        ids = self.assert_checks(exts, ["token2022_not_pausable"])
        self.assertIs(ids["token2022_not_pausable"]["pass"], True)

    def test_default_account_state_frozen_flags(self):
        # state byte then freeze authority COption
        exts = token2022.decode_extensions(account(ext_bytes(6, bytes([2]) + bytes(36))))
        ids = self.assert_checks(exts, ["token2022_default_account_state"])
        self.assertIs(ids["token2022_default_account_state"]["pass"], False)

    def test_mint_close_authority_flags(self):
        exts = token2022.decode_extensions(account(ext_bytes(3, bytes(36))))
        ids = self.assert_checks(exts, ["token2022_no_mint_close"])
        self.assertIs(ids["token2022_no_mint_close"]["pass"], False)

    def test_multiple_extensions_all_reported(self):
        body = (ext_bytes(12, bytes(36))          # permanent delegate
                + ext_bytes(1, transfer_fee_body(250))
                + ext_bytes(9, bytes(14)))        # non-transferable
        exts = token2022.decode_extensions(account(body))
        ids = self.assert_checks(
            exts,
            ["token2022_no_permanent_delegate", "token2022_transfer_fee",
             "token2022_transferable"])
        self.assertIs(ids["token2022_no_permanent_delegate"]["pass"], False)

    def test_truncated_extension_raises(self):
        data = BASE + ext_bytes(1, bytes(50)) + bytes(4)  # incomplete TLV
        with self.assertRaises(token2022.ExtensionDecodeError):
            # extend length so walk attempts to consume the short body
            token2022.decode_extensions(BASE + (1).to_bytes(2, "little")
                                        + (116).to_bytes(2, "little") + bytes(50))


if __name__ == "__main__":
    unittest.main()

"""Token-2022 (Token Extensions) trap detection.

Token-2022 lets a deployer attach *extensions* to a mint that can trap a
holder after they buy: transfer fees that tax your exit, a permanent delegate
that can seize any holder's tokens, transfer hooks that route your transfers
through a third-party program, a token that is simply non-transferable, or a
mint that can be paused / closed by an authority.

These are exactly the "what is not yours and not negotiable" facts from the
fleet mission -- whether a position can trap you. The classic SPL checks look
at mint/freeze authority; Token-2022 mint-level extensions are an additional
trap layer that most "token safety" screens miss entirely, so this module
decodes them straight off the raw account bytes.

Extension type values are the Token-2022 `ExtensionType` enum (sequential from
0, verified against solana-program/token-2022 `interface/src/extension/mod.rs`).
A mint account's raw layout is an 82-byte SPL-mint base followed by a TLV
section: u16 type, u16 length, then `length` bytes of value, repeated.
`Uninitialized` (0) marks the end (zero padding).
"""
from __future__ import annotations

# Mint-account base length shared with classic SPL (82 bytes).
MINT_BASE_LEN = 82

# ExtensionType enum values (0 = Uninitialized marks end of TLV section).
UNINITIALIZED = 0
TRANSFER_FEE_CONFIG = 1
MINT_CLOSE_AUTHORITY = 3
DEFAULT_ACCOUNT_STATE = 6
NON_TRANSFERABLE = 9
PERMANENT_DELEGATE = 12
TRANSFER_HOOK = 14
PAUSABLE = 26

# AccountState enum: 0 Uninitialized, 1 Initialized, 2 Frozen.
ACCOUNT_STATE_FROZEN = 2

# PausableConfig: authority (COption=36 bytes) then paused (Bool=1 byte).
PAUSABLE_PAUSED_OFFSET = 36


class ExtensionDecodeError(RuntimeError):
    pass


def decode_extensions(raw: bytes) -> list[dict]:
    """Walk the TLV extension section of a Token-2022 mint account.

    `raw` is the full raw account data (base64-decoded). The base mint occupies
    the first 82 bytes; the TLV section runs from there to the end of data.
    """
    n = len(raw)
    if n < MINT_BASE_LEN + 4:
        return []  # no extension section
    out: list[dict] = []
    off = MINT_BASE_LEN
    while off + 4 <= n:
        etype = int.from_bytes(raw[off:off + 2], "little")
        elen = int.from_bytes(raw[off + 2:off + 4], "little")
        if etype == UNINITIALIZED:
            break  # zero padding / end of TLV
        body = raw[off + 4:off + 4 + elen]
        if len(body) < elen:
            # account data truncated mid-extension
            raise ExtensionDecodeError(
                f"extension type {etype} length {elen} exceeds remaining data")
        out.append({"type": etype, "len": elen, "data": body})
        off += 4 + elen
    return out


def extension_checks(exts: list[dict]) -> list[dict]:
    """Turn decoded extensions into PASS/FAIL/WARN checks.

    Only the extensions that can trap a holder produce checks. We deliberately
    *name the trap* instead of shrugging -- a permanent delegate or a
    non-transferable token is a hard FAIL, independent of any score.
    """
    by_type: dict[int, dict] = {e["type"]: e for e in exts}
    checks: list[dict] = []

    if NON_TRANSFERABLE in by_type:
        checks.append({
            "id": "token2022_transferable",
            "label": "Token is transferable",
            "pass": False,
            "detail": "NON-TRANSFERABLE extension: this token cannot be sold, "
                       "swapped, or transferred. You could be stuck forever.",
        })

    if PERMANENT_DELEGATE in by_type:
        checks.append({
            "id": "token2022_no_permanent_delegate",
            "label": "No permanent delegate",
            "pass": False,
            "detail": "PERMANENT DELEGATE set: the delegate authority can seize "
                       "or burn ANY holder's tokens (backdoor).",
        })

    if TRANSFER_FEE_CONFIG in by_type:
        fee = by_type[TRANSFER_FEE_CONFIG]
        bps = int.from_bytes(fee["data"][-2:], "little") if len(fee["data"]) >= 2 else 0
        if bps > 0:
            checks.append({
                "id": "token2022_transfer_fee",
                "label": "No transfer fee on exit",
                "pass": False,
                "detail": f"TRANSFER FEE active ({bps} bps = {bps / 100:.2f}%): "
                           f"every transfer -- including selling -- is taxed to the "
                           f"deployer, and the fee can be raised after you buy.",
            })
        else:
            checks.append({
                "id": "token2022_transfer_fee",
                "label": "No transfer fee on exit",
                "pass": True,
                "detail": "transfer-fee extension present but fee is 0.00% (0 bps)",
            })

    if TRANSFER_HOOK in by_type:
        checks.append({
            "id": "token2022_no_transfer_hook",
            "label": "No transfer hook",
            "pass": False,
            "detail": "TRANSFER HOOK set: every transfer is routed through an "
                       "external hook program that can censor, redirect, or "
                       "fail your exit.",
        })

    if PAUSABLE in by_type:
        cfg = by_type[PAUSABLE]
        paused = len(cfg["data"]) > PAUSABLE_PAUSED_OFFSET and \
            cfg["data"][PAUSABLE_PAUSED_OFFSET] == 1
        checks.append({
            "id": "token2022_not_pausable",
            "label": "Mint is not pausable",
            "pass": not paused,
            "detail": ("PAUSABLE extension: an authority can pause transfers, "
                       "minting, and burning at any time"
                       + (" (currently PAUSED)" if paused else "")),
        })

    if DEFAULT_ACCOUNT_STATE in by_type:
        cfg = by_type[DEFAULT_ACCOUNT_STATE]
        state = cfg["data"][0] if cfg["data"] else 0
        frozen = state == ACCOUNT_STATE_FROZEN
        checks.append({
            "id": "token2022_default_account_state",
            "label": "New accounts not frozen",
            "pass": not frozen,
            "detail": ("DefaultAccountState set to "
                       + ("FROZEN -> any new account starts frozen and cannot "
                          "receive or trade tokens" if frozen
                          else f"{state} (not frozen)")),
        })

    if MINT_CLOSE_AUTHORITY in by_type:
        checks.append({
            "id": "token2022_no_mint_close",
            "label": "No mint close authority",
            "pass": False,
            "detail": "MINT CLOSE AUTHORITY set: an authority can burn/close "
                       "the mint and destroy all supply.",
        })

    return checks

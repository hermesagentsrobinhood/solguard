"""On-chain data access for Solana token due diligence.

Reads immutable, server-attested facts straight off the chain RPC: mint
authority, freeze authority, decimals, circulating supply, and holder
concentration. These are the checks that actually carry information about
whether a position can trap you -- not venue risk badges.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request

from solders.pubkey import Pubkey

from . import token2022

PUBLIC_RPC = "https://api.mainnet-beta.solana.com"

# Users with a paid RPC key (Helius/QuickNode/...) can set SOLGUARD_RPC_URL to
# unthrottle the holder-concentration query. Resolution order:
#   explicit --rpc arg  >  SOLGUARD_RPC_URL env  >  free public endpoint.
def resolve_rpc(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("SOLGUARD_RPC_URL")
    if env:
        return env
    return PUBLIC_RPC

TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

# Free-tier public RPCs throttle holder/circulation queries. The only reliably
# working public endpoint is api.mainnet-beta.solana.com; retry it with backoff.
FALLBACK_RPCS = [
    "https://api.mainnet-beta.solana.com",
]

MAX_RETRIES = 6


class RpcError(RuntimeError):
    pass


def _rpc(method: str, params: list, url: str = PUBLIC_RPC) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    rpcs = [url] if url != PUBLIC_RPC else FALLBACK_RPCS
    last_err = None
    for attempt in range(MAX_RETRIES):
        endpoint = rpcs[attempt % len(rpcs)]
        req = urllib.request.Request(endpoint, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
            if "error" in data:
                raise RpcError(f"{method}: {data['error']}")
            return data["result"]
        except urllib.error.HTTPError as e:
            last_err = e
            backoff = 1.0 * (2 ** attempt) + 0.5
            if e.code in (429, 403, 500, 502, 503, 504):
                time.sleep(backoff)
                continue
            raise
    raise RpcError(f"{method} failed after {MAX_RETRIES} attempts: {last_err}")


def parse_pubkey(addr: str) -> Pubkey:
    try:
        return Pubkey.from_string(addr)
    except ValueError as e:
        raise ValueError(f"Invalid Solana address: {addr!r}") from e


def _rpc_base64(mint: str, url: str = PUBLIC_RPC) -> bytes:
    """Fetch a mint account's RAW bytes (base64 encoding) for extension parsing."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
                       "params": [mint, {"encoding": "base64"}]}).encode()
    req = urllib.request.Request(PUBLIC_RPC if url == PUBLIC_RPC else url, data=body,
                                 headers={"Content-Type": "application/json"})
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
            if "error" in data:
                raise RpcError(f"getAccountInfo(base64): {data['error']}")
            value = data.get("result", {}).get("value")
            if not value:
                return b""
            enc = value.get("data")
            b64 = enc[0] if isinstance(enc, list) else enc
            return base64.b64decode(b64)
        except urllib.error.HTTPError as e:
            last_err = e
            backoff = 1.0 * (2 ** attempt) + 0.5
            if e.code in (429, 403, 500, 502, 503, 504):
                time.sleep(backoff)
                continue
            raise
    raise RpcError(f"getAccountInfo(base64) failed after {MAX_RETRIES} attempts: {last_err}")


def _decoded_extensions(mint: str, url: str) -> list[dict] | None:
    """Return decoded Token-2022 extensions for a mint, or None if unreadable.

    Only meaningful for Token-2022 mints; non-Token-2022 mints have no
    extension section and caller should pass is_token2022=False.
    """
    try:
        raw = _rpc_base64(mint, url)
        if not raw:
            return []
        return token2022.decode_extensions(raw)
    except (token2022.ExtensionDecodeError, RpcError, urllib.error.URLError):
        return None


def mint_info(mint: str, url: str = PUBLIC_RPC) -> dict:
    """Return parsed mint-account facts: mint/freeze authority, decimals, supply.

    mintAuthority / freezeAuthority are the rug vectors (a live authority can
    inflate supply or freeze your holdings). A None authority is GOOD.
    """
    pk = parse_pubkey(mint)
    try:
        parsed = _rpc("getAccountInfo", [str(pk), {"encoding": "jsonParsed"}], url)
    except RpcError:
        parsed = _rpc("getAccountInfo", [str(pk), {"encoding": "jsonParsed"}], url)
    info = (parsed or {}).get("value")
    if not info:
        raise RpcError(f"Account {mint} has no on-chain state (not a token / unlaunched).")
    owner = info.get("owner")
    if owner == TOKEN_2022_PROGRAM_ID:
        is_token2022 = True
        token_program = "token-2022"
        exts = _decoded_extensions(str(pk), url)
    elif owner == TOKEN_PROGRAM_ID:
        is_token2022 = False
        token_program = "spl"
        exts = []
    else:
        raise RpcError(f"{mint} is not an SPL/Token-2022 token (owner={owner}).")
    parsed_data = info["data"]["parsed"]["info"]
    mint_authority = parsed_data.get("mintAuthority")
    freeze_authority = parsed_data.get("freezeAuthority")
    return {
        "mint": str(pk),
        "decimals": parsed_data.get("decimals"),
        "supply_raw": int(parsed_data.get("supply", "0")),
        "is_initialized": parsed_data.get("isInitialized", False),
        "mint_authority": mint_authority,
        "freeze_authority": freeze_authority,
        "mint_authority_live": mint_authority is not None,
        "freeze_authority_live": freeze_authority is not None,
        "token_program": token_program,
        "is_token2022": is_token2022,
        "token2022_exts": exts,
    }


def token_supply(mint: str, url: str = PUBLIC_RPC) -> dict:
    result = _rpc("getTokenSupply", [mint], url)
    value = result.get("value", {})
    return {
        "amount": int(value.get("amount", 0)),
        "decimals": value.get("decimals"),
        "ui_amount": value.get("uiAmount"),
    }


def top_holders(mint: str, limit: int = 10, url: str = PUBLIC_RPC) -> list[dict]:
    """Top holder token accounts by balance (on-chain, server-attested)."""
    result = _rpc("getTokenLargestAccounts", [mint], url)
    accounts = result.get("value", [])[:limit]
    out = []
    for acc in accounts:
        amt = int(acc["amount"])
        ui = acc.get("uiAmount") if acc.get("uiAmount") is not None else 0.0
        out.append({"address": acc["address"], "ui_amount": float(ui), "amount": amt})
    return out

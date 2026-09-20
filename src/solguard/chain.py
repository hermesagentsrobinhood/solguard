"""On-chain data access for Solana token due diligence.

Reads immutable, server-attested facts straight off the chain RPC: mint
authority, freeze authority, decimals, circulating supply, and holder
concentration. These are the checks that actually carry information about
whether a position can trap you -- not venue risk badges.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from solders.pubkey import Pubkey

PUBLIC_RPC = "https://api.mainnet-beta.solana.com"

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
    if info.get("owner") != "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA":
        raise RpcError(f"{mint} is not an SPL token (owner={info.get('owner')}).")
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

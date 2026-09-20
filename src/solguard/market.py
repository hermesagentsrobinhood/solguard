"""Market data via DexScreener's public API (token/pair search).

Market liquidity is a *property of the pool at the size you intend to take*,
not an absolute. We report the raw numbers and let the risk model interpret
them against a caller-supplied position size.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.parse

BASE = "https://api.dexscreener.com/latest/dex"


def _get(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/120.0 Safari/537.36"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def search_query(query: str) -> dict:
    """Search by symbol/name -> returns token pairs across chains."""
    url = f"{BASE}/search?q={urllib.parse.quote(query)}"
    return _get(url)


def token_by_address(chain_id: str, address: str) -> dict:
    """Call with e.g. chain_id='solana', address=<mint>.

    DexScreener's token endpoint is address-keyed and chain-agnostic; `chain_id`
    is accepted for call-site clarity and used only to filter results.
    """
    url = f"{BASE}/tokens/{address}"
    try:
        data = _get(url)
    except Exception as e:  # noqa: BLE001 - surface as empty result
        return {"pairs": [], "error": str(e)}
    pairs = data.get("pairs") or []
    if chain_id:
        pairs = [p for p in pairs if p.get("chainId") == chain_id]
    data["pairs"] = pairs
    return data


def best_solana_pair(mint: str) -> dict | None:
    """Return the deepest single Solana pool for a mint, or None."""
    data = token_by_address("solana", mint)
    pairs = data.get("pairs") or []
    if not pairs:
        return None
    pairs = [p for p in pairs if p.get("liquidity", {}).get("usd")]
    pairs.sort(key=lambda p: p["liquidity"]["usd"], reverse=True)
    best = pairs[0]
    liq = best.get("liquidity", {}) or {}
    vol = best.get("volume", {}) or {}
    price = best.get("priceUsd")
    return {
        "dex": best.get("dexId"),
        "pair_address": best.get("pairAddress"),
        "quote_token": (best.get("quoteToken") or {}).get("symbol"),
        "price_usd": float(price) if price else None,
        "liquidity_usd": float(liq.get("usd") or 0),
        "volume_24h_usd": float(vol.get("h24") or 0),
        "fdv_usd": float(best["fdv"]) if best.get("fdv") else None,
        "market_cap_usd": float(best["marketCap"]) if best.get("marketCap") else None,
        "txns_24h": {
            "buys": (best.get("txns", {}).get("h24") or {}).get("buys"),
            "sells": (best.get("txns", {}).get("h24") or {}).get("sells"),
        },
        "pool_created_at": best.get("pairCreatedAt"),
    }

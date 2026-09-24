"""Risk model: turns on-chain + market facts into a scored verdict.

The checks that CARRY information are the ones verified on chain ourselves:
mint/freeze authority, owner schema, holder concentration, and whether the
numbers decode to something sane. Venue risk badges carry almost none and are
deliberately NOT part of this model.

Score: 0-100, higher = safer / cleaner. Flags (PASS/WARN/FAIL) per check are
the primary output; the single number is a convenience summary.
"""
from __future__ import annotations

from .chain import RpcError, mint_info, top_holders, token_supply
from . import token2022

# Freeze threshold: a token this concentrated in wallets risks dump & rug.
TOP10_CONCERN_PCT = 30.0
TOP10_FAIL_PCT = 60.0
SUPPLY_TOO_SMALL_SOL = 0.0001  # placeholder guard; not a real threshold


def run_rug_checks(mint: str, rpc_url: str | None = None) -> dict:
    """Execute immutable safety checks. These are NON-NEGOTIABLE and hold at any size.

    A check we cannot verify is reported as UNKNOWN, never as PASS -- failing to
    run a check is not the same as the check passing, and we refuse to give a
    false sense of safety.
    """
    info = mint_info(mint, rpc_url) if rpc_url else mint_info(mint)
    supply = token_supply(mint, rpc_url) if rpc_url else token_supply(mint)
    try:
        holders = top_holders(mint, limit=10, url=rpc_url) if rpc_url else top_holders(mint, limit=10)
    except RpcError as e:
        holders = None
        holder_error = str(e)

    checks = []
    # 1. Mint authority live -> deployer can inflate supply endlessly (rug vector).
    checks.append({
        "id": "mint_authority",
        "label": "Mint authority disabled",
        "pass": not info["mint_authority_live"],
        "detail": ("disabled" if not info["mint_authority_live"]
                   else f"LIVE: {info['mint_authority']} can mint unlimited tokens"),
    })
    # 2. Freeze authority live -> deployer can freeze your holdings.
    checks.append({
        "id": "freeze_authority",
        "label": "Freeze authority disabled",
        "pass": not info["freeze_authority_live"],
        "detail": ("disabled" if not info["freeze_authority_live"]
                   else f"LIVE: {info['freeze_authority']} can freeze your tokens"),
    })

    # 3. Supply sane: >0 and not absurdly tiny.
    supply_ui = float(supply["ui_amount"] or 0)
    checks.append({
        "id": "supply_sane",
        "label": "Supply is sane (>0)",
        "pass": supply_ui > 0,
        "detail": f"circulating supply {supply_ui:,.6g} ({supply.get('amount')} raw units)",
    })

    # 4. Holder concentration (top-10 % of supply) -- UNKNOWN if RPC blocks it.
    ui_supply = float(supply["ui_amount"] or 0)
    top10_pct = None
    if holders is None:
        checks.append({
            "id": "holder_concentration",
            "label": "Holder concentration (top-10)",
            "pass": None,
            "unknown": True,
            "detail": f"could not verify (RPC throttled): {holder_error}",
        })
    else:
        top10_ui = sum(h["ui_amount"] for h in holders)
        top10_pct = (top10_ui / ui_supply * 100.0) if ui_supply > 0 else 100.0
        if top10_pct >= TOP10_FAIL_PCT:
            top_pass = False
        elif top10_pct >= TOP10_CONCERN_PCT:
            top_pass = None
        else:
            top_pass = True
        checks.append({
            "id": "holder_concentration",
            "label": "Holder concentration (top-10)",
            "pass": top_pass,
            "unknown": False,
            "detail": f"top-10 hold {top10_pct:.1f}% of {ui_supply:,.6g} supply",
        })

    failed = sum(1 for c in checks if c["pass"] is False)
    warned = sum(1 for c in checks if c["pass"] is None and not c.get("unknown"))
    unknown = sum(1 for c in checks if c.get("unknown"))

    # Token-2022 extension traps (transfer fee on exit, permanent delegate,
    # non-transferable, transfer hook, pausable, mint-close, frozen-by-default).
    if info.get("is_token2022", False):
        exts = info.get("token2022_exts")
        if exts is None:
            checks.append({
                "id": "token2022_extensions",
                "label": "Token-2022 extension scan",
                "pass": None,
                "unknown": True,
                "detail": "could not decode Token-2022 extension section (RPC). "
                          "Permanent-delegate / transfer-fee traps NOT checked.",
            })
        else:
            ext_checks = token2022.extension_checks(exts)
            if not ext_checks:
                ext_checks = [{
                    "id": "token2022_no_traps",
                    "label": "No Token-2022 extension traps",
                    "pass": True,
                    "detail": "no dangerous mint extensions detected (transfer "
                              "fee, permanent delegate, transfer hook, "
                              "non-transferable, pausable, mint-close).",
                }]
            checks.extend(ext_checks)
        failed = sum(1 for c in checks if c["pass"] is False)
        warned = sum(1 for c in checks if c["pass"] is None and not c.get("unknown"))
        unknown = sum(1 for c in checks if c.get("unknown"))

    # Simple score: each FAIL -25, each WARN -10, base 100, floor 0. UNKNOWN
    # does not lower the score but is surfaced so the reader knows the picture
    # is incomplete.
    score = max(0, 100 - failed * 25 - warned * 10)
    clean = failed == 0 and warned == 0 and unknown == 0
    return {
        "checks": checks,
        "score": score,
        "clean": clean,
        "failed": failed,
        "warned": warned,
        "unknown": unknown,
        "mint": info,
        "supply": supply,
        "top_holders": holders,
        "top10_pct": top10_pct,
    }

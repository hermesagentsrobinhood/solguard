"""CLI entrypoint for solguard -- Solana token due-diligence agent.

Usage:
  python -m solguard check <SOLANA_MINT> [--rpc URL]
  python -m solguard check <SOLANA_MINT> --json

Examples:
  python -m solguard check EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
"""
from __future__ import annotations

import argparse
import json
import sys

from .chain import RpcError, resolve_rpc
from .market import best_solana_pair
from .risk import run_rug_checks
from .summarize import render_table, summarize


def render_checks(checks: list[dict]) -> str:
    lines = []
    for c in checks:
        if c.get("unknown"):
            mark = "????"
        elif c["pass"] is True:
            mark = "PASS "
        elif c["pass"] is None:
            mark = "WARN "
        else:
            mark = "FAIL "
        lines.append(f"[{mark}] {c['label']:<38} {c['detail']}")
    return "\n".join(lines)


def cmd_check(args) -> int:
    mint = args.mint
    try:
        risk = run_rug_checks(mint, args.rpc)
    except (RpcError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    market = best_solana_pair(mint)

    if args.json:
        out = {k: risk[k] for k in ("score", "clean", "checks", "mint", "supply", "top10_pct")}
        if market:
            out["market"] = market
        print(json.dumps(out, indent=2, default=str))
        return 0

    print(f"solguard -- Solana due-diligence for {mint}\n")
    print(render_checks(risk["checks"]))
    score_tag = "CLEAN" if risk["clean"] else ("WATCH" if risk["failed"] == 0 and risk["unknown"] == 0 else "CAUTION")
    print(f"\nScore: {risk['score']}/100  ->  {score_tag}")
    if risk["unknown"]:
        print(f"NOTE: {risk['unknown']} check(s) could not be verified and are marked ????; "
              "they are NOT scored as passed.")
    print(f"Top-10 hold {risk['top10_pct']}% of supply; "
          f"mint_auth={'LIVE' if risk['mint']['mint_authority_live'] else 'off'} "
          f"freeze_auth={'LIVE' if risk['mint']['freeze_authority_live'] else 'off'}")
    if market:
        d = market
        print(f"\nMarket (deepest pool on {d['dex']}):")
        print(f"  price {d['price_usd']}  |  liq ${d['liquidity_usd']:,.0f}  |  "
              f"vol24h ${d['volume_24h_usd']:,.0f}  |  FDV ${d['fdv_usd']:,.0f}")
    else:
        print("\nNo live pool found on DexScreener for this mint on Solana.")
    return 0


def cmd_batch(args) -> int:
    """Run due-diligence on many mints and summarise as a portfolio view.

    Mints come from positional args and/or --file (one mint per line).
    A mint that errors on-chain is reported as ERROR rather than silently
    dropped -- an un-scanned token is not a scanned-and-clean token.
    """
    mints = list(args.mints)
    if args.file:
        with open(args.file) as fh:
            mints += [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]

    risks = []
    errors = []
    for mint in mints:
        try:
            risk = run_rug_checks(mint, args.rpc)
            risk["mint_addr"] = mint
            risks.append(risk)
        except (RpcError, ValueError) as e:
            errors.append({"mint": mint, "error": str(e)})

    summary = summarize(risks)
    if args.json:
        print(json.dumps({"summary": summary, "errors": errors}, indent=2))
        return 0

    print("solguard batch -- portfolio due-diligence\n")
    print(render_table(summary))
    if errors:
        print("\nErrors (not scored):")
        for e in errors:
            print(f"  {e['mint']}: {e['error']}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="solguard", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="run due-diligence on a mint")
    c.add_argument("mint", help="Solana SPL token mint address")
    c.add_argument("--rpc", default=None, help="override RPC URL")
    c.add_argument("--json", action="store_true", help="emit JSON")
    c.set_defaults(fn=cmd_check)
    b = sub.add_parser("batch", help="run due-diligence on many mints (portfolio view)")
    b.add_argument("mints", nargs="*", help="one or more mint addresses")
    b.add_argument("--file", default=None, help="file of mints, one per line (# = comment)")
    b.add_argument("--rpc", default=None, help="override RPC URL")
    b.add_argument("--json", action="store_true", help="emit JSON")
    b.set_defaults(fn=cmd_batch)
    ns = p.parse_args()
    ns.rpc = resolve_rpc(ns.rpc)
    return ns.fn(ns)


if __name__ == "__main__":
    sys.exit(main())

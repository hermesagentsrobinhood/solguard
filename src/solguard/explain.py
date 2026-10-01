"""Plain-language verdict narrative for a solguard due-diligence result.

The CLI and HTML report give a judge the raw facts (PASS/WARN/FAIL/???? per
check plus a score). ``explain`` translates the same risk record into a short,
non-technical paragraph that states the bottom line up front and then gives the
*why* behind each meaningful finding -- so a reader who does not parse on-chain
authority flags can still tell whether the project is telling them the truth.

Pure functions, no I/O. Deterministic given a risk record, so unit-testable
with the same discipline as the rest of the model.
"""

from __future__ import annotations


def _verdict(c: dict) -> str:
    """Single-letter verdict used inside the narrative."""
    if c.get("unknown"):
        return "unverifiable"
    if c["pass"] is True:
        return "clean"
    if c["pass"] is None:
        return "a warning"
    return "a fail"


# Per-check, what a FAIL here actually means in plain English.
_WHY = {
    "mint_authority": (
        "the deployer still holds mint authority, so they can print an "
        "unlimited number of tokens at will -- the classic rug vector"
    ),
    "freeze_authority": (
        "the deployer can freeze any holder's tokens, so your own holdings "
        "can be locked at their discretion"
    ),
    "supply_sane": (
        "the reported token supply does not decode to a sane positive number"
    ),
    "holder_concentration": (
        "a very small group holds a dominant share of the supply, so the "
        "price is vulnerable to a coordinated dump"
    ),
    # Token-2022 traps just map to their own labels.
    "token2022_no_traps": (
        "no dangerous Token-2022 mint extensions were found"
    ),
}

_RISK_NOTE = (
    "Nothing here is a buy/sell recommendation -- it is only whether the "
    "on-chain facts could trap you. A clean verdict does not mean the token "
    "will go up; it means the deployer cannot print, freeze, seize, or block "
    "your exit."
)


def explain(risk: dict, market: dict | None = None) -> str:
    """Return a short plain-language narrative for a risk record."""
    score = risk["score"]
    tag = _tag(risk)
    fails = [c for c in risk["checks"] if c.get("pass") is False]
    warns = [c for c in risk["checks"] if c.get("pass") is None and not c.get("unknown")]
    unk = risk.get("unknown", 0)

    parts = []
    parts.append(f"{tag}: This mint scores {score}/100 on the immutable "
                 f"trappability checks the tool actually verifies on chain.")

    if fails:
        reasons = []
        for c in fails:
            why = _WHY.get(c["id"], c["label"])
            reasons.append(f"{c['label'].lower()} ({why})")
        parts.append("It FAILS " + "; ".join(reasons) + ".")
    if warns:
        parts.append(f"There {_plural(warns, 'is a warning', 'are warnings')} on: "
                     + ", ".join(c["label"].lower() for c in warns) + ".")
    if unk:
        parts.append(f"{unk} check(s) could NOT be verified and are not scored "
                     f"as passed -- the picture is incomplete, not proven safe.")

    if market:
        d = market
        parts.append(f"Market depth: ~${d['liquidity_usd']:,.0f} liquidity and "
                     f"${d['volume_24h_usd']:,.0f} 24h volume on {d['dex']}, "
                     f"price ${d['price_usd']}.")
    else:
        parts.append("No live Solana pool was found on DexScreener for this mint.")

    parts.append(_RISK_NOTE)
    return " ".join(parts)


def _tag(risk: dict) -> str:
    if risk["clean"]:
        return "CLEAN"
    if risk.get("failed", 0) > 0:
        return "CAUTION"
    if risk.get("unknown", 0) > 0:
        return "INCOMPLETE"
    return "WATCH"


def _plural(items: list, one: str, many: str) -> str:
    return many if len(items) != 1 else one

"""Portfolio-level summarisation for solguard batch mode.

Pure functions, no I/O, so they are trivially unit-testable with deterministic
mocks -- exactly the same discipline as the rest of the risk model.
"""
from __future__ import annotations


def risk_tag(risk: dict) -> str:
    """Human tag for a single risk record."""
    if risk["clean"]:
        return "CLEAN"
    if risk["failed"] == 0 and risk["unknown"] == 0:
        return "WATCH"
    if risk["failed"] > 0:
        return "CAUTION"
    return "INCOMPLETE"


def summarize(risks: list[dict]) -> dict:
    """Aggregate a list of risk records into a portfolio summary.

    Each row is (mint, score, tag, fails, warns, unknown). Returns both a
    JSON-safe structure and pre-sorted metadata. Highest risk (lowest score)
    sorts first so the eye lands on the worst offenders.
    """
    rows = []
    for r in risks:
        rows.append({
            "mint": r.get("mint_addr", r.get("mint", {}).get("address", "?")),
            "score": r["score"],
            "tag": risk_tag(r),
            "failed": r["failed"],
            "warned": r["warned"],
            "unknown": r["unknown"],
        })
    rows.sort(key=lambda x: (x["score"], -x["failed"]))
    total = len(rows)
    by_tag = {}
    for r in rows:
        by_tag[r["tag"]] = by_tag.get(r["tag"], 0) + 1
    return {
        "scanned": total,
        "by_tag": by_tag,
        "rows": rows,
    }


def render_table(summary: dict) -> str:
    """Render a summary to a fixed-width text table."""
    header = f"{'MINT':<46} {'SCORE':>5} {'TAG':<10} {'FAIL':>4} {'WARN':>4} {'??':>3}"
    sep = "-" * len(header)
    lines = [header, sep]
    for r in summary["rows"]:
        lines.append(
            f"{r['mint']:<46} {r['score']:>5} {r['tag']:<10} "
            f"{r['failed']:>4} {r['warned']:>4} {r['unknown']:>3}"
        )
    lines.append(sep)
    scans = summary["scanned"]
    tags = ", ".join(f"{k}={v}" for k, v in sorted(summary["by_tag"].items()))
    lines.append(f"Scanned {scans} mint(s): {tags}")
    return "\n".join(lines)

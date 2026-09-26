"""Self-contained HTML report for a solguard due-diligence result.

Generates a single-file, no-network HTML report with per-check rationale so a
judge (or a human) can read *why* each check passed / warned / failed at a
glance -- and where the picture is incomplete (?). Pure function: takes a risk
record and returns a string, so it is trivially unit-testable.

An UNKNOWN check is rendered as `?` and is explicitly described as NOT scored
as passed -- solguard never sells a false picture of safety to a reader any
more than it does to the CLI.
"""

from __future__ import annotations


def _row(pass_: bool | None, unknown: bool) -> tuple[str, str]:
    """Return (css class, badge) for a check's verdict."""
    if unknown:
        return "verdict-unknown", "?"
    if pass_ is True:
        return "verdict-pass", "PASS"
    if pass_ is None:
        return "verdict-warn", "WARN"
    return "verdict-fail", "FAIL"


def check_verdict(c: dict) -> str:
    """Plain-text verdict for a single check (used in titles/summaries)."""
    if c.get("unknown"):
        return "UNKNOWN"
    if c["pass"] is True:
        return "PASS"
    if c["pass"] is None:
        return "WARN"
    return "FAIL"


def render_html(risk: dict, market: dict | None = None, mint_addr: str = "") -> str:
    """Build the full HTML document for one risk record.

    `risk` is the dict returned by ``run_rug_checks``; `market` is the dict
    from ``best_solana_pair`` (or None). Pure -- no filesystem access.
    """
    mint = risk.get("mint", {})
    addr = mint_addr or mint.get("address") or "?"
    score = risk["score"]

    if risk["clean"]:
        tag = "CLEAN"
    elif risk["failed"] > 0:
        tag = "CAUTION"
    elif risk["unknown"] > 0:
        tag = "INCOMPLETE"
    else:
        tag = "WATCH"

    tag_cls = {"CLEAN": "tag-clean", "CAUTION": "tag-caution",
               "WATCH": "tag-watch", "INCOMPLETE": "tag-incomplete"}.get(tag, "tag-watch")

    rows = []
    for c in risk["checks"]:
        cls, badge = _row(c.get("pass"), c.get("unknown"))
        rows.append(f"""
      <div class="check {cls}">
        <span class="badge">{badge}</span>
        <div class="check-body">
          <div class="check-label">{c['label']}</div>
          <div class="check-detail">{c.get('detail', '')}</div>
          <div class="check-why">{rationale(c['id'])}</div>
        </div>
      </div>""")

    market_html = ""
    if market:
        m = market
        liq = m["liquidity_usd"]
        vol = m["volume_24h_usd"]
        fdv = m.get("fdv_usd")
        mc = m.get("market_cap_usd")
        price = m.get("price_usd")
        dex = m.get("dex")
        market_html = f"""
      <section>
        <h2>Market depth (deepest pool)</h2>
        <p class="market-note">Liquidity and volume are properties of the pool at
        the size <em>you</em> intend to take, not an absolute good or bad. All
        figures from {dex} via DexScreener.</p>
        <table class="kv">
          <tr><td>DEX / pair</td><td>{dex or 'n/a'}</td></tr>
          <tr><td>Price (USD)</td><td>{f"${price:.8g}" if price is not None else "n/a"}</td></tr>
          <tr><td>Liquidity</td><td>${liq:,.0f}</td></tr>
          <tr><td>24h volume</td><td>${vol:,.0f}</td></tr>
          <tr><td>Market cap</td><td>{f"${mc:,.0f}" if mc is not None else "n/a"}</td></tr>
          <tr><td>Fully-diluted valuation</td><td>{f"${fdv:,.0f}" if fdv is not None else "n/a"}</td></tr>
        </table>
      </section>"""

    unknown_note = ""
    if risk["unknown"]:
        unknown_note = (f'<div class="unknown-note">⚠ {risk["unknown"]} check(s) '
                        'could not be verified and are marked <b>?</b> — they are '
                        '<b>NOT scored as passed</b>. The picture is incomplete.</div>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>solguard due-diligence — {addr}</title>
<style>
  :root {{ --ink:#d7dbe2; --muted:#9aa3b2; --bg:#0f1115; --card:#171a21;
           --pass:#2ecc71; --warn:#f1c40f; --fail:#e74c3c; --unknown:#6b7280; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:820px; margin:0 auto; padding:40px 22px 80px; }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  .addr {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--muted);
          font-size:13px; word-break:break-all; }}
  .score-row {{ display:flex; align-items:center; gap:18px; margin:22px 0 6px; }}
  .score-big {{ font-size:40px; font-weight:700; }}
  .tag {{ padding:5px 14px; border-radius:20px; font-weight:700; font-size:14px; }}
  .tag-clean {{ background:#16291e; color:var(--pass); }}
  .tag-caution {{ background:#3a1c1c; color:var(--fail); }}
  .tag-watch {{ background:#332b10; color:var(--warn); }}
  .tag-incomplete {{ background:#1c2028; color:var(--unknown); }}
  section {{ background:var(--card); border-radius:14px; padding:20px 22px; margin-top:18px;
            border:1px solid #232733; }}
  h2 {{ font-size:16px; margin:0 0 14px; }}
  .check {{ display:flex; gap:14px; padding:12px 0; border-bottom:1px solid #1f242e; }}
  .check:last-child {{ border-bottom:0; }}
  .badge {{ min-width:64px; height:30px; display:flex; align-items:center; justify-content:center;
           border-radius:8px; font-weight:700; font-size:13px; }}
  .verdict-pass .badge {{ background:#16291e; color:var(--pass); }}
  .verdict-fail .badge {{ background:#3a1c1c; color:var(--fail); }}
  .verdict-warn .badge {{ background:#332b10; color:var(--warn); }}
  .verdict-unknown .badge {{ background:#1c2028; color:var(--unknown); }}
  .check-label {{ font-weight:600; }}
  .check-detail {{ color:var(--muted); margin-top:2px; font-size:13.5px;
                  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
  .check-why {{ color:#b9c0cc; margin-top:6px; font-size:13px; }}
  .check-why::before {{ content:"why: "; color:var(--muted); font-style:italic; }}
  .unknown-note {{ background:#332b10; /* reused warn tint */ border-radius:10px;
                  padding:12px 16px; margin-top:16px; color:#f0e6c0; }}
  .market-note {{ color:var(--muted); font-size:13px; margin:0 0 12px; }}
  table.kv {{ width:100%; border-collapse:collapse; font-size:14px; }}
  table.kv td {{ padding:7px 4px; border-bottom:1px solid #1f242e; }}
  table.kv td:first-child {{ color:var(--muted); width:42%; }}
  footer {{ margin-top:26px; color:#555d6b; font-size:12px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>solguard — Token due-diligence report</h1>
  <div class="addr">{addr}</div>
  <div class="score-row">
    <div class="score-big">{score}<span style="font-size:18px;color:var(--muted)">/100</span></div>
    <div class="tag {tag_cls}">{tag}</div>
  </div>
  {unknown_note}
  <section>
    <h2>Immutable on-chain checks</h2>
    {''.join(rows)}
  </section>
  {market_html}
  <footer>Generated by solguard · free public RPC · no paid API keys ·
  verified on-chain facts only — checks that could not be verified are marked ?</footer>
</div>
</body>
</html>"""


RATIONALE = {
    "mint_authority": (
        "A live mint authority lets the deployer mint unlimited new tokens at "
        "will, inflating supply against every existing holder. Most rugs are "
        "this vector. Revoked = good."),
    "freeze_authority": (
        "A live freeze authority can freeze YOUR holdings, making them "
        "untradeable at the deployer's discretion. Revoked = good."),
    "supply_sane": (
        "Supply must decode to something sane (> 0 and not absurdly tiny). A "
        "bizarre or zero supply suggests a malformed or manipulated contract."),
    "holder_concentration": (
        "How much of the total supply sits in a few wallets. Above 60% in the "
        "top 10 risks a coordinated dump; above 30% is a concern."),
    "token2022_extensions": (
        "Token-2022 lets a deployer attach extensions that can trap you after "
        "you buy: permanent delegate (seize/burn), transfer fee on your exit, "
        "transfer hook (censor), non-transferable (stuck forever), pausable, "
        "mint-close, or frozen-default accounts."),
    "token2022_no_traps": (
        "No dangerous Token-2022 mint extensions detected in the decoded "
        "on-chain extension section."),
}


def rationale(check_id: str) -> str:
    """Human-readable *why* for a check id. Unknown ids degrade gracefully."""
    return RATIONALE.get(check_id, "See on-chain detail above for the evidence.")


def rationale_for_all_ids() -> dict:
    """Expose the rationale map (useful for tests / future i18n)."""
    return dict(RATIONALE)

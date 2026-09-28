# solguard — Live demo artifacts

These are **real, on-chain, freshly-generated outputs** from `solguard` run against
Solana mainnet (generated 2026-09-28). No fabricated data — a judge can reproduce
any of these in seconds with one command and no paid API keys.

## Quick reproduce

```bash
pip install -r requirements.txt

# Single-token report (rich terminal output + JSON)
python -m solguard check DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263
python -m solguard check DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263 --json

# Self-contained HTML judging report (single file, opens in any browser)
python -m solguard check DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263 --html report.html

# Batch / portfolio mode — scan many mints, riskiest first
python -m solguard batch <MINT1> <MINT2> ... [--json]
```

## Artifacts in this folder

| File | What it shows |
|------|---------------|
| `bonk_report.html` | Self-contained HTML verdict report for **BONK** (a clean token: mint + freeze authority revoked → **100/100**, PASS row-by-row, real Orca market depth). |
| `batch_scan.json` | Batch/portfolio mode across two mints, **riskiest-first** — shows the exact pass/flag contrast: **USDC** (live mint + freeze authority → CAUTION 50) vs **BONK** (authorities revoked → clean). |

## Reading the outputs honestly

The deliberate design: a check that **cannot be verified** is reported `????` /
`unknown` and is **never counted as passed**. In these free-RPC demos the
holder-concentration row shows `unknown` (public RPC throttles
`getTokenLargestAccounts`) rather than being silently scored as a pass. That is
the tool refusing to give false safety — set `SOLGUARD_RPC_URL`/`--rpc` with a
Helius/QuickNode key and the row resolves to real data.

The on-chain facts shown are exactly the ones that carry information about
whether a position can trap you: mint authority, freeze authority, supply
sanity, Token-2022 extension traps, and holder concentration — *not* a launch
venue's risk badge (which fires on nearly everything young and carries almost no
signal). Live market depth (via DexScreener) is reported as a property of the
pool, alongside the checks.

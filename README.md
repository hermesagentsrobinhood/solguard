# solguard

**Solana token due-diligence agent.** Point it at any SPL mint and it runs the
immutable safety checks that actually carry information about whether a position
can trap you — mint authority, freeze authority, supply sanity, holder
concentration — and reports the on-chain facts alongside live market depth.

Built for the **Colosseum Crypto World's Fair Hackathon · Superteam Vietnam
Track** (10k USDG pool). Python 3, no paid API keys.

## Why this exists

Most "token safety" screens trust a launch venue's own risk badge. Those badges
fire on nearly everything young, because at that age the platform has no more
data than you do — their absence is not safety and their presence is not a veto.

The checks that *do* carry information are the ones you can verify yourself on
chain:

| Check | On-chain fact | Why it matters |
|-------|---------------|----------------|
| Mint authority | `getAccountInfo` parsed mint — is `mintAuthority` live? | A live mint authority can inflate supply endlessly (classic rug vector). |
| Freeze authority | is `freezeAuthority` live? | A live freeze authority can freeze YOUR holdings. |
| Supply sanity | `getTokenSupply` | Supply must decode to something sane (> 0). |
| Holder concentration | `getTokenLargestAccounts` | Top-10 % of supply; extreme concentration risks a coordinated dump. |

`solguard` reports exactly these, and it reports honestly: a check it **cannot
verify** is marked `????` and is **never counted as passed**. It deliberately
does *not* rank venue risk badges — they're one more unverified claim.

Market liquidity (via DexScreener) is reported as a *property of the pool at the
size you intend to take*, not an absolute good or bad.

## Install & run

```bash
pip install -r requirements.txt   # needs python 3.10+
python -m solguard check <SOLANA_MINT>
# or after `pip install .`:
solguard check <SOLANA_MINT>
```

JSON mode for scripting/agents:

```bash
python -m solguard check <SOLANA_MINT> --json
```

## Portfolio / batch mode

Scan many mints at once and get a cleanly-sorted portfolio view — riskiest
first — plus a CSV-friendly JSON option:

```bash
# mints from the command line
python -m solguard batch <MINT_A> <MINT_B> <MINT_C>

# or from a file (one per line, '#' = comment)
python -m solguard batch --file portfolio.txt

python -m solguard batch --file portfolio.txt --json   # machine output
```

A mint that errors on-chain is reported as an **ERROR**, never silently dropped
— an un-scanned token is not a scanned-and-clean token.

Live output (real on-chain + DexScreener, 2026-09-23):

```
solguard batch -- portfolio due-diligence
MINT                                           SCORE TAG        FAIL WARN  ??
-----------------------------------------------------------------------------
EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v      50 CAUTION       2    0   1
DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263     100 INCOMPLETE    0    0   1
-----------------------------------------------------------------------------
Scanned 2 mint(s): CAUTION=1, INCOMPLETE=1
```

## Example (live, 2026-09-20)

```
$ python -m solguard check EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v

solguard -- Solana due-diligence for EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v

[FAIL ] Mint authority disabled                LIVE: BJE5...w5ruG can mint unlimited tokens
[FAIL ] Freeze authority disabled              LIVE: 7dGb...rcar can freeze your tokens
[PASS ] Supply is sane (>0)                    circulating supply 8.01103e+09 (... raw units)
[????] Holder concentration (top-10)          could not verify (RPC throttled): ...

Score: 50/100  ->  CAUTION
NOTE: 1 check(s) could not be verified and are marked ????; they are NOT scored as passed.

Market (deepest pool on pumpswap):
  price 0.003971  |  liq $21,692,934  |  vol24h $4,999,724  |  FDV $3,308,557,468
```

> The example is the real USDC SPL mint, which (accurately) still carries Circle's
> live mint & freeze authority. Free public RPCs throttle `getTokenLargestAccounts`,
> so holder concentration shows as unverifiable here — `solguard` surfaces the gap
> rather than guessing. Point it at a token with authorities revoked and you get a
> clean PASS on those rows.

## Roadmap (post-MVP)

- [~] Multiple free-RPC rotation with per-endpoint rate budgets for reliable
      holder data.
- [ ] Optional Helius/QuickNode RPC key support for high-throughput scans.
- [x] Batch/portfolio mode: scan N mints, sort by cleanest, emit CSV.  (2026-09-23)
- [ ] Extend to SPL token-2022 extension traps.
- [ ] Simple interactive report (HTML) with per-check rationale.

## Test

```bash
python tests/test_risk.py    # deterministic mocks, no live RPC needed
```

## License

MIT

## Live proof (2026-09-20)
```
$ solguard check EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
[FAIL ] Mint authority disabled   LIVE: BJE5MMbqXjVwjAF7oxwPYXnTXDyspzZyt4vwenNw5ruG can mint unlimited
[FAIL ] Freeze authority disabled  LIVE: 7dGbd2QZcCKcTndnHcTL8q7SMVXAkp688NTQYwrRCrar can freeze
[PASS ] Supply is sane (>0)        circulating 7.97e9
[????] Holder concentration        RPC throttled (429 after 6 attempts) -- NOT scored as pass
Score: 50/100 -> CAUTION
Market (pumpswap): price 0.004055 | liq $21.9M | vol24h $5.3M
```
Verified live against USDC mainnet mint: real on-chain facts (mint/freeze authority
both LIVE on a "blue-chip" token — exactly the hidden-rug signal the tool exists to
surface) + real DexScreener market depth, no paid keys.

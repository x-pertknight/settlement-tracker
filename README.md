# Settlement tracker: first release

How prediction markets actually settle, measured from public data on Polymarket and Kalshi.
Cutoff 2026-11-17 00:00 UTC. Refreshable: every number comes from the scripts in `scripts/`, except the two money-waiting snapshots, which are point-in-time API reads.

## Findings

1. **Disputes are rare, but when they happen the first answer often does not stand.** On Polymarket's UMA paths, 0.07% of 1.43M questions proposed between 11 Oct and 17 Nov 2026 were disputed (on-chain, numerator and denominator in the same window). Of the 930 disputed markets that had settled by the cutoff, 24% ended with a different outcome from the first proposal (28.6% on the main direct path); 107 were still open and are not counted.
2. **Disputed markets usually settle within hours.** The adapter re-asks immediately after a dispute, so the market settles in a median 1.4 h on the main path (p90 17 h). The disputed request itself goes to the UMA vote and settles days later, with no further effect on the market.
3. **UMA is not always the final word, on paper.** On every mapped Polymarket path, verified contract code gives an admin role the power to flag, pause, reset or manually resolve a question, and on neg-risk markets a second contract can set the outcome after a flag. This is a capability in the code, not an observed event: how often it is used and who holds the role are not measured in this release. A forward logger records every such event from 18 Nov 2026.
4. **Crypto and sports settle fastest, economics, entertainment and politics slowest.** Kalshi settles crypto and sports in minutes after close, economics in ~9 h and entertainment in ~18 h (25 markets per category). On Polymarket, scheduled markets settle a median 4 h after their end date, politics a median 24 h (31 markets). The pattern is the same on both venues; this release does not test why.
5. **Money waiting is mostly normal pipeline.** At the snapshot, about $5.8M had waited more than 3 days for settlement across both venues, and $5.0M of it was one Polymarket election-results market whose end date is election day. The rest of the ~$11M in ended-but-unpaid markets was within hours of closing or on early proposals.
6. **A public field undercounts disputes by ~96%.** Polymarket's data-api `was_disputed` flags 29 of 691 direct-path questions disputed on-chain. Dispute statistics here come from on-chain events only.

Full tables: [RESULTS.md](RESULTS.md). Preregistered predictions and how they scored: [docs/PREDICTIONS.md](docs/PREDICTIONS.md) and the last section of RESULTS.md (six clear misses).

## Windows (they differ by measure, and every table says which)

| Measure | Window |
|---|---|
| Polymarket population, path mix, settlement lag | markets closed 17 Nov 2025 to 17 Nov 2026 |
| Polymarket disputes and outcome changes | 11 Oct to 17 Nov 2026, on-chain (free RPC history limit) |
| Kalshi lag, prices, snapshot | markets closed 18 Sep to 17 Nov 2026 (the historical API cannot be sampled by close time) |
| Money waiting | snapshots on 18 Nov 2026, about 06:00 UTC |

## Method in short

- **Polymarket population:** 70,000 random Gamma market IDs (seed fixed in the script), equal inclusion probability per market; 53,801 closed in the window (about 5.48M estimated in total; market creation grew from ~73k a month in Dec 2025 to ~1.3M in Oct 2026). Cross-check: the sample implies ~1.42M UMA markets closing 11 Oct to 17 Nov, the on-chain census counts 1.43M questions. A stratified subsample of 3,105 (category x market type) with expansion weights for lag and classification.
- **Settlement time:** data-api `last_update_timestamp`, validated against the on-chain `ConditionResolution` block on 150 recent resolutions (all within 47 s on both main paths). On the legacy neg-risk route it is not the settlement time, so those markets are excluded from every lag figure.
- **Paths:** `resolvedBy` mapped to contracts using Polymarket docs, GitHub releases and verified source on Sourcify; levels (documented or inferred) stated per path.
- **Disputes:** every ProposePrice, DisputePrice and Settle event on the two UMA oracles for the Polymarket adapters, grouped by question and request round. The market outcome is the settlement of the latest round; the vote on a disputed request is reported separately.
- **Kalshi:** all settled non-combo markets closing in 300 random 60-second windows (19,373 markets: Kalshi closes whole strike ladders in the same minute, so confidence intervals resample minutes); trades for a category-balanced subsample of 25 per category.
- **Classes:** scheduled vs by-date from question text, tags and series only (no timing or outcome fields), in `scripts/classify.py`.

## Limits

- Windows differ by measure; Polymarket and Kalshi lags start from different points (end date vs close). Compare shapes, not levels.
- Polymarket lag excludes markets whose end date is later than their close (376 of 1,713 scheduled markets, mostly sports). The median (4 h) is stable across windows; the p90 is 10.3 h over the year and ~6 h in recent months, and timestamps before 9 Oct 2026 could not be checked on-chain.
- Kalshi p90 lag is fragile (64 min, 95% CI 30 min to 9.5 h) because a few minutes hold most of the sample.
- The upset rate is secondary: prices often already reflect the outcome before the reference point.
- One unverified UMA requester (74k proposals, 90 disputes in the window) is excluded; if it belongs to Polymarket the dispute denominator would rise about 5%.
- Kalshi challenge history is not public, so Kalshi has no dispute statistics.
- Admin override frequency and holders are not measured in this release.

## Files

- `data/settlement_tracker_v1_markets.csv.gz`: one row per sampled market, both venues; schema in `docs/SCHEMA.md`.
- `charts/`: the four figures.
- `docs/ADMIN_POWERS.md`: admin functions and preconditions, quoted from verified source.
- `scripts/`: collection, validation, classification, the final dispute table, the checks added after review (09 to 12), the charts (13, needs `matplotlib`) and the forward logger (Python standard library otherwise, plus `pycryptodome` for keccak in the on-chain scripts).
- `data/disputes_final.json`: one row per disputed question (path, question ID, first and final answer, how it ended, category); no wallet data.

No wallet-level data is published. Public endpoints only: Polymarket Gamma, data-api and CLOB; Kalshi trade API; a public Polygon RPC.

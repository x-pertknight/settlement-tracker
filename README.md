# Settlement tracker: first release

How prediction markets actually settle, measured from public data on Polymarket and Kalshi.
Cutoff 2026-11-17 00:00 UTC. Refreshable: the numbers come from the scripts in `scripts/`, with two exceptions: the money-waiting snapshots are point-in-time API reads, and the category split of disputes on the neg-risk and legacy routes comes from an earlier mapping step.

## Findings

1. **Disputes are rare, and most are about timing.** On Polymarket's UMA paths, 1,037 of 1.43M questions proposed between 11 Oct and 17 Nov 2026 were disputed: 0.07% (on-chain, numerator and denominator in the same window; the population is mostly automated sports lines). In 660 of them the UMA vote said the proposal came too early, and there the first answer stood in 550 of 580 settled markets. Where the vote ruled on the facts, the final outcome differs from the first proposal in 169 of 243 settled markets. Overall, 223 of the 929 disputed markets that had settled ended on a different outcome: 24%, with a 95% interval of about 17% to 35% because disputes come in bursts (65 in one minute for one football match). 33 markets had their outcome set directly by the UMA vote; 108 were still open and are not counted.
2. **On the main path, disputed markets usually settle within hours.** The adapter re-asks immediately after a first dispute. On the direct path 70% of all disputed markets settled within 4 hours of the dispute and 84% within a day; on the neg-risk route about half within a day. About 10% were still open at the cutoff. After a first dispute the vote on the disputed request settles days later and does not move the market; after a second dispute the vote sets the outcome.
3. **UMA is not always the final word, on paper.** On the three UMA adapter paths (82.5% of sampled markets; the V2 aggregator and no-resolver markets were not reviewed), verified and publicly audited contract code gives an admin role the power to flag, pause, reset or manually resolve a question, and on neg-risk markets a second contract can set the outcome after a flag. This is a capability in the code, not an observed event: how often it is used and who holds the role are not measured in this release. A forward logger records every such event from 18 Nov 2026.
4. **Settlement lags are measured, but the two venues cannot be compared.** Kalshi settles a median 2.9 minutes after close, and its close is roughly when the outcome is known. Polymarket scheduled markets settle a median 4.0 h after their end date, but for most sports markets the end date is kickoff, so that figure includes the game; where the end date is the observation moment (crypto price markets) the median is 13 minutes. On-chain, the median from UMA proposal to settlement is 0.8 h on the direct path. An earlier version of this release compared the venues by category; that comparison is withdrawn (RESULTS.md section 9).
5. **Money waiting is mostly normal pipeline.** At one snapshot, about $5.8M had waited more than 3 days for settlement across both venues (measured differently on each), and $5.0M of it was one Polymarket election-results market whose end date is election day; without it, about $0.7M. Of the rest of the ~$11M in ended-but-unpaid markets, $3.3M was within 6 hours of closing, $1.1M had waited between 6 hours and 3 days, and $0.8M was on early proposals in markets not yet past their end date.
6. **A public field is not a count of disputes.** Polymarket's data-api `was_disputed` is true for 29 of 691 direct-path questions disputed on-chain. It may mark only disputes escalated to the UMA vote; that was not tested. Dispute statistics here come from on-chain events only.

Full tables: [RESULTS.md](RESULTS.md). Preregistered predictions and how they scored: [docs/PREDICTIONS.md](docs/PREDICTIONS.md) and section 6 of RESULTS.md (three outright misses, four partial, three that cannot be scored cleanly).

## Windows (they differ by measure, and every table says which)

| Measure | Window |
|---|---|
| Polymarket population, path mix, settlement lag | markets closed 17 Nov 2025 to 17 Nov 2026 |
| Polymarket disputes and outcome changes | 11 Oct to 17 Nov 2026, on-chain (free RPC history limit) |
| Kalshi lag, prices, snapshot | markets closed 18 Sep to 17 Nov 2026 (the historical API cannot be sampled by close time) |
| Money waiting | snapshots on 18 Nov 2026, about 06:00 UTC |

## Method in short

- **Polymarket population:** 70,000 random Gamma market IDs (seed fixed in the script), equal inclusion probability per market; 53,801 closed in the window (about 5.48M estimated in total; market creation grew from ~73k a month in Dec 2025 to ~1.3M in Oct 2026). Cross-check: the sample implies ~1.42M UMA markets closing 11 Oct to 17 Nov, the on-chain census counts 1.43M questions. A stratified subsample of 3,105 (category x market type) with expansion weights for lag and classification.
- **Settlement time:** data-api `last_update_timestamp`, validated against the on-chain `ConditionResolution` block on 124 recent resolutions on the two main paths (all within 47 s). On the legacy neg-risk route it is not the settlement time, so those markets are excluded from every lag figure.
- **Paths:** `resolvedBy` mapped to contracts using Polymarket docs, GitHub releases and verified source on Sourcify; levels (documented or inferred) stated per path.
- **Disputes:** every ProposePrice, DisputePrice and Settle event on the two UMA oracles for the Polymarket adapters, grouped by question and request round. The market outcome is the settlement of the latest round; the vote on a disputed request is reported separately.
- **Kalshi:** all settled non-combo markets closing in 300 random 60-second windows (19,373 markets: Kalshi closes whole strike ladders in the same minute, so confidence intervals resample minutes); trades for a category subsample (25 markets in most categories; some categories come from a single close minute and are not reported).
- **Classes:** scheduled vs by-date from question text, tags and series only (no timing or outcome fields), in `scripts/classify.py`. A 100-market check of the rule is in RESULTS.md section 3: the scheduled class is clean (39 of 40), the by-date rule is too wide (20 of 40).

## Limits

- Windows differ by measure. Polymarket and Kalshi lags start from different points (end date, which is kickoff for sports, vs close) and are not compared.
- Disputes cover 37 days in one regime and cluster by match and by disputer; intervals are in RESULTS.md section 2.
- Polymarket lag excludes markets whose end date is later than their close (377 of 1,714 scheduled markets, mostly sports). The median (4 h) is stable across windows; the p90 is 10.3 h over the year and ~6 h in recent months, and timestamps before 9 Oct 2026 could not be checked on-chain.
- Kalshi p90 lag is fragile (64 min, 95% CI 30 min to 9.5 h) because a few minutes hold most of the sample.
- The by-date rule also catches some fixed-moment markets ("this week", "in 2025"), which are then left out of the lag. Counting every excluded market as scheduled leaves the median at 4.0 h and moves the politics median from 24 h to 19 h (politics end dates are mostly the start of the event day, so read that figure loosely).
- The upset rate is secondary: prices often already reflect the outcome before the reference point.
- One unverified UMA requester (74k proposals, 90 disputes in the window) is excluded; if it belongs to Polymarket the dispute denominator would rise about 5%.
- Kalshi challenge history is not public, so Kalshi has no dispute statistics.
- Admin override frequency and holders are not measured in this release.

## How these numbers relate to my earlier work

I have published other numbers on UMA disputes. They do not match the ones above because they count different things. This study covers Polymarket's three main UMA paths from 11 October to 17 November 2026 and works at market level. It compares the final outcome of each disputed market with the first proposal.

**About 14% of disputes ended on a different outcome.** The source is The Missing Greek, in [prediction-market-integrity](https://github.com/x-pertknight/prediction-market-integrity). The scope is 973 disputes on Polymarket's classic resolution adapters, rebuilt from public Polygon RPC. The window is April 2025 to July 2026. The unit is the disputed question, final outcome against original proposal, and the result is 136 of 973, or 14.0%. It differs from the 24% here because it covers the older adapters over an earlier period that does not overlap with this one. Here 1,019 of the 1,037 disputes are on the two paths that use the newer managed oracle.

**54% reset, 22% overturned, 24% upheld.** The source is [uma-disputes-live](https://github.com/x-pertknight/uma-disputes-live), as rebuilt on 17 November 2026. The scope is every disputed and settled price request on UMA's OptimisticOracleV2 and ManagedOptimisticOracleV2 on Polygon, whoever made the request, 4,423 in total. The window is the 365 days to 17 November 2026. The unit is the single price request, not the market. Reset means the vote said too early (54.2%). Overturned means the vote ruled on the facts against the proposal (22.2%). Upheld means the vote confirmed the proposal (23.6%). It differs because it stops at what the vote said about one request. This study follows the market to its final outcome, so a reset that later settles on the first answer counts here as unchanged.

**The dispute rate from my Dune dashboard is not quoted here.** The dashboard is [UMA Oracle, Base Rates vs Anecdotes](https://dune.com/xpertknight/uma-oracle-base-rates-vs-anecdotes). Its query counts every price request and assertion on UMA's optimistic oracles on Polygon since they started, across all three oracle versions, and its dispute rate is disputed requests divided by all requests. That is a lifetime rate per request for every requester. The 0.07% here is one window of 37 days on three Polymarket paths. The stored results of the dashboard had expired when I wrote this section, so I could not confirm its figure and I leave it out.

## Files

- `data/settlement_tracker_v1_markets.csv.gz`: one row per sampled market, both venues; schema in `docs/SCHEMA.md`.
- `charts/`: the four figures.
- `docs/ADMIN_POWERS.md`: admin functions and preconditions, quoted from verified source.
- `scripts/`: collection, validation, classification, the final dispute table, the checks added after review (09 to 12, 14), the charts (13, needs `matplotlib`) and the forward logger (Python standard library otherwise, plus `pycryptodome` for keccak in the on-chain scripts).
- `data/disputes_final.json`: one row per disputed question (path, question ID, first and final answer, how it ended; category and market type for the direct path only); no wallet data.
- `data/class_check_100.csv`: the 100-market check of the class rule.

No wallet-level data is published. Public endpoints only: Polymarket Gamma, data-api and CLOB; Kalshi trade API; a public Polygon RPC.

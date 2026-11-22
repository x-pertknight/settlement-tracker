# settlement_tracker_v1_markets.csv: schema

One row per sampled market. Cutoff 2026-11-17 00:00 UTC. Public data only.

| Column | Meaning |
|---|---|
| venue | polymarket or kalshi |
| market_id | Polymarket Gamma market id (empty for Kalshi) |
| condition_id_or_ticker | Polymarket conditionId, or Kalshi market ticker |
| category | sports, crypto_updown, crypto_other, weather, politics, macro, other (Polymarket, from tags); Kalshi series category |
| market_type | Polymarket: binary, line (totals/spreads/props/O-U), multi (neg-risk). Kalshi: API market_type |
| class | Polymarket only: scheduled / by-date / unclassified (rule in classify.py: question text, tags and series only; 100-market check in RESULTS.md section 3) |
| path | Polymarket settlement path from resolvedBy (UMA MOOV2 direct, UMA MOOV2 routed, UMA OOV2 routed, V2 OracleAggregator, no resolver, other); Kalshi exchange |
| event_end_anchor | Polymarket endDate; Kalshi close_time |
| closed_time | Polymarket closedTime; Kalshi close_time |
| settlement_time | Polymarket data-api last_update_timestamp (validated against on-chain ConditionResolution on the two MOOV2 paths: 124/124 within 47 s); Kalshi settlement_ts |
| lag_hours | settlement_time minus event_end_anchor, only where lag_status = in lag |
| lag_status | in lag; excluded: endDate padded or missing (closedTime earlier than endDate); not validated: API timestamp is not settlement on this path (OOV2 route); not in lag (class or path) |
| disputed_onchain | Polymarket: yes / no for UMA-path markets closed 11 Oct-17 Nov 2026 (on-chain DisputePrice); outside on-chain window otherwise. The data-api was_disputed field is NOT used (it flags 29 of 691 direct-path questions disputed on-chain). Kalshi: not observable from public data |
| sample | how the row was drawn |
| weight | expansion weight. Polymarket: stratum count in the equal-probability S1 sample / rows drawn, times N_est / S1 size (N_est ~5.48M markets in window). Kalshi: 86,400 / 300 = 288 (random 60-second windows) |
| cutoff | study cutoff |
| last_refreshed | when this file was built |

Coverage: Polymarket rows 3,105 (stratified subsample of 53,801 equal-probability markets), of which 1,337 in the lag. Kalshi rows 19,373 (all settled non-combo markets closing in 300 random minutes, 18 Sep-17 Nov 2026).
Wallet-level data: none in this file.

# disputes_timing.csv: schema

One row per disputed question, the same 1,037 questions in the same order as `data/disputes_final.json`.
Built by `scripts/17_fetch_dispute_times.py` (public Polygon RPC `polygon.gateway.tenderly.co`, DisputePrice events
on the two UMA oracles with one of the three Polymarket adapters as requester) and `scripts/18_build_dispute_timing.py`
(public Gamma API). Fetched 2026-11-21 23:56 UTC. Blocks 95,314,366 (first block at or after 2026-10-11 00:00 UTC) to
97,445,420 (last block before 2026-11-17 00:00 UTC), the window of `scripts/04_uma_onchain_census.py`. 1,088 DisputePrice
events on 1,039 questions; the 2 questions without a round 1 proposal in the window are left out, as in `09_disputes_final.py`.

| Column | Meaning |
|---|---|
| qid | adapter questionID, keccak256 of the request's ancillary data |
| path, first, final, how, mtype | copied from `data/disputes_final.json` (final empty = still open at the cutoff) |
| first_dispute_utc, first_dispute_unix | block time of the first DisputePrice event of the question |
| first_dispute_block, first_dispute_log_index | where that event is on chain |
| dispute_events | DisputePrice events of the question in the window (2 = went to a second dispute) |
| market_title | title from the ancillary data |
| polymarket_market_id | market id from the ancillary data (empty for 3 questions) |
| gamma_event_id, gamma_event_slug, gamma_event_title | the market's Gamma event; empty for 22 questions Gamma did not return |

Wallet level data: none in this file. No proposer, disputer or other address and no transaction hash; the
initializer address inside the ancillary data is not copied.

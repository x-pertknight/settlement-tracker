# settlement_tracker_v1_markets.csv: schema

One row per sampled market. Cutoff 2026-11-17 00:00 UTC. Public data only.

| Column | Meaning |
|---|---|
| venue | polymarket or kalshi |
| market_id | Polymarket Gamma market id (empty for Kalshi) |
| condition_id_or_ticker | Polymarket conditionId, or Kalshi market ticker |
| category | sports, crypto_updown, crypto_other, weather, politics, macro, other (Polymarket, from tags); Kalshi series category |
| market_type | Polymarket: binary, line (totals/spreads/props/O-U), multi (neg-risk). Kalshi: API market_type |
| class | Polymarket only: scheduled / by-date / unclassified (rule in classify.py: question text, tags and series only; hand-check pending) |
| path | Polymarket settlement path from resolvedBy (UMA MOOV2 direct, UMA MOOV2 routed, UMA OOV2 routed, V2 OracleAggregator, no resolver, other); Kalshi exchange |
| event_end_anchor | Polymarket endDate; Kalshi close_time |
| closed_time | Polymarket closedTime; Kalshi close_time |
| settlement_time | Polymarket data-api last_update_timestamp (validated against on-chain ConditionResolution on the two MOOV2 paths: 150/150 within 47 s); Kalshi settlement_ts |
| lag_hours | settlement_time minus event_end_anchor, only where lag_status = in lag |
| lag_status | in lag; excluded: endDate padded or missing (closedTime earlier than endDate); not validated: API timestamp is not settlement on this path (OOV2 route); not in lag (class or path) |
| disputed_onchain | Polymarket: yes / no for UMA-path markets closed 11 Oct-17 Nov 2026 (on-chain DisputePrice); outside on-chain window otherwise. The data-api was_disputed field is NOT used (it missed 11 of 11 on-chain disputes). Kalshi: not observable from public data |
| sample | how the row was drawn |
| weight | expansion weight. Polymarket: stratum count in the equal-probability S1 sample / rows drawn, times N_est / S1 size (N_est ~5.48M markets in window). Kalshi: 86,400 / 300 = 288 (random 60-second windows) |
| cutoff | study cutoff |
| last_refreshed | when this file was built |

Coverage: Polymarket rows 3,105 (stratified subsample of 53,801 equal-probability markets), of which 1,337 in the lag. Kalshi rows 19,373 (all settled non-combo markets closing in 300 random minutes, 18 Sep-17 Nov 2026).
Wallet-level data: none in this file.

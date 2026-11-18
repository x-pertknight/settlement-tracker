# Settlement tracker v1: preregistered predictions

v1 written 2026-11-17, before any collection. v2 (same day) updates denominators after the day-1 gates (GATES_REPORT.md, BRIEF_CHANGES.md). v3 (same day) applies decision A (Polymarket event end). v4 (same day) applies decision B (free path only, no Dune).
Study cutoff 2026-11-17 00:00 UTC. Window: resolved markets 6 to 12 months before cutoff; Polymarket window filtered on closedTime.
Rule for v2: predicted ranges are unchanged from v1. Only denominators changed. Where gate data already touched a prediction, it is marked, not rewritten.
All rates are reported by stratum (category x market type), because the Polymarket list is dominated by short-duration markets.

| # | Prediction (range as in v1) | Denominator (v2) | Confidence | Gate status |
|---|---|---|---|---|
| 1 | Path mix close to June to July prior: UMA 60 to 75%, automated resolver 20 to 32%, single key at most 10% | Polymarket resolved markets in window with a non-null `resolvedBy` mapped to a documented adapter. Null and unmapped counts published separately | medium | untested |
| 2 | 0.5 to 1.5% of resolutions disputed at least once | Polymarket resolved markets on the UMA path (from `resolvedBy`), `was_disputed` | medium | seen in gates: 2/200 (1.0%) on a random sample of all paths. Not a test (n too small, wrong denominator) |
| 3 | Outcome changed (a) in 8 to 20% of disputed resolutions | Polymarket disputed resolutions; changed = `proposed_price` differs from final `price` | medium | seen in gates: 0/200 differ on all markets, 0/2 on disputed. Not a test |
| 4 | Betting lines disputed at 2x or more the binary rate, and overturned more often once disputed | Polymarket UMA-path resolved markets, split by market type | medium | untested |
| 5 | Kalshi median lag under 2 h; Polymarket median above Kalshi's | Kalshi: settled non-KXMVE markets, close_time to settlement_ts, all markets (not only traded). Polymarket: **secondary lag** (endDate to `last_update_timestamp`), scheduled class with closedTime >= endDate only. Cross-venue comparison uses this lag only (decision A6) | high | untested |
| 6 | Polymarket p90 lag above 24 h; Kalshi p90 under 12 h | Same as 5 | medium | untested |
| 7 | ~~Inclusive p90 at least 1.5x exclusive p90 on Polymarket~~ (moved to v2); under 10% difference on Kalshi | Polymarket half: **moved to v2** (needs historical proposal times; decision B). Kalshi: ended non-KXMVE markets, with and without pending | low | Kalshi half untested |
| 8 | Polymarket price history recoverable for 70% or more from CLOB /prices-history; OrderFilled fallback raises it to 90% or more | Gate 3 test batch | low | **resolved at gates**: CLOB 50/50; OrderFilled not needed. Reported as a gate result, not counted as a prediction |
| 9 | Upset rate (b) at 0.95/0.05 is 1% or less on both venues; 1 to 3% at 0.90/0.10 | Polymarket: **scheduled class only**, markets with a trade within 24 h (primary) or 60 min (robustness) before endDate; never closedTime. By-date and unclassified markets excluded and counted (no anchor without historical proposal times; decision B1). Kalshi: settled non-KXMVE markets with volume (gates: 88 of 1,000) | medium | untested. Gate 3 coverage figures invalid (measured before closedTime) |
| 10 | 40 to 70% of markets pinned (Yes 0.99 or more, or 0.01 or less) at close | Same as 9 | low | untested |
| 11 | KXMVE combos are 30% or more of Kalshi settled markets in window | All Kalshi settled markets in window | medium | seen in gates on a different set: 4,986 of 5,000 status=closed markets were KXMVE. Not a test (closed, not settled) |
| 12 | (a) No public Polymarket endpoint gives OI for closed-but-unresolved markets. (b) Kalshi snapshot ex-KXMVE under USD 5M, top 5 markets over 50% | (a) endpoint test. (b) Kalshi non-KXMVE markets past close_time and not settled, at snapshot; unit of open_interest_fp to verify first | least confident, method stated | **(a) falsified at gates**: `/v2/oi` returns USD per condition, 40/40. Kept as a miss. (b) untested |
| 13 | ~~resolved_at minus resolved_block: median within 5 minutes~~ Replaced: `last_update_timestamp` minus block time of the resolving tx, median within 5 minutes | Polymarket markets resolved in the last few hours before the validation run, where non-archive public RPC serves the tx | medium | **Confirmed (17 Nov):** 50 most recent resolutions, settle = CTF ConditionResolution block time; median 0 s, max 31 s, 0 of 50 over 1 h. Used as B3 gate with two added pass conditions (at most 5% over 1 h, n at least 30). Scope: recent only, 0 disputed, epoch only, customLiveness empty. Re-run each refresh |

## What changed from v1
- #1: denominator from `resolution_source` to `resolvedBy` adapter mapping (change 5).
- #2, #3: denominator fixed to UMA path / disputed; #3 "changed" now defined as `proposed_price` vs final `price`. Gate glimpses noted.
- #5, #6, #9, #10: Polymarket anchor depends on an event-end field that is not yet defined (open issue A). Kalshi lag uses all settled non-KXMVE; Kalshi upset/pinned uses traded markets only.
- #7: pending now uses the limbo definition (change 2).
- #8: closed by the gates; no longer a prediction.
- #9: primary look-back 24 h, 60 min robustness (change 3).
- #11: gate figure noted (closed list, not settled).
- #12: part (a) falsified at gates and kept as a recorded miss; part (b) gains a unit check.
- #13: replaced, because resolved_block and resolved_at are no longer returned (change 1).

## What changed from v2 (decision A)
- #5, #6: Polymarket denominator = secondary lag, scheduled class, closedTime >= endDate. The primary Polymarket lag (proposal to settlement) is not compared with Kalshi, because it starts at a different point.
- #7: Polymarket inclusive/exclusive now on the primary lag, UMA-path markets only; pending = proposed but not settled at cutoff.
- #9, #10: window ends at the earlier of endDate (scheduled) and first proposal time, never closedTime. Gate 3 coverage marked invalid.
- No new predictions added for the primary lag (proposal to settlement). Adding them now would come after seeing the decision-A evidence; if wanted, add them as v3 additions with that note before collection.
- Depends on gaps A1 to A6 in BRIEF_CHANGES.md (class rule, selection bias, padded endDate, non-UMA paths, resets).

## What changed from v3 (decision B: free path only)
- #7: Polymarket half moved to v2 (historical proposal-to-settlement lag not recoverable free). Kalshi half kept.
- #9, #10: Polymarket window ends at endDate only, so scheduled class only; by-date markets excluded (B1).
- #5, #6: unchanged. They already used the secondary lag (endDate to `last_update_timestamp`, scheduled class). Still conditional on change 1 validating (B3).
- #2, #3, #4: unchanged. Dispute frequency and outcome changed (a) come free from `/v2/resolutions` (`was_disputed`, `proposed_price` vs `price`).
- No prediction on the undisputed proposal-to-settlement lag: it is a documented rule (2 h, or the market's `customLiveness`), checked on recent receipts, not a preregistered estimate (B2, B4).

## What changed after the B3 check
- #13: tested on the 50 most recent resolutions and confirmed. CTF `ConditionResolution` block time is the reference used to validate; the historical lag keeps using `last_update_timestamp`, accepted as settlement time within the stated scope. #5 and #6 stay in v1 (they depended on this).
- #1: path map gains resolver `0x69c47De9...5f24` (20 of 50 recent). Correction: path map shows it is a UMA adapter, not automated. Range unchanged; the path map suggests UMA share well above the prior, so #1 may fail as preregistered.

## What changed after the B3 rerun (150 markets, definition b)
- Settlement time = payout redeemable on ConditionalTokens (`ConditionResolution`). Historical proxy = `last_update_timestamp` (validated on the two mapped MOOV2 paths: 69 of 69 direct, 55 of 55 routed; routed gap median 31 s, max 47 s). The earlier 50-market note under #13 is superseded by this run.
- #13: confirmed per path for UMA MOOV2 direct and routed. Not validated: OOV2 routed (`0x2F5e3684`, absent from sample) and null resolvedBy (26, below n 30).
- #5, #6: ~~Polymarket lag figures for `0x2F5e3684` markets carry "not validated this release" until that path passes.~~ Targeted check failed (17 Nov). Polymarket denominator for #5 and #6 = scheduled-class markets on the two MOOV2 paths only (`0x65070BE9`, `0x69c47De9`). `0x2F5e3684` markets excluded with "not validated: API timestamp is not settlement on this path"; excluded share per month and per category published.
- #2, #3, #4: unchanged; `0x2F5e3684` markets stay in (timestamp-free fields).
- #13: fails on the OOV2 routed path (`last_update_timestamp` not settlement). Holds on the two MOOV2 paths.
- `0x2F5e3684` label: "not yet recovered" (no `ConditionResolution` under any ID within plus/minus 30 blocks).
- Cause from source: NegRiskOperator `0x71523d0f` has `DELAY_PERIOD` = 1 h plus a manual `resolveQuestion` call; `0x661992ae` has `DELAY_PERIOD` = 0.
- #1 path labels now "UMA + operator (delay 0)" and "UMA + operator (delay 1 h)" for routed markets. Range unchanged.
- No prediction added on admin override use: frequency is not measured in v1 (capability only).
- #1: lead only, not a result: null resolvedBy = 26 of 150 (17%), a candidate for the prior's "automated" share. Range unchanged.
- New metric (not a prediction): adapter resolution to redeemable gap, per path.

## Moved to v2
- Polymarket inclusive vs exclusive p90 on proposal-to-settlement lag (old #7 Polymarket half).
- Any historical distribution of dispute durations. Measured forward from release 1.

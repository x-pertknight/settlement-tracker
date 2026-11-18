# Settlement tracker: first release, results

Cutoff 2026-11-17 00:00 UTC. Public data only. Every figure states its window and denominator.

## Windows actually used (differ from the brief, stated everywhere)
| Measure | Window | Why |
|---|---|---|
| Polymarket market population, path mix, settlement lag | markets closed 17 Nov 2025 to 17 Nov 2026 (equal-probability ID sample, 53,801 markets; ~5.48M estimated in window) | full year available through Gamma and data-api |
| Polymarket disputes and outcome changed | 11 Oct to 17 Nov 2026, on-chain (UMA oracle events) | data-api `was_disputed` missed all 11 on-chain disputes we checked (and flags only 3 of 53,801 sampled markets); free RPC history ends ~9 Oct |
| Kalshi settlement lag, upset, snapshot | markets closed 18 Sep to 17 Nov 2026 | Kalshi `/historical/markets` has no close-time filter; older markets cannot be sampled by time |
| Money waiting | snapshots 18 Nov 2026 05:48 (Kalshi) and 06:13 UTC (Polymarket) | snapshot only, not an average |

## 1. Who has the final word (Polymarket path mix, equal-probability sample, n = 53,801)
| Path | Share | Evidence level |
|---|---|---|
| UMA ManagedOOV2, direct adapter 0x6507...2A7 | 64.8% | inferred (verified source + on-chain oracle pointer) |
| UMA ManagedOOV2, neg-risk route 0x69c4...5f24 + operator (delay 0) | 16.8% | inferred |
| No resolver recorded (all short crypto up/down) | 15.4% | unclassified |
| Protocol V2 OracleAggregator | 2.0% | documented (reporter per market not identified) |
| UMA OOV2, neg-risk route 0x2F5e...a9d + operator (delay 1 h) | 0.9% | inferred |
| Other / documented legacy adapters | 0.1% | mixed |

Admin override exists on every mapped path (verified code): adapters can flag, pause, reset or manually resolve (after a flag and a 1 h wait; 2 days on the legacy path); neg-risk operators can block resolution or set the outcome after a flag (no wait on the current route, 1 h on the legacy route), before or after UMA answers, until the result is passed to the market. Frequency of use and current admin holders: not verified in v1. Forward logger records every such event from 18 Nov.

## 2. Disputes (Polymarket, on-chain, 11 Oct to 17 Nov 2026)
| | MOOV2 direct | MOOV2 routed | OOV2 routed | All |
|---|---|---|---|---|
| Questions with a proposal | 1,111,473 | 317,747 | 5,007 | 1,434,227 |
| Disputed | 692 (0.062%) | 327 (0.103%) | 18 (0.359%) | 1,037 (0.072%) |
| Market settled after dispute | 635 | 283 | 11 | 929 |
| Final outcome differs from the first proposal | 28.5% | 14.5% | 9.1% | 24.0% (223 / 929) |
| Dispute to market settle, median / p90 | 1.4 h / 17 h | 8 h / 32 h | 16 h / 21 h | |
| Decided by UMA vote after a 2nd dispute | 35 | 10 | 1 | 46 |
| Open or awaiting a new round at cutoff | 57 | 44 | 7 | 108 |

Excluded: requester 0x5370...8218 (not verified on Sourcify, not in Polymarket docs): 74,202 proposals and 90 disputes in the same 37 days. If it were a Polymarket adapter, the dispute denominator would rise ~5%; rates above would barely move.
Category of disputed markets (mapped to Gamma): sports 832, weather 117, politics 44, other 24. Line bets are disputed 1.82x as often as binary markets (direct path), but change outcome less often once disputed (26.1% vs 36.8%). Validation: on-chain final outcome matches Gamma 97.3% (639/657) on the direct path; 278/278 on the routed path; the 18 direct-path mismatches are markets still open after a single disputed round.

## 3. Settlement lag
| Venue, measure | n | Median | p90 | p99 |
|---|---|---|---|---|
| Polymarket, endDate to settlement, scheduled class, MOOV2 paths, weighted | 1,337 | 4.0 h | 10.3 h | 54 h |
| Polymarket, UMA proposal to settlement (on-chain), direct / routed | 1.11M / 318k | 0.8 h / 2.0 h | 2.1 h / 2.1 h | 2.6 h / 4.8 h |
| Kalshi, close to settlement, all settled non-combo | 19,373 | 2.9 min | 64 min | 13.9 h |
| Kalshi, close to settlement, traded markets only | 6,532 | 4.0 min | 9.2 h | 18.4 h |

Polymarket by category (median / p90): crypto 0.2 h / 2.8 h, macro 2.0 / 4.1, sports 4.0 / 7.8, weather 10.4 / 19.3, politics 24.2 / 108. Kalshi traded, by category (median): sports 4 min, crypto 2.4 min, commodities ~1 h, weather ~1.2 h (tail to 10.8 days), economics ~9.4 h, entertainment ~18 h.
Exclusions: Polymarket markets whose endDate is later than closedTime (padded endDate) are excluded from the lag: 376 of 1,713 scheduled MOOV2 markets in the subsample, 302 of them sports. OOV2-route markets excluded (timestamp not validated). The two venues' lags start at different points and are compared only with that caveat.

## 4. Money waiting for settlement (snapshot, 18 Nov 2026 ~06:00 UTC)
Most of what sits in ended-but-unpaid markets is normal pipeline (hours). The part that has waited more than 3 days is small in count and concentrated.

| Venue | Waiting < 6 h (normal) | 6 h to 3 days | More than 3 days | Not comparable |
|---|---|---|---|---|
| Polymarket, priced gross OI (UMA proposed or disputed, closed=false) | $1.08M (524 markets) | $0.53M (44 markets) | $5.07M (60 markets), $5.03M of it in one market | $0.81M on markets not yet past endDate (89 disputed, 37 proposed: early proposals, not settlement delay) |
| Kalshi, OI contracts x notional (closed, not settled, non-combo) | $2.20M | $0.57M | $0.70M (mostly NYC temperature markets of 13 Nov) | |

Total Polymarket OI at snapshot: $322.6M; the >3-day Polymarket amount is 1.6% of it, almost entirely one market.

## 5. Upset rate (secondary, limits stated)
Polymarket scheduled MOOV2 (anchor: pre-game for sports, endDate otherwise): 1 of 176 favoured at >= 0.95 lost (0.57%, 95% CI 0.1-3.1%); 0 of 131 one hour before. But 60% of endDate-anchored markets already priced >= 0.99 or <= 0.01 in the last hour (outcome known before the anchor), so the rate is biased low. Kalshi: 0 of 223 at close (meaningless: in-play markets close after the outcome); 2 of 118 one hour before close (1.7%, CI 0.5-6.0%), 88 sampled markets had no trade that early.

## 6. Preregistered predictions, scored
| # | Prediction | Result | Verdict |
|---|---|---|---|
| 1 | UMA 60-75%, automated 20-32%, single key <= 10% | UMA ~82.5%, no-resolver (automated candidate) 15.4%, single key none identified | MISS on UMA and automated |
| 2 | 0.5-1.5% disputed | 0.072% of questions (on-chain, 37 days; field in the prediction proved unusable) | MISS (far lower) |
| 3 | Outcome changed in 8-20% of disputed | 24.0% (223/929) | MISS (higher) |
| 4 | Lines disputed >= 2x binary and overturned more often | 1.82x; overturned less often (26.1% vs 36.8%) | MISS |
| 5 | Kalshi median < 2 h; Polymarket median above Kalshi | Kalshi 2.9 min; Polymarket 4.0 h | HIT |
| 6 | Polymarket p90 > 24 h; Kalshi p90 < 12 h | Polymarket 10.3 h; Kalshi 64 min | half: Kalshi HIT, Polymarket MISS |
| 7 | Kalshi inclusive vs exclusive p90 within 10% | not computed (pending set is a snapshot, not dated per market) | NOT TESTED |
| 8 | (gate result) price history recoverable | CLOB 50/50 at gates | resolved at gates |
| 9 | Upset <= 1% at 0.95 both venues; 1-3% at 0.90 | PM 0.57% / 0.55%; Kalshi 1 h before close 1.7% / 1.5% | mixed, and biased (see 5) |
| 10 | 40-70% pinned at close | PM: 60% of endDate-anchored markets reach >= 0.99 or <= 0.01 in the last hour; Kalshi traded sample: 223 of 257 (87%) at >= 0.95 or <= 0.05 at close (pinning threshold differs) | PM HIT; Kalshi MISS (higher), thresholds not identical |
| 11 | KXMVE >= 30% of Kalshi settled | not measured (combos filtered at source) | NOT TESTED |
| 12 | (a) no OI endpoint; (b) Kalshi < $5M, top 5 > 50% | (a) false at gates; (b) $3.48M total (of which $0.70M waiting > 3 days), top 5 = 44% | (a) MISS, (b) half |
| 13 | last_update_timestamp within 5 min of on-chain settlement | 150/150 matched, median 0 s, on MOOV2 paths; fails on OOV2 | HIT on MOOV2, MISS on OOV2 |

Six clear misses out of the testable set. The misses are the finding: disputes are much rarer per market than the prior suggested, but when they happen the final outcome differs from the first proposal about one time in four.

# Settlement tracker: first release, results

Cutoff 2026-11-17 00:00 UTC. Public data only. Every figure states its window and denominator.

## Windows actually used (they differ by measure, stated everywhere)
| Measure | Window | Why |
|---|---|---|
| Polymarket market population, path mix, settlement lag | markets closed 17 Nov 2025 to 17 Nov 2026 (equal-probability ID sample, 53,801 markets; ~5.48M estimated in window) | full year available through Gamma and data-api |
| Polymarket disputes and outcome changed (numerator AND denominator) | 11 Oct to 17 Nov 2026, on-chain (UMA oracle events) | free RPC history ends ~9 Oct; data-api `was_disputed` flags only 29 of 691 on-chain disputed questions (section 2) |
| Kalshi settlement lag, upset, snapshot | markets closed 18 Sep to 17 Nov 2026 | Kalshi `/historical/markets` has no close-time filter; older markets cannot be sampled by time |
| Money waiting | snapshots 18 Nov 2026 05:48 (Kalshi) and 06:13 UTC (Polymarket) | snapshot only, not an average |

## 0. Sample frame checks
- **Market creation grew fast, so most of the ID range closed in the last year.** Gamma IDs rise with creation date. Markets closed per month in the equal-probability sample, scaled to the population: Dec 2025 ~73k, Mar 2026 ~204k, Jun ~323k, Aug ~721k, Sep ~988k, Oct ~1.31M. Most of the volume is short, auto-generated markets (sports lines and props, crypto up/down, price ladders). This is why 53,801 of the 70,000 sampled IDs (77%) closed inside the last year.
- **Independent cross-check of the ~5.48M estimate.** For 11 Oct to 17 Nov 2026 the ID sample implies ~1.42M markets on the three UMA paths (13,956 sampled markets x 101.8). The on-chain census counts 1,434,227 UMA questions with a proposal for the same paths and window. The two independent counts agree within 1%.
- One UMA question per market: the adapter `questionID` is keccak(ancillaryData) of that market, so "questions" in section 2 are markets.

## 1. Who has the final word (Polymarket path mix, equal-probability sample, n = 53,801)
| Path | Share | Evidence level |
|---|---|---|
| UMA ManagedOOV2, direct adapter 0x6507...2A7 | 64.8% | inferred (verified source + on-chain oracle pointer) |
| UMA ManagedOOV2, neg-risk route 0x69c4...5f24 + operator (delay 0) | 16.8% | inferred |
| No resolver in Gamma data (8,297 of 8,298 are short crypto up/down) | 15.4% | unclassified: the API records no resolver, the mechanism is not identified here |
| Protocol V2 OracleAggregator | 2.0% | documented (reporter per market not identified) |
| UMA OOV2, neg-risk route 0x2F5e...a9d + operator (delay 1 h) | 0.9% | inferred |
| Other / documented legacy adapters | 0.1% | mixed |

Admin override in the code (verified source). Scope: the three UMA adapter paths and their two operators, 82.5% of sampled markets; the V2 aggregator and the no-resolver markets were not reviewed. These functions are in public, audited code; nothing here is evidence of use. Adapters can flag, pause, reset or manually resolve (after a flag and a 1 h wait; 2 days on the legacy path); neg-risk operators can block resolution or set the outcome after a flag (no wait on the current route, 1 h on the legacy route), before or after UMA answers, until the result is passed to the market. This is a capability, not an observed event: how often it has been used and which addresses hold the role are not measured in v1. A forward logger records every such event from 18 Nov 2026. In the dispute data below, all 13 third-round re-asks follow a UMA vote result of "too early" (the ignore-price value), not an admin reset.

## 2. Disputes (Polymarket, on-chain, 11 Oct to 17 Nov 2026)
| | MOOV2 direct | MOOV2 routed | OOV2 routed | All |
|---|---|---|---|---|
| Questions with a proposal (same window) | 1,111,473 | 317,747 | 5,007 | 1,434,227 |
| Disputed | 692 (0.062%) | 327 (0.103%) | 18 (0.359%) | 1,037 (0.072%) |
| Market settled after dispute by cutoff | 635 | 283 | 11 | 929 |
| Still open at cutoff (not counted below) | 57 | 44 | 7 | 108 |
| Final outcome differs from the first proposal (share of settled) | 28.5% (181) | 14.5% (41) | 9.1% (1) | 24.0% (223) |
| Dispute to market settle, median / p90 | 1.4 h / 16 h | 8 h / 32 h | 16 h / 21 h | 2.1 h / 31 h |
| Went to a second dispute | 38 | 10 | 1 | 49 |
| of which outcome set by the UMA vote | 30 | 2 | 1 | 33 |
| of which vote returned "too early", question re-asked and settled | 5 | 8 | 0 | 13 |
| of which vote returned "too early", not yet re-asked at cutoff (still open) | 1 | 0 | 0 | 1 |
| of which awaiting the vote at cutoff | 2 | 0 | 0 | 2 |

Rules: the market outcome is the settlement of the latest request round; a first dispute triggers a new round; a second dispute sends the market to the UMA vote; a vote that returns "too early" does not settle the market, which stays open until it is asked again. Two direct-path questions whose round-1 proposal fell before 11 Oct are excluded (first answer unknown). Script: `scripts/09_disputes_final.py`.

The 24.0% is a share of the 929 disputed markets that had settled by the cutoff. The 108 still open are left out; if all of them ended with the first answer, the share would be 21.5% (223 / 1,037); if all of them changed, 31.9%.

**What the vote said about the disputed proposal.** A dispute sends the disputed proposal to the UMA vote while the market is asked again. Splitting the 1,037 by that vote (script `scripts/14_dispute_vote_split.py`):

| Vote on the first disputed proposal | Disputed | Market settled by cutoff | Final outcome differs from first proposal |
|---|---|---|---|
| "Too early" (proposal came before the event could be settled) | 660 | 580 | 30 (5.2%) |
| Ruled on the facts: proposal overturned | 193 | 172 | 169 |
| Ruled on the facts: proposal upheld | 72 | 71 | 0 |
| Vote still pending at cutoff | 112 | 106 | 24 (22.6%) |
| All | 1,037 | 929 | 223 (24.0%) |

So most disputes (64%) are about timing, and in those the first answer nearly always stands. Where the vote ruled on the facts, the final outcome differs in 169 of 243 settled markets (70%). The 24.0% is the mix of the two.

**Disputes come in bursts, so the 24.0% is less precise than 929 markets suggest.** The largest burst is 65 disputes in one minute on one football match (37 exact score questions, 28 spread and total questions). All 65 were still open at the cutoff, awaiting a new round, so they are 65 of the 108 open markets and do not enter the 24.0% or its interval. Among settled markets, one match produced 62 disputes in two consecutive minutes and 98 in total. Resampling whole hours of disputes instead of single markets (199 hours) gives a 95% interval of 16.6% to 35.0%. The same resampling for lines vs binary gives a difference of -10.7 points with an interval of -25.7 to +7.9: the gap is not established.

**Speed counted over all disputed markets, not only the settled ones.** The medians in the table leave out the 108 markets still open. Counting those as not yet settled: on the direct path 70% of disputed markets settled within 4 hours of the dispute and 84% within 24 hours; on the neg-risk route 29% and 49%; on the legacy route 11% and 56%.

Excluded requester: 0x5370...8218 (not verified on Sourcify, not in Polymarket docs): 74,202 proposals and 90 disputes in the same 37 days. If it were a Polymarket adapter, the dispute denominator would rise ~5% and the dispute rate would stay at about 0.07%.

Category of disputed questions (direct path mapped to Gamma by questionID; routed and legacy questions from the stage-2f mapping): sports 830, weather 117, politics 44, crypto 11, macro 9, other 4, not mapped 22 (total 1,037).

Line bets vs binary (direct path): disputed at the same rate once the base is taken from the same window (540 disputed line questions and 151 binary, against 8,609 line and 2,352 binary markets in the same-window sample: ratio 0.98x). The 1.82x in the first draft used full-year base rates against 37 days of disputes; lines went from 66% of direct-path line plus binary markets over the full year to 79% in the dispute window, so that ratio was an artifact. Once disputed, lines change outcome less often (26.1%, 128 / 491) than binary markets (36.8%, 53 / 144).

`was_disputed` check: of the 691 direct-path questions disputed on-chain and mapped to Gamma, data-api `/v2/resolutions` flags 29 (4.2%) as disputed. So the field is not a count of all disputes. It may mark only disputes that were escalated to the UMA vote (38 second disputes on this path), which would make it a narrower field rather than a faulty one; that was not tested here. Script: `scripts/11_check_was_disputed.py`.

Validation: on the direct path, all 635 settled questions map to a Gamma market marked closed, and all 635 match Gamma `outcomePrices`. Routed and legacy paths: 278 settled questions mapped, 278 / 278 match.

## 3. Settlement lag
| Venue, measure | n | Median | p90 | p99 |
|---|---|---|---|---|
| Polymarket, end date to settlement, scheduled class, MOOV2 paths, weighted, full year | 1,337 | 4.0 h | 10.3 h | 54 h |
| same, markets closed 18 Sep to 17 Nov 2026 (Kalshi window) | 506 | 4.0 h | 6.3 h | 29 h |
| same, markets closed from 9 Oct 2026 (period where the timestamp is validated on-chain) | 354 | 4.0 h | 6.1 h | 42 h |
| Polymarket, UMA proposal to settlement (on-chain), direct / routed | 1.11M / 318k | 0.8 h / 2.0 h | 2.1 h / 2.1 h | 2.6 h / 4.8 h |
| Kalshi, close to settlement, all settled non-combo (95% CI, minutes resampled) | 19,373 | 2.9 min (2.7 to 4.1) | 64 min (30 min to 9.5 h) | 10.8 h |
| Kalshi, close to settlement, traded markets only | 6,532 | 4.0 min (4.0 to 6.0) | 9.2 h (6 min to 9.5 h) | 18.4 h |

**What the Polymarket "end date" is.** For sports it is kickoff: in 500 of the 543 sports markets in the lag that carry a game start time, end date equals game start. For weather it is 12:00 UTC of the measured day (318 of 331 scheduled weather markets); for most politics markets it is 00:00 UTC of the event day. Sports are 84.8% of the weight, so the 4.0 h median is mostly the length of a game plus settlement; the weighted median of the non-sports markets is 1.4 h, and crypto price markets, where the end date is the observation moment, settle in a median 13 min. Kalshi's close is roughly the moment the outcome is known. The two lags therefore do not measure the same thing, and the levels cannot be compared across venues.

The Polymarket median is ~4 h in each window (quarters range from 1.3 h, n 18, to 4.5 h). The p90 is not: 10.3 h over the full year, 6.1 to 6.3 h in the recent windows. Settlement timestamps before 9 Oct 2026 could not be checked on-chain (free RPC history), so part of the longer older tail may be timestamp noise rather than slower settlement. Script: `scripts/12_pm_lag_windows.py`.

Kalshi sample design: 300 random minutes out of the 86,400 in the window. Kalshi closes whole strike ladders at once (dozens to thousands of markets in the same minute), so 192 of the 300 minutes contain markets and 5 minutes hold 68% of the 19,373. Confidence intervals resample minutes, not markets. The median is robust; the p90 is not, and is reported with its interval. Script: `scripts/10_kalshi_cluster_ci.py`.

By category, medians. Polymarket (end date to settlement, full year): crypto 13 min (n 391), macro 2.0 h (n 50), sports 4.0 h (n 553), weather 10.4 h (n 269), politics 24.2 h (n 31). Kalshi (close to settlement, trades sample; markets and distinct close minutes in brackets): crypto 2.5 min (25, 11), sports 4 min (25, 19), mentions 31 min (25, 5), financials 42 min (25, 10), commodities 1.1 h (25, 9, of which 17 markets in one minute), weather 1.2 h (43, 7). Economics (9.4 h), entertainment (17.9 h) and politics (31 min, 9 markets) each come from a single close minute, that is one settlement batch, so they are not category figures and are withdrawn from the findings. Categories are defined differently on the two venues.

Exclusions: Polymarket markets whose end date is later than their close (padded end date) are excluded from the lag: 377 of 1,714 scheduled MOOV2 markets in the subsample, 302 of them sports; the direction of this bias is not known. The OOV2 route (0.9% of markets) is excluded because its timestamp does not match on-chain settlement; its on-chain proposal-to-settlement time (median 2.0 h, p90 2.0 h) is in line with the other paths, but that is UMA's time, not the market's: on this route the operator adds a 1 h delay and a manual call, so a slower tail on these markets cannot be ruled out. The two venues' lags start at different points (end date vs close) and are compared only on shape.

Class rule check: 100 markets (40 scheduled, 40 by-date, 20 unclassified) were labelled again from the question text alone. Scheduled: 39 of 40 agree, so little that is not a fixed-moment market gets into the lag. By-date: 20 of 40 agree; the rule also catches fixed-moment markets worded with "this week" or "in 2025" (weekly charts, year-end closes, an election), which are left out of the lag. Of the 20 unclassified, 12 are fixed-moment markets. By-date and unclassified markets are 0.3% and 1.8% of the weighted population. Sensitivity: if every by-date and unclassified market on the two MOOV2 paths were counted as scheduled (n 1,871), the median stays 4.0 h and the p90 moves from 10.3 h to 10.6 h; the politics median moves from 24.2 h (n 31) to 19.4 h (n 247) and macro from 2.0 h to 1.7 h. Read the politics figure as "about a day", not as a precise number. Labels: `data/class_check_100.csv`.

## 4. Money waiting for settlement (snapshot, 18 Nov 2026 ~06:00 UTC)
The two venues are measured differently (Polymarket: priced open interest; Kalshi: contracts x $1), and the Polymarket side covers only markets already proposed or disputed on UMA, not ended markets still waiting for a first proposal. Most of what sits in ended-but-unpaid markets is normal pipeline (hours). The part that has waited more than 3 days is one Polymarket market plus a small Kalshi remainder.

| Venue | Waiting < 6 h (normal) | 6 h to 3 days | More than 3 days | Not comparable |
|---|---|---|---|---|
| Polymarket, priced gross OI (UMA proposed or disputed, closed=false) | $1.08M (524 markets) | $0.53M (44 markets) | $5.07M (60 markets): $5.03M in one election-results market whose end date is election day, $0.04M in the other 59 | $0.81M on markets not yet past their end date (89 disputed, 37 proposed: early proposals, not settlement delay) |
| Kalshi, OI contracts x notional (closed, not settled, non-combo) | $2.20M | $0.57M | $0.70M (mostly NYC temperature markets of 13 Nov) | |

Total Polymarket OI at snapshot: $322.6M; the >3-day Polymarket amount is 1.6% of it, almost all of it one market. For an election-results market the end date is election night, before results are official, so its wait is partly an artifact of the end-date anchor.

## 5. Upset rate (secondary, limits stated)
Polymarket scheduled MOOV2 (anchor: pre-game for sports, end date otherwise): 1 of 176 favoured at >= 0.95 lost (0.57%, 95% CI 0.1 to 3.1%); 0 of 131 one hour before. But 60% of end-date-anchored markets already priced >= 0.99 or <= 0.01 in the last hour (outcome known before the anchor), so the rate is biased low.
Kalshi at close: not measurable, because in-play markets close after the outcome is known (223 favoured, 0 lost, by construction). Kalshi one hour before close: 2 of 118 favoured at >= 0.95 lost (1.7%, 95% CI 0.5 to 6.0%). The denominator is the 118 markets that had a trade in that hour and a favourite at >= 0.95; 88 sampled markets with no trade that early are excluded, not counted as non-upsets.

## 6. Predictions, scored
| # | Prediction | Result | Verdict |
|---|---|---|---|
| 1 | UMA 60-75%, automated 20-32%, single key <= 10% | UMA ~82.5%, no-resolver (automated candidate) 15.4%, single key none identified | MISS on UMA and automated |
| 2 | 0.5-1.5% disputed | 0.072% of questions (on-chain, 37 days; field in the prediction proved unusable) | MISS (far lower) |
| 3 | Outcome changed in 8-20% of disputed | 24.0% of settled (223/929); 95% interval 16.6% to 35.0% with clustered disputes | NOT ESTABLISHED (point estimate above the range, interval overlaps it) |
| 4 | Lines disputed >= 2x binary and overturned more often | 0.98x (same window); overturned 26.1% vs 36.8%, difference not established | MISS on the rate; second half not established |
| 5 | Kalshi median < 2 h; Polymarket median above Kalshi | Kalshi 2.9 min; Polymarket 4.0 h | NOT TESTABLE as written: Polymarket counts from kickoff for sports, Kalshi from the close |
| 6 | Polymarket p90 > 24 h; Kalshi p90 < 12 h | Polymarket 10.3 h (6.1 h recent); Kalshi 64 min (CI up to 9.5 h) | Kalshi HIT; Polymarket not testable (same anchor problem) |
| 7 | Kalshi inclusive vs exclusive p90 within 10% | not computed (pending set is a snapshot, not dated per market) | NOT TESTED |
| 8 | (gate result) price history recoverable | CLOB 50/50 at gates | resolved at gates |
| 9 | Upset <= 1% at 0.95 both venues; 1-3% at 0.90 | PM 0.57% / 0.55%; Kalshi 1 h before close 1.7% / 1.5% | partial MISS (Polymarket 0.55% at 0.90 is below 1-3%; Kalshi 1.7% at 0.95 is above 1%), and biased (see 5) |
| 10 | 40-70% pinned at close | PM: 60% of end-date-anchored markets reach >= 0.99 or <= 0.01 in the last hour; Kalshi traded sample: 223 of 257 (87%) at >= 0.95 or <= 0.05 at close (pinning threshold differs) | PM HIT; Kalshi MISS (higher), thresholds not identical |
| 11 | KXMVE >= 30% of Kalshi settled | not measured (combos filtered at source) | NOT TESTED |
| 12 | (a) no OI endpoint; (b) Kalshi < $5M, top 5 > 50% | (a) false at gates; (b) $3.48M total (of which $0.70M waiting > 3 days), top 5 = 44% | (a) MISS, (b) half |
| 13 | last_update_timestamp within 5 min of on-chain settlement | 124/124 matched on the two MOOV2 paths (69 direct, 55 routed; 150/150 counting 26 no-resolver markets), median 0 s; fails on OOV2 | HIT on MOOV2, MISS on OOV2 |

Three predictions missed outright (1, 2, 4), four missed in part (9, 10, 12, 13), and three cannot be scored cleanly (3, 5, 6). Deviation from the written predictions: they named markets resolved 6 to 12 months before the cutoff; the results use the full 12 months, because most markets in the sample closed in the last six. Disputes are much rarer per market than the prior suggested, but when one happens the final outcome differs from the first proposal in about one settled case in four.

## 7. Corrections after independent review (18 Nov 2026)
- Disputed-by-category counts did not add up (unmapped questions had been dropped). Recomputed on the final set; they now sum to 1,037.
- Validation denominator came from an earlier intermediate set (657). Recomputed on the final set: 635 / 635 direct.
- Line vs binary dispute ratio: 1.82x mixed a full-year base with a 37-day numerator. Same-window ratio is 0.98x.
- `was_disputed`: "missed all 11 checked" replaced by the full check, 29 of 691 flagged.
- Dispute table reproduced by a committed script: direct-path settled 636 (was 635), outcome changed 182 (was 181); "decided by vote" split into the three cases above (the first draft counted every second dispute as a vote decision).
- Kalshi lag: confidence intervals that account for minute clustering; p99 recomputed with the committed script (10.8 h, first draft 13.9 h).
- Kalshi category medians: sample size per category stated (25, not 6,532); entertainment 17.9 h (first draft 18.4 h).
- Money waiting: the >3-day Polymarket amount is one market, now said in the title and table.
- Polymarket lag by window and the frame cross-check added.

## 8. Corrections after a second consistency check (18 Nov 2026)
- One direct-path question had been counted as settled with the UMA "too early" value as its outcome. Both of its rounds were voted "too early" on 11 Nov and no new round had opened by the cutoff, so it is open (Gamma still lists it as open and disputed). Settled 929 (was 930), outcome changed 223 (was 224), 24.0% (was 24.1%); direct path 635 / 181 / 28.5%; outcome set by the vote 33 (was 34); still open 108. Binary share changed once disputed 36.8% (was 37.2%). Direct-path p90 from dispute to settlement 16 h (was 17 h). `scripts/09_disputes_final.py` now treats this case as open.
- Settlement-time validation: 124 of 124 on the two MOOV2 paths, not 150 of 150. The other 26 checked markets have no resolver in Gamma data; they also matched but are not one of the validated paths.
- Classifier: month names are now matched as whole words ("by market cap" had been read as "by" + March). Three markets move from by-date to scheduled; none enters the lag (two are on the OOV2 route, one has a padded end date), so no lag figure changes. Padded-end-date count is now 377 of 1,714.
- Class rule check and sensitivity added (section 3). Prediction score reworded: four outright misses and four partial, instead of "six clear misses". Kalshi snapshot total: see section 9.

## 9. Further corrections after independent review (18 Nov 2026)
The published repo was checked independently three times: the numbers, the method, and how an informed reader would read it. The dispute table, path mix, population estimate, lag table and Kalshi intervals were recomputed independently and reproduce. What changed:
- **Cross-venue speed comparison withdrawn.** Polymarket's end date is kickoff for sports, midday for weather and start of day for most politics, so its lag includes the event itself; Kalshi's close is roughly when the outcome is known. Predictions 5 and 6 rescored as not testable.
- **Kalshi category figures for economics, entertainment and politics withdrawn**: each rests on one settlement batch (a single close minute).
- **Disputes split by the vote** (section 2): 660 of 1,037 were voted "too early"; the 24.0% mixes 5.2% in those with 70% where the vote ruled on the facts.
- **Interval added to the 24.0%** (16.6% to 35.0%, clustered); prediction 3 rescored from MISS to not established; the line vs binary gap is not established.
- **Dispute-to-settlement speed restated over all disputed markets**, open ones included.
- **was_disputed reworded**: not a count of all disputes; possibly a flag for escalated disputes only (not tested).
- **Admin override scope stated**: the three UMA adapter paths, 82.5% of sampled markets.
- Kalshi snapshot total is $3.48M (3,477,920); the $3.47M in the previous correction was a sum of rounded buckets and was itself wrong. Prediction 9 scored as a partial miss. "Stable across quarters" corrected.
Not yet done, stated as open: counting admin events in the on-chain window; checking the was_disputed interpretation against the vote; identifying the resolver of the no-resolver markets (Polymarket documents a data-feed resolution for up/down markets, not verified here); dispute rates per category and per dollar; a script for the money-waiting snapshot.

# Admin powers on the mapped Polymarket resolution paths (Q5)

Source: verified contract source on Sourcify (`exact_match`, Polygon 137), read 18 Nov 2026.
All three adapters are `UmaCtfAdapter`, Solidity 0.8.15. `0x65070BE9...` and `0x69c47De9...` have identical admin logic; `0x2F5e3684...` differs only in names and the safety period.
This file documents **capability in code**. Who holds the admin role today and how often these functions are used are **not verified in this release**.

## Constants
| Adapter | Path | Constant | Value |
|---|---|---|---|
| `0x65070BE91477460D8A7AeEb94ef92fe056C2f2A7` | MOOV2 direct | `SAFETY_PERIOD` | 1 hour |
| `0x69c47De9D4D3Dad79590d61b9e05918E03775f24` | MOOV2 routed | `SAFETY_PERIOD` | 1 hour |
| `0x2F5e3684cb1F318ec51b00Edba38d79Ac2c0aA9d` | OOV2 routed | `EMERGENCY_SAFETY_PERIOD` | 2 days |

## Functions and preconditions (all `onlyAdmin`)
| Function | Preconditions in code | Effect |
|---|---|---|
| `flag(questionID)` | initialized; not already flagged; **not resolved** | sets `paused = true`; starts the clock: override allowed from `block.timestamp + SAFETY_PERIOD` (1 h) or `+ EMERGENCY_SAFETY_PERIOD` (2 days) |
| `unflag(questionID)` | initialized; flagged; not resolved; **only before** the safety period ends (`block.timestamp > deadline` reverts `SafetyPeriodPassed`) | clears the flag and the pause |
| `resolveManually(questionID, payouts)` (MOOV2 adapters) | valid payout array; initialized; **must be flagged**; **only after** the safety period (`block.timestamp < deadline` reverts `SafetyPeriodNotPassed`) | marks resolved and calls `ctf.reportPayouts` with the admin's payouts. UMA's price is not read |
| `emergencyResolve(questionID, payouts)` (OOV2 adapter) | same as `resolveManually`, with the 2-day period | same effect |
| `pause(questionID)` | initialized; not resolved | `paused = true`. **No time limit in code**: the public `resolve()` reverts with `Paused` until `unpause` |
| `unpause(questionID)` | (body not printed in this read; symmetric to pause) | clears the pause |
| `reset(questionID)` | initialized; not resolved | refunds the reward if due, then sends a **new** UMA price request paid by the caller |

Public path for comparison: `resolve(questionID)` (anyone) requires initialized, **not paused**, not resolved, and a UMA price available; it then reads the price from the oracle and reports payouts.

## What this means, stated exactly
1. **A flag must come first.** Manual or emergency resolution is impossible on an unflagged question.
2. **The safety period runs from the flag, not from UMA's answer.** Earliest override: 1 hour after the flag (MOOV2 adapters), 2 days after the flag (OOV2 adapter). During that period the admin can still `unflag`.
3. **The window is "before the adapter resolves".** `flag`, `pause` and `reset` all revert once `resolved = true`. So the adapter admin can act during UMA's liveness or dispute, and also **after UMA has a price but before anyone calls `resolve()`**. Once the adapter has resolved, the adapter admin can no longer change the outcome.
4. **Pause has no expiry.** A paused, unflagged question cannot be resolved through the public path until the admin unpauses it.
5. **Reset sends the question back to UMA** with a new request; it does not set an outcome by itself.
6. **Neg-risk markets have a second layer.** On the routed paths, the adapter reports to a NegRiskOperator, which has its own admin powers (next section).

## NegRiskOperator (neg-risk routes): functions and preconditions
Source: Sourcify `exact_match`, `NegRiskOperator`, Solidity 0.8.19, read 18 Nov 2026. Admin logic identical on both; only `DELAY_PERIOD` differs.

| Operator | Route | `DELAY_PERIOD` |
|---|---|---|
| `0x661992aebf6becf7ba5abb66f6b0bf62aa7a2e93` | MOOV2 routed (adapter `0x69c47De9`), current | **0** |
| `0x71523d0f655b41e805cec45b17163f528b59b820` | OOV2 routed (adapter `0x2F5e3684`), older | 1 hour |

| Function | Who | Preconditions in code | Effect |
|---|---|---|---|
| `reportPayouts(requestId, payouts)` | oracle only (the adapter) | 2 payouts summing to 1; known request; **not already reported** | stores the result and `reportedAt`; does not resolve |
| `resolveQuestion(questionId)` | **anyone** | **not flagged**; a result reported; `block.timestamp >= reportedAt + DELAY_PERIOD` | passes the stored (UMA) result to the NegRiskAdapter (`nrAdapter.reportOutcome`) |
| `flagQuestion(questionId)` | admin | not already flagged. **No check on whether UMA has reported** | records `flaggedAt`; blocks `resolveQuestion` |
| `unflagQuestion(questionId)` | admin | flagged. **No time limit** | clears the flag |
| `emergencyResolveQuestion(questionId, result)` | admin | flagged; `block.timestamp >= flaggedAt + DELAY_PERIOD`. **No check on `reportedAt`** | passes the **admin's** result to the NegRiskAdapter |
| `addAdmin(a)` / `removeAdmin(a)` / `renounceAdmin()` | admin | none beyond being admin | any single admin can add or remove admins; no threshold in this contract |

### What this means, stated exactly
1. **On the current neg-risk operator the override has no waiting period.** With `DELAY_PERIOD = 0`, an admin can flag and emergency-resolve in the same block.
2. **The override can replace UMA's answer after UMA has reported**, as long as `resolveQuestion` has not yet passed it on. It can also act **before UMA answers**: `emergencyResolveQuestion` does not require a report.
3. **A flag blocks the public path indefinitely** (no expiry on the operator flag).
4. **One admin is enough.** Each admin acts alone, and any admin can add others. Whether the admin addresses are themselves multisigs or timelocks is not verified.
5. Whether `nrAdapter.reportOutcome` rejects a second report (which would make the outcome final after the first resolve or emergency resolve) is in the NegRiskAdapter, **not read in this pass**.

## Measured context (17 Nov data)
On the MOOV2 direct path the adapter resolution and the CTF payout report were within 0 s median of `last_update_timestamp` (B3 rerun). So in practice the "after UMA price, before `resolve()`" window is very short when resolution is called promptly. Whether it is called promptly on every market is not measured.

## Summary wording used in the release

"On every mapped Polymarket path, verified code gives an admin role the power to flag, pause, reset or manually resolve a question over UMA's answer. At the adapter level, manual resolution requires a prior flag and a waiting period from the flag: 1 hour on the current path, 2 days on the older path; pause has no time limit. On neg-risk markets a second contract adds its own admin override: after a flag, an admin can set the outcome with no waiting period on the current route (1 hour on the older route), before or after UMA has answered, as long as the result has not yet been passed on to the market. A flag blocks normal resolution with no time limit. The original deployer no longer holds the operator role. Current holders and frequency of use are not verified in this release."

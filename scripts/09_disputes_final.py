#!/usr/bin/env python3
"""Final dispute table from on-chain UMA events (input: s2d_disputed_questions.json).
Rules: rounds = request timestamps; the market outcome is the Settle of the LATEST round,
unless that round is disputed: a first dispute means a new round is still to come (pending),
a second dispute means the market waits for the UMA vote (outcome = that round's Settle).
Questions whose round-1 proposal is not in the window are excluded (first answer unknown).
Usage: python3 -I 09_disputes_final.py s2d_disputed_questions.json out.json"""
import json, sys, collections
PATH = {"0x65070be9": "MOOV2 direct", "0x69c47de9": "MOOV2 routed", "0x2f5e3684": "OOV2 routed"}

def q(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p; f = int(k); c = min(f + 1, len(xs) - 1)
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 1)

d = json.load(open(sys.argv[1]))
out = collections.defaultdict(collections.Counter); lag = collections.defaultdict(list); rows = []
for r in d:
    path = PATH.get(r["req"][:10].lower(), "other")
    P, D, S = (collections.defaultdict(list) for _ in range(3))
    for k, m in (("P", P), ("D", D), ("S", S)):
        for t, v, rt in r[k]:
            m[rt].append((t, v))
    if not D:
        continue
    rounds = sorted(set(P) | set(D) | set(S)); r1, L = rounds[0], rounds[-1]
    if not P.get(r1):
        out[path]["excluded_no_round1_proposal"] += 1; continue
    o = out[path]; o["disputed"] += 1
    nd = sum(1 for rt in rounds if D.get(rt))
    if nd >= 2: o["second_dispute"] += 1
    if len(rounds) >= 3 and not D.get(L): o["reasked_after_vote_ignore"] += 1
    first = min(P[r1])[1]
    if D.get(L):
        if nd >= 2 and S.get(L): final, how = min(S[L])[1], "vote"
        else: final, how = None, "awaiting_vote" if nd >= 2 else "awaiting_new_round"
    else:
        final, how = (min(S[L])[1], "settled") if S.get(L) else (None, "awaiting_settle")
    rows.append({"path": path, "qid": r["qid"], "first": first, "final": final, "how": how})
    if final is None:
        o[how] += 1; continue
    o["market_settled"] += 1
    if how == "vote": o["decided_by_vote"] += 1
    if final != first: o["outcome_changed"] += 1
    t_d = min(t for rt in rounds for t, _ in D.get(rt, []))
    lag[path].append((min(S[L])[0] - t_d) / 3600)
res = {}
tot = collections.Counter(); alllag = []
for p in sorted(out):
    o = out[p]; tot += o; alllag += lag[p]
    res[p] = dict(o, outcome_changed_pct=round(100 * o["outcome_changed"] / o["market_settled"], 1),
                  dispute_to_market_settle_h={"median": q(lag[p], .5), "p90": q(lag[p], .9)})
res["All"] = dict(tot, outcome_changed_pct=round(100 * tot["outcome_changed"] / tot["market_settled"], 1),
                  dispute_to_market_settle_h={"median": q(alllag, .5), "p90": q(alllag, .9)})
json.dump({"by_path": res, "rows": rows}, open(sys.argv[2], "w"), indent=1)
for p, v in res.items(): print(p, v)

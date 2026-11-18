#!/usr/bin/env python3
"""Disputes split by what the UMA vote said about the disputed proposal, with intervals that respect clustering.

Why: disputes come in bursts (many questions of one match disputed in the same minute), and most are about
timing ("too early"), not about the facts. A single 24% hides both.

Inputs: the on-chain question file used by 09_disputes_final.py, and that script's output (or data/disputes_final.json).
Usage: python3 -I 14_dispute_vote_split.py s2d_disputed_questions.json disputes_final.json
"""
import collections, json, random, sys

IGNORE = str(-2**255)  # UMA "too early" answer


def vote_kind(q):
    """What the vote said about the FIRST disputed proposal: too early / upheld / overturned / pending."""
    P, D, S = (collections.defaultdict(list) for _ in range(3))
    for key, store in (("P", P), ("D", D), ("S", S)):
        for t, v, rnd in q[key]:
            store[rnd].append((t, str(v)))
    r1 = min(set(P) | set(D) | set(S))
    if not S.get(r1):
        return "vote pending"
    vote, first = min(S[r1])[1], min(P[r1])[1]
    if vote == IGNORE:
        return "too early"
    return "upheld" if vote == first else "overturned"


def cluster_ci(groups, stat, reps=4000, seed=1):
    """95% interval, resampling whole clusters (hours of dispute) instead of single questions."""
    keys, rng, out = list(groups), random.Random(seed), []
    for _ in range(reps):
        sample = [x for k in rng.choices(keys, k=len(keys)) for x in groups[k]]
        out.append(stat(sample))
    out.sort()
    return round(out[int(reps * .025)], 1), round(out[int(reps * .975) - 1], 1)


def pct_changed(rows):
    return 100 * sum(r["changed"] for r in rows) / len(rows)


def line_minus_binary(rows):
    a = [r for r in rows if r["mtype"] == "line"]; b = [r for r in rows if r["mtype"] == "binary"]
    return pct_changed(a) - pct_changed(b) if a and b else 0.0


questions = {q["qid"]: q for q in json.load(open(sys.argv[1]))}
final = json.load(open(sys.argv[2]))["rows"]

split = collections.defaultdict(collections.Counter)
by_hour = collections.defaultdict(list); by_minute = collections.Counter(); open_by_minute = collections.Counter()
speed = collections.defaultdict(lambda: [0, 0, 0])
for f in final:
    q = questions[f["qid"]]
    t_dispute = min(t for t, _, _ in q["D"])
    settled = f["final"] is not None
    changed = settled and str(f["final"]) != str(f["first"])
    kind = vote_kind(q)
    split[kind]["disputed"] += 1
    split[kind]["settled"] += settled
    split[kind]["changed"] += changed
    by_minute[t_dispute // 60] += 1
    if not settled:
        open_by_minute[t_dispute // 60] += 1
    else:
        by_hour[t_dispute // 3600].append({"changed": changed, "mtype": f.get("mtype")})
    # Speed over ALL disputed markets: an open market counts as not settled yet.
    s = speed[f["path"]]; s[0] += 1
    if settled:
        last_round = max(rnd for key in "PDS" for _, _, rnd in q[key])
        hours = (min(t for t, _, rnd in q["S"] if rnd == last_round) - t_dispute) / 3600
        s[1] += hours <= 4; s[2] += hours <= 24

rows = [r for v in by_hour.values() for r in v]
big = by_minute.most_common(1)[0]
out = {
    "by_vote_on_first_disputed_proposal": {k: dict(v, changed_pct_of_settled=round(100 * v["changed"] / v["settled"], 1) if v["settled"] else None)
                                           for k, v in sorted(split.items())},
    "ruled_on_the_facts": {"settled": split["upheld"]["settled"] + split["overturned"]["settled"],
                           "changed": split["upheld"]["changed"] + split["overturned"]["changed"]},
    "all_settled": {"n": len(rows), "changed_pct": round(pct_changed(rows), 1),
                    "ci95_hour_clusters": cluster_ci(by_hour, pct_changed), "hour_clusters": len(by_hour)},
    "line_minus_binary_changed_pp": {"point": round(line_minus_binary(rows), 1), "ci95_hour_clusters": cluster_ci(by_hour, line_minus_binary)},
    "largest_one_minute_burst": {"disputes": big[1], "still_open_at_cutoff": open_by_minute[big[0]]},
    "share_of_all_disputed_settled_within": {p: {"disputed": n, "4h_pct": round(100 * a / n), "24h_pct": round(100 * b / n)}
                                             for p, (n, a, b) in sorted(speed.items())},
}
print(json.dumps(out, indent=1))

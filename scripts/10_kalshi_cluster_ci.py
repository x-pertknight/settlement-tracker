#!/usr/bin/env python3
"""Kalshi close-to-settlement lag with cluster-bootstrap CIs. The sample unit is a random minute; markets closing in the
same minute (strike ladders) are not independent, so minutes are resampled. Usage: python3 -I 10_kalshi_cluster_ci.py kalshi_minutes.jsonl.gz"""
import gzip, json, sys, random, collections, datetime as dt
rows = [json.loads(l) for l in gzip.open(sys.argv[1], "rt")]
p = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
def pct(xs, q):
    xs = sorted(xs); return xs[int(q * (len(xs) - 1))]
out = {}
for name, keep in (("all settled non-combo", lambda r: True), ("traded only", lambda r: float(r.get("volume_fp") or 0) > 0)):
    cl = collections.defaultdict(list)
    for r in rows:
        if r.get("settlement_ts") and r.get("close_time") and keep(r):
            cl[r["hour_index"]].append((p(r["settlement_ts"]) - p(r["close_time"])).total_seconds() / 60)
    allv = [x for v in cl.values() for x in v]; keys = list(cl); rng = random.Random(20261119); bs = collections.defaultdict(list)
    for _ in range(2000):
        s = [x for k in (rng.choice(keys) for _ in keys) for x in cl[k]]
        for q in (.5, .9, .99): bs[q].append(pct(s, q))
    sizes = sorted((len(v) for v in cl.values()), reverse=True)
    out[name] = {"n": len(allv), "minutes_with_markets": len(cl), "share_top5_minutes": round(sum(sizes[:5]) / len(allv), 3),
                 **{f"p{int(q*100)}_min": round(pct(allv, q), 1) for q in (.5, .9, .99)},
                 **{f"p{int(q*100)}_ci95_min": [round(pct(bs[q], .025), 1), round(pct(bs[q], .975), 1)] for q in (.5, .9, .99)}}
print(json.dumps(out, indent=1))

#!/usr/bin/env python3
"""Polymarket endDate-to-settlement lag (scheduled class, MOOV2 paths, weighted) by window, to compare like for like with Kalshi
and to see whether old (unvalidated) timestamps behave differently. Usage: python3 -I 12_pm_lag_windows.py s2_subsample.jsonl.gz classes.csv"""
import gzip, json, csv, sys, datetime as dt, collections
cls = {r["id"]: r["class"] for r in csv.DictReader(open(sys.argv[2]))}
rows = [json.loads(l) for l in gzip.open(sys.argv[1], "rt")]
def p(s):
    s = str(s).replace(" ", "T")
    if s.endswith("+00"): s += ":00"
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
def ts(x):
    x = str(x); return dt.datetime.fromtimestamp(int(x), dt.timezone.utc) if x.isdigit() else p(x)
def wq(pairs, q):
    pairs = sorted(pairs); tot = sum(w for _, w in pairs); acc = 0
    for v, w in pairs:
        acc += w
        if acc >= q * tot: return round(v, 2)
pts = []
for r in rows:
    if cls.get(r["id"]) != "scheduled" or r["path"] not in ("UMA MOOV2 direct", "UMA MOOV2 routed"): continue
    res = r.get("res") or {}
    if not res.get("last_update_timestamp") or res.get("status") != "resolved" or not r.get("endDate") or not r.get("closedTime"): continue
    e, c = p(r["endDate"]), p(r["closedTime"])
    if e > c: continue
    pts.append(((ts(res["last_update_timestamp"]) - e).total_seconds() / 3600, r["weight"], c, r["category"]))
P = lambda s: [(a, b) for a, b, _, _ in s]
out = {}
def put(name, s):
    out[name] = {"n": len(s), "median_h": wq(P(s), .5), "p90_h": wq(P(s), .9), "p99_h": wq(P(s), .99)}
put("full year", pts)
put("18 Sep to 17 Nov 2026 (Kalshi window)", [x for x in pts if x[2] >= dt.datetime(2026, 9, 18, tzinfo=dt.timezone.utc)])
put("closed before 9 Oct 2026 (timestamp not validated on-chain)", [x for x in pts if x[2] < dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)])
put("closed from 9 Oct 2026 (validated period)", [x for x in pts if x[2] >= dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)])
by = collections.defaultdict(list)
for x in pts: by[f"{x[2].year} Q{(x[2].month - 1) // 3 + 1}"].append(x)
for k in sorted(by): put(k, by[k])
kw = [x for x in pts if x[2] >= dt.datetime(2026, 9, 18, tzinfo=dt.timezone.utc)]
cat = collections.defaultdict(list)
for x in kw: cat[x[3]].append(x)
out["by_category_kalshi_window"] = {c: {"n": len(v), "median_h": wq(P(v), .5), "p90_h": wq(P(v), .9)} for c, v in sorted(cat.items())}
print(json.dumps(out, indent=1))

#!/usr/bin/env python3
"""Stage 5: Polymarket upset rate, scheduled class, MOOV2 paths only.
Anchor: sports with gameStartTime -> gameStartTime (pre-game price);
        other categories -> endDate, only if closedTime >= endDate (else endDate is padded: excluded, counted).
Price = last CLOB prices-history point at or before anchor, and at or before anchor - 1 h (fidelity 1 min, window 6 h).
Favoured side = first outcome token price >= h or <= 1-h; upset = final outcomePrices goes against it.
Usage: python3 -I stage5_pm_upset.py <classes.csv> <out.json>
"""
import collections, csv, datetime as dt, gzip, json, math, random, sys, time, urllib.parse, urllib.request

CLS, OUT = sys.argv[1], sys.argv[2]
SEED, CAP = 20261121, 60
cls = {r["id"]: r["class"] for r in csv.DictReader(open(CLS))}
s1 = {json.loads(l)["id"]: json.loads(l) for l in gzip.open("idsample/sample.jsonl.gz", "rt")}
sub = [json.loads(l) for l in gzip.open("s2/s2_subsample.jsonl.gz", "rt")]


def T(s):
    if not s or str(s) == "None": return None
    s = str(s).replace(" ", "T").replace("Z", "+00:00")
    if s.endswith("+00"): s += ":00"
    try: return int(dt.datetime.fromisoformat(s).timestamp())
    except ValueError: return None


el = [r for r in sub if cls.get(str(r["id"])) == "scheduled" and r["path"] in ("UMA MOOV2 direct", "UMA MOOV2 routed")]
excluded = collections.Counter(); cand = collections.defaultdict(list)
for r in el:
    m = s1[r["id"]]; ct, ed, gs = T(m["closedTime"]), T(m["endDate"]), T(m.get("gameStartTime"))
    if r["category"] == "sports" and gs:
        anchor, kind = gs, "pre-game"
    elif ed and ct and ct >= ed:
        anchor, kind = ed, "endDate"
    else:
        excluded[(r["category"], "endDate padded or missing")] += 1; continue
    cand[r["category"]].append((r, m, anchor, kind))
rng = random.Random(SEED)
sample = []
for c in sorted(cand):
    lst = sorted(cand[c], key=lambda x: x[0]["id"])
    sample += [(c, *x) for x in rng.sample(lst, min(CAP, len(lst)))]
res = []
for c, r, m, anchor, kind in sample:
    tok = json.loads(m["clobTokenIds"] or "[]")
    fin = json.loads(m.get("outcomePrices") or "[]")
    if not tok or len(fin) < 2: continue
    u = "https://clob.polymarket.com/prices-history?" + urllib.parse.urlencode({"market": tok[0], "startTs": anchor - 6 * 3600, "endTs": anchor, "fidelity": 1})
    h = []
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "settlement-tracker/0.1"}), timeout=40) as rr:
                h = json.load(rr).get("history", []); break
        except Exception:
            time.sleep(3 * (a + 1))
    time.sleep(0.25)
    def at(t):
        pts = [p for p in h if p["t"] <= t]
        return (pts[-1]["p"], t - pts[-1]["t"]) if pts else (None, None)
    p0, age0 = at(anchor); p1, age1 = at(anchor - 3600)
    known1h = None
    win = [p["p"] for p in h if anchor - 3600 <= p["t"] <= anchor]
    if win: known1h = any(x >= 0.99 or x <= 0.01 for x in win)
    res.append({"id": r["id"], "category": c, "kind": kind, "path": r["path"], "weight": r["weight"], "final_first": fin[0],
                "p_anchor": p0, "age_s": age0, "p_1h": p1, "age_1h_s": age1, "extreme_in_last_hour": known1h, "n_points": len(h)})


def wil(k, n, z=1.96):
    if not n: return None
    p = k / n; d = 1 + z * z / n; cc = p + z * z / (2 * n); hh = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round(100 * (cc - hh) / d, 1), round(100 * (cc + hh) / d, 1))


summary = {"eligible": len(el), "excluded": {f"{k[0]}|{k[1]}": v for k, v in excluded.items()}, "sampled": len(res),
           "no_price_history": sum(1 for x in res if x["p_anchor"] is None)}
for key in ("p_anchor", "p_1h"):
    for hi in (0.95, 0.90):
        fav = ups = 0; byc = collections.defaultdict(lambda: [0, 0])
        for x in res:
            p = x[key]
            if p is None or x["final_first"] not in ("0", "1"): continue
            side = "1" if p >= hi else "0" if p <= 1 - hi else None
            if not side: continue
            fav += 1; u = x["final_first"] != side; ups += u; byc[x["category"]][0] += 1; byc[x["category"]][1] += u
        summary[f"{key}@{hi}"] = {"favoured": fav, "upsets": ups, "rate_%": round(100 * ups / fav, 2) if fav else None, "ci95": wil(ups, fav), "by_cat": dict(byc)}
summary["A3_extreme_price_in_last_hour_share_%"] = round(100 * sum(1 for x in res if x["extreme_in_last_hour"]) / max(1, sum(1 for x in res if x["extreme_in_last_hour"] is not None)), 1)
summary["A3_by_kind"] = {k: round(100 * sum(1 for x in res if x["kind"] == k and x["extreme_in_last_hour"]) / max(1, sum(1 for x in res if x["kind"] == k and x["extreme_in_last_hour"] is not None)), 1) for k in ("pre-game", "endDate")}
json.dump({"summary": summary, "rows": res}, open(OUT, "w"), indent=1)
print(json.dumps(summary, indent=1))

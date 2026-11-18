#!/usr/bin/env python3
"""Map final disputed questions to Gamma markets (category, market type, validation vs outcomePrices).
Usage: python3 -I 09b_map_disputes_gamma.py disputes_final.json out.json"""
import json, sys, time, collections, urllib.request, urllib.parse
UA = {"User-Agent": "settlement-tracker/0.1", "Accept": "application/json"}
SPORTS = {"sports", "nfl", "nba", "mlb", "nhl", "soccer", "football", "tennis", "mma", "ufc", "boxing", "cricket", "golf", "f1", "esports", "ncaa"}
CRYPTO = {"crypto", "crypto-prices", "bitcoin", "ethereum", "xrp", "solana", "bnb", "hype", "dogecoin", "zcash"}
POLITICS = {"politics", "elections", "geopolitics", "world", "us-presidential-election", "trump"}
MACRO = {"economy", "fed", "finance", "business", "economic-policy", "inflation", "fed-rates", "stocks", "earnings"}
WEATHER = {"weather", "daily-temperature", "highest-temperature", "lowest-temperature", "climate"}

def category(t):
    if "up-or-down" in t: return "crypto_updown"
    if t & WEATHER: return "weather"
    if t & SPORTS: return "sports"
    if t & CRYPTO: return "crypto_other"
    if t & POLITICS: return "politics"
    if t & MACRO: return "macro"
    return "other"

def mtype(m):
    q = (m.get("question") or "").lower(); smt = (m.get("sportsMarketType") or "").lower()
    if any(k in smt for k in ("totals", "spreads", "player", "exact_score")) or " o/u " in f" {q} " or "spread" in q or "over/under" in q: return "line"
    return "multi" if m.get("negRisk") else "binary"

def get(params):
    u = "https://gamma-api.polymarket.com/markets?" + urllib.parse.urlencode(params)
    for a in range(5):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
        except Exception: time.sleep(3 * (a + 1))
    raise RuntimeError(u)

rows = json.load(open(sys.argv[1]))["rows"]
want = {r["qid"].lower() for r in rows}; found = {}
for closed in ("true", "false"):
    todo = sorted(want - set(found))
    for i in range(0, len(todo), 20):
        b = todo[i:i + 20]
        for m in get([("question_ids", x) for x in b] + [("closed", closed), ("include_tag", "true"), ("limit", "100")]):
            k = (m.get("questionID") or "").lower()
            if k in want and k not in found: found[k] = m
        time.sleep(0.2)
WIN = {"1000000000000000000": ["1", "0"], "0": ["0", "1"], "500000000000000000": ["0.5", "0.5"]}
cat = collections.Counter(); cat_changed = collections.Counter(); mt = collections.Counter(); mt_changed = collections.Counter()
val = collections.Counter(); out = []
for r in rows:
    m = found.get(r["qid"].lower())
    c = category({t.get("slug") for t in (m.get("tags") or [])}) if m else "unmapped"
    t = mtype(m) if m else "unmapped"
    settled = r["final"] is not None
    cat[(r["path"], c)] += 1; mt[(r["path"], t)] += 1
    if settled and r["final"] != r["first"]: cat_changed[(r["path"], c)] += 1
    if settled: mt_changed[(r["path"], t, "settled")] += 1
    if settled and r["final"] != r["first"]: mt_changed[(r["path"], t, "changed")] += 1
    if settled and m and m.get("closed"):
        try: op = json.loads(m.get("outcomePrices") or "[]")
        except Exception: op = []
        exp = WIN.get(r["final"])
        val[(r["path"], "match" if exp and [str(float(x)).rstrip("0").rstrip(".") for x in op] == [str(float(x)).rstrip("0").rstrip(".") for x in exp] else "mismatch")] += 1
    elif settled: val[(r["path"], "market_not_closed_in_gamma" if m else "unmapped")] += 1
    out.append(dict(r, category=c, mtype=t, gamma_closed=(m or {}).get("closed")))
res = {"mapped": len(found), "of": len(want),
       "category": {f"{a}|{b}": v for (a, b), v in sorted(cat.items())},
       "category_changed": {f"{a}|{b}": v for (a, b), v in sorted(cat_changed.items())},
       "mtype": {f"{a}|{b}": v for (a, b), v in sorted(mt.items())},
       "mtype_settled_changed": {f"{a}|{b}|{c}": v for (a, b, c), v in sorted(mt_changed.items())},
       "validation": {f"{a}|{b}": v for (a, b), v in sorted(val.items())}}
json.dump({"summary": res, "rows": out}, open(sys.argv[2], "w"), indent=1)
print(json.dumps(res, indent=1))

#!/usr/bin/env python3
"""Stage 2: stratified subsample of the S1 equal-probability sample + /v2/resolutions.
Strata = category x market type. Cap per cell; inclusion weight = (cell count in S1 / cell n drawn) * (N_est / S1 in-window count).
Usage: python3 -I stage2_subsample_resolutions.py <s1_sample.jsonl.gz> <out_dir>
"""
import collections, gzip, json, os, random, sys, time, urllib.request

S1, OUT = sys.argv[1], sys.argv[2]
SEED, CAP = 20261118, 300
ID_MAX, N_IDS = 7126067, 70000
UA = {"User-Agent": "settlement-tracker/0.1"}
os.makedirs(OUT, exist_ok=True)

SPORTS = {"sports", "soccer", "tennis", "esports", "basketball", "baseball", "mlb", "nba", "nfl", "cfb", "mls", "table-tennis", "games"}
CRYPTO = {"crypto", "crypto-prices", "bitcoin", "ethereum", "xrp", "solana", "bnb", "hype", "dogecoin", "zcash"}
POLITICS = {"politics", "elections", "geopolitics", "world", "us-presidential-election", "trump"}
MACRO = {"economy", "fed", "finance", "business", "economic-policy", "inflation", "fed-rates", "stocks", "earnings"}
WEATHER = {"weather", "daily-temperature", "highest-temperature", "lowest-temperature", "climate"}
RES = {"0x65070be91477460d8a7aeeb94ef92fe056c2f2a7": "UMA MOOV2 direct", "0x69c47de9d4d3dad79590d61b9e05918e03775f24": "UMA MOOV2 routed",
       "0x2f5e3684cb1f318ec51b00edba38d79ac2c0aa9d": "UMA OOV2 routed", "0x0a0a0a0a8b00c51b7d810501b03f230028c04a87": "V2 OracleAggregator",
       "0x157ce2d672854c848c9b79c49a8cc6cc89176a49": "UMA v3.1", "0x6a9d222616c90fca5754cd1333cfd9b7fb6a4f74": "UMA v2"}


def category(r):
    t = set(r["tags"])
    if "up-or-down" in t:
        return "crypto_updown"
    if t & WEATHER: return "weather"
    if t & SPORTS: return "sports"
    if t & CRYPTO: return "crypto_other"
    if t & POLITICS: return "politics"
    if t & MACRO: return "macro"
    return "other"


def mtype(r):
    q = (r["question"] or "").lower(); smt = (r.get("sportsMarketType") or "").lower()
    if any(k in smt for k in ("totals", "spreads", "player", "exact_score")) or " o/u " in f" {q} " or "spread" in q or "over/under" in q:
        return "line"
    if r.get("negRisk"):
        return "multi"
    return "binary"


rows = [json.loads(l) for l in gzip.open(S1, "rt")]
inw = [r for r in rows if "2025-11-17" <= str(r["closedTime"])[:10] < "2026-11-17" and r.get("conditionId")]
N_est = len(inw) / N_IDS * ID_MAX
for r in inw:
    r["category"], r["mtype"] = category(r), mtype(r)
    r["path"] = RES.get((r["resolvedBy"] or "").lower(), "no resolver" if not r["resolvedBy"] else "other")
cells = collections.defaultdict(list)
for r in inw:
    cells[(r["category"], r["mtype"])].append(r)
rng = random.Random(SEED)
sub = []
for k, lst in sorted(cells.items()):
    n = min(CAP, len(lst))
    pick = rng.sample(lst, n)
    w = (len(lst) / n) * (N_est / len(inw))
    for r in pick:
        r["weight"] = w; r["cell"] = f"{k[0]}|{k[1]}"; r["cell_s1_count"] = len(lst)
    sub += pick

# resolutions
res = {}
cids = [r["conditionId"] for r in sub]
for i in range(0, len(cids), 20):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request("https://data-api.polymarket.com/v2/resolutions?condition=" + ",".join(cids[i:i + 20]), headers=UA), timeout=60) as rr:
                for x in json.load(rr).get("data", []):
                    res[x["condition_id"].lower()] = x
            break
        except Exception:
            time.sleep(3 * (attempt + 1))
    time.sleep(0.25)
for r in sub:
    x = res.get(r["conditionId"].lower())
    r["res"] = {k: x.get(k) for k in ("status", "was_disputed", "extended_review", "proposed_price", "reproposed_price", "price", "last_update_timestamp", "resolution_source")} if x else None

with gzip.open(os.path.join(OUT, "s2_subsample.jsonl.gz"), "wt") as f:
    for r in sub:
        f.write(json.dumps(r, separators=(",", ":")) + "\n")
summary = {"N_est_window": round(N_est), "s1_in_window": len(inw), "subsample": len(sub), "with_resolution": sum(1 for r in sub if r["res"]),
           "cells": {f"{k[0]}|{k[1]}": [len(v), min(CAP, len(v))] for k, v in sorted(cells.items())},
           "path_share_s1": dict(collections.Counter(r["path"] for r in inw).most_common()),
           "category_share_s1": dict(collections.Counter(r["category"] for r in inw).most_common())}
json.dump(summary, open(os.path.join(OUT, "s2_summary.json"), "w"), indent=1)
print(json.dumps(summary, indent=1))

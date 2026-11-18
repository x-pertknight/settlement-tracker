#!/usr/bin/env python3
"""Stage 4d: Kalshi upset-rate inputs + series categories + closed-not-settled snapshot.
Resumable. Usage: python3 -I stage4d_kalshi_trades.py <out_dir> [max_seconds]
Per sampled market: last trade before close_time, and last trade at least 1 hour before close_time.
"""
import collections, datetime as dt, gzip, json, os, random, sys, time, urllib.error, urllib.parse, urllib.request

OUT = sys.argv[1]; MAX_S = int(sys.argv[2]) if len(sys.argv) > 2 else 540
K = "https://api.elections.kalshi.com/trade-api/v2"; UA = {"User-Agent": "settlement-tracker/0.1"}
PACE, CAP, SEED = 1.6, 60, 20261120
os.makedirs(OUT, exist_ok=True)
state_p = os.path.join(OUT, "state.json")
state = json.load(open(state_p)) if os.path.exists(state_p) else {"phase": "series", "i": 0, "calls": 0, "http429": 0, "series_cat": {}, "snapshot": None}


def save():
    tmp = state_p + ".tmp"; json.dump(state, open(tmp, "w")); os.replace(tmp, state_p)


def get(path, q=None):
    for attempt in range(8):
        time.sleep(PACE)
        try:
            u = K + path + ("?" + urllib.parse.urlencode(q) if q else "")
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
                state["calls"] += 1; return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                state["http429"] += 1; time.sleep(8 + 4 * attempt); continue
            if e.code == 404:
                return {}
            time.sleep(5 * (attempt + 1))
        except Exception:
            time.sleep(5 * (attempt + 1))
    return {}


def ts(s):
    return int(dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp())


rows = [json.loads(l) for l in gzip.open(sys.argv[3] if len(sys.argv) > 3 else "s4c/kalshi_minutes.jsonl.gz", "rt")]
vol = [r for r in rows if float(r.get("volume_fp") or 0) > 0]
known = {}
for l in gzip.open("s4b/kalshi_events.jsonl.gz", "rt"):
    e = json.loads(l)
    if e.get("series_ticker"): known[e["series_ticker"]] = e.get("category")
t0 = time.time()

if state["phase"] == "series":
    need = sorted({r["ticker"].split("-")[0] for r in vol} - set(known) - set(state["series_cat"]))
    for s in need:
        if time.time() - t0 > MAX_S: break
        j = get(f"/series/{s}")
        state["series_cat"][s] = (j.get("series") or {}).get("category") or "unknown"
        save()
    if not ({r["ticker"].split("-")[0] for r in vol} - set(known) - set(state["series_cat"])):
        state["phase"] = "trades"; save()

if state["phase"] == "trades":
    cat = {**known, **state["series_cat"]}
    by = collections.defaultdict(list)
    for r in vol:
        by[cat.get(r["ticker"].split("-")[0], "unknown")].append(r)
    rng = random.Random(SEED)
    sample = []
    for c in sorted(by):
        lst = sorted(by[c], key=lambda r: r["ticker"])
        pick = rng.sample(lst, min(CAP, len(lst)))
        for r in pick:
            r["category"] = c; r["weight_within_vol"] = len(lst) / len(pick)
        sample += pick
    TARGET = 25   # per category, reduced 18 Nov 05:15 UTC because Kalshi throttling (~4 markets/min)
    done = set(); per = collections.Counter()
    tp = os.path.join(OUT, "kalshi_trades.jsonl.gz")
    if os.path.exists(tp):
        for l in gzip.open(tp, "rt"):
            try:
                d = json.loads(l); done.add(d["ticker"]); per[d["category"]] += 1
            except Exception:
                pass
    # round-robin across categories so an early stop stays balanced
    queues = collections.defaultdict(list)
    for r in sample: queues[r["category"]].append(r)
    order = []
    for k in range(CAP):
        for c in sorted(queues):
            if k < len(queues[c]): order.append(queues[c][k])
    todo = [r for r in order if r["ticker"] not in done]
    with gzip.open(tp, "at") as f:
        for r in todo:
            if time.time() - t0 > MAX_S: break
            if per[r["category"]] >= TARGET: continue
            close = ts(r["close_time"])
            t_close = (get("/markets/trades", {"ticker": r["ticker"], "max_ts": close, "limit": 1}).get("trades") or [None])[0]
            t_1h = (get("/markets/trades", {"ticker": r["ticker"], "max_ts": close - 3600, "limit": 1}).get("trades") or [None])[0]
            out = {k: r.get(k) for k in ("ticker", "category", "weight_within_vol", "close_time", "settlement_ts", "result", "volume_fp", "can_close_early")}
            for name, t in (("last", t_close), ("last_1h", t_1h)):
                out[name + "_yes_price"] = float(t["yes_price_dollars"]) if t else None
                out[name + "_time"] = t["created_time"] if t else None
            f.write(json.dumps(out, separators=(",", ":")) + "\n"); f.flush()
            per[r["category"]] += 1; state["i"] = sum(per.values()); save()
        if all(per[c] >= min(TARGET, len(queues[c])) for c in queues):
            state["phase"] = "snapshot"; state["n_sample"] = len(sample); save()

if state["phase"] == "snapshot" and time.time() - t0 < MAX_S:
    snap, cur, pages = [], None, 0
    while pages < 30:
        q = {"status": "closed", "limit": 1000, "mve_filter": "exclude"}
        if cur: q["cursor"] = cur
        j = get("/markets", q); pages += 1
        snap += [{k: m.get(k) for k in ("ticker", "close_time", "open_interest_fp", "notional_value_dollars", "volume_fp", "result")} for m in j.get("markets", [])]
        cur = j.get("cursor")
        if not cur: break
    json.dump({"taken_at": dt.datetime.now(dt.timezone.utc).isoformat(), "complete": not cur, "markets": snap}, open(os.path.join(OUT, "kalshi_closed_snapshot.json"), "w"))
    state["phase"] = "done"; state["snapshot"] = {"n": len(snap), "complete": not cur}; save()

print(state["phase"].upper(), json.dumps({k: v for k, v in state.items() if k != "series_cat"}), "series mapped:", len(state["series_cat"]), f"{round(time.time()-t0)}s")

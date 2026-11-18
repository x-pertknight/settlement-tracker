#!/usr/bin/env python3
"""Stage 4a: Kalshi settled non-combo markets, cluster sample of random 60-second close windows, 18 Sep-17 Nov 2026 (live API only: /historical/markets has no close-time filter) in the study window.
Every market closing in the window has inclusion probability = n_hours / total_hours.
Live /markets for hours after the historical cutoff, /historical/markets before it. Resumable.
Usage: python3 -I stage4_kalshi_hours.py <out_dir> [max_seconds]
"""
import datetime as dt, gzip, json, os, random, sys, time, urllib.error, urllib.parse, urllib.request

OUT = sys.argv[1]; MAX_S = int(sys.argv[2]) if len(sys.argv) > 2 else 540
K = "https://api.elections.kalshi.com/trade-api/v2"; UA = {"User-Agent": "settlement-tracker/0.1"}
W0 = int(dt.datetime(2026, 9, 18, tzinfo=dt.timezone.utc).timestamp()); W1 = int(dt.datetime(2026, 11, 17, tzinfo=dt.timezone.utc).timestamp())
HIST_CUT = int(dt.datetime(2026, 9, 18, tzinfo=dt.timezone.utc).timestamp())   # market_settled_ts cutoff read 18 Nov 2026
SEED, N_HOURS, PACE = 20261119, 300, 1.6   # N_HOURS = number of random 60-second windows
TOTAL_H = (W1 - W0) // 60   # number of 60-second slots
hours = sorted(random.Random(SEED).sample(range(TOTAL_H), N_HOURS))
KEEP = ("ticker", "event_ticker", "market_type", "title", "yes_sub_title", "close_time", "expected_expiration_time", "occurrence_datetime",
        "expiration_time", "settlement_ts", "settlement_timer_seconds", "result", "status", "volume_fp", "open_interest_fp", "can_close_early",
        "last_price_dollars", "mve_collection_ticker", "strike_type")
os.makedirs(OUT, exist_ok=True)
state_p = os.path.join(OUT, "state.json")
state = json.load(open(state_p)) if os.path.exists(state_p) else {"i": 0, "cursor": None, "rows": 0, "calls": 0, "http429": 0, "hours": N_HOURS, "total_hours": TOTAL_H, "seed": SEED}


def get(path, q):
    for attempt in range(8):
        time.sleep(PACE)
        try:
            with urllib.request.urlopen(urllib.request.Request(K + path + "?" + urllib.parse.urlencode(q), headers=UA), timeout=60) as r:
                state["calls"] += 1
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                state["http429"] += 1; time.sleep(8 + 4 * attempt); continue
            if e.code >= 500:
                time.sleep(5 * (attempt + 1)); continue
            raise
        except Exception:
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("kalshi fetch failed")


t0 = time.time()
with gzip.open(os.path.join(OUT, "kalshi_minutes.jsonl.gz"), "at") as f:
    while state["i"] < N_HOURS and time.time() - t0 < MAX_S:
        h = hours[state["i"]]; a = W0 + h * 60; b = a + 60
        path = "/markets" if a >= HIST_CUT else "/historical/markets"
        q = {"limit": 1000, "min_close_ts": a, "max_close_ts": b - 1, "mve_filter": "exclude"}
        if path == "/markets":
            q["status"] = "settled"
        if state["cursor"]:
            q["cursor"] = state["cursor"]
        j = get(path, q)
        for m in j.get("markets", []):
            rec = {k: m.get(k) for k in KEEP}; rec["hour_index"] = h; rec["source"] = path
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
            state["rows"] += 1
        f.flush()
        state["cursor"] = j.get("cursor") or None
        if not state["cursor"]:
            state["i"] += 1
        tmp = state_p + ".tmp"; json.dump(state, open(tmp, "w")); os.replace(tmp, state_p)
print(("DONE " if state["i"] >= N_HOURS else "PARTIAL ") + json.dumps(state), f"{round(time.time()-t0)}s")

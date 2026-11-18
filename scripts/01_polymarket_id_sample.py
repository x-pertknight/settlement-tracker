#!/usr/bin/env python3
"""Stage 1b: equal-probability sample of Polymarket markets by random Gamma ID.
Every market ID in [1, ID_MAX] has the same inclusion probability, so stratum shares and the
total count in the window are estimated from the sample (no census).
Resumable by batch index. Usage: python3 -I stage1b_id_sample.py <out_dir> [max_seconds]
"""
import gzip, json, os, random, sys, time, urllib.error, urllib.parse, urllib.request

OUT = sys.argv[1]
MAX_S = int(sys.argv[2]) if len(sys.argv) > 2 else 540
SEED = 20261117
ID_MAX = 7126067          # latest closed market id observed 17 Nov 2026 23:30 UTC
N_IDS = 70000
BATCH = 100
UA = {"User-Agent": "settlement-tracker/0.1", "Accept": "application/json"}
os.makedirs(OUT, exist_ok=True)
rng = random.Random(SEED)
ids = rng.sample(range(1, ID_MAX + 1), N_IDS)
state_p = os.path.join(OUT, "state.json")
state = json.load(open(state_p)) if os.path.exists(state_p) else {"next_batch": 0, "returned": 0, "seed": SEED, "id_max": ID_MAX, "n_ids": N_IDS}


def fetch(batch):
    q = [("id", str(i)) for i in batch] + [("closed", "true"), ("include_tag", "true"), ("limit", str(BATCH))]
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request("https://gamma-api.polymarket.com/markets?" + urllib.parse.urlencode(q), headers=UA), timeout=90) as r:
                return json.load(r)
        except Exception:
            time.sleep(4 * (attempt + 1))
    raise RuntimeError("fetch failed")


def slim(m):
    ev = (m.get("events") or [{}])[0]
    return {"id": m.get("id"), "conditionId": m.get("conditionId"), "questionID": m.get("questionID"),
            "endDate": m.get("endDate"), "closedTime": m.get("closedTime"), "resolvedBy": m.get("resolvedBy"),
            "negRisk": m.get("negRisk"), "umaResolutionStatus": m.get("umaResolutionStatus"), "customLiveness": m.get("customLiveness"),
            "outcomes": m.get("outcomes"), "outcomePrices": m.get("outcomePrices"), "clobTokenIds": m.get("clobTokenIds"),
            "volumeNum": m.get("volumeNum"), "question": (m.get("question") or "")[:160], "slug": m.get("slug"),
            "tags": [t.get("slug") for t in (m.get("tags") or [])], "event_id": ev.get("id"), "event_slug": ev.get("slug"),
            "series": [s.get("slug") for s in (ev.get("series") or [])], "sportsMarketType": m.get("sportsMarketType"),
            "gameStartTime": m.get("gameStartTime")}


t0 = time.time()
nb = (N_IDS + BATCH - 1) // BATCH
with gzip.open(os.path.join(OUT, "sample.jsonl.gz"), "at") as f:
    while state["next_batch"] < nb and time.time() - t0 < MAX_S:
        b = state["next_batch"]
        ms = fetch(ids[b * BATCH:(b + 1) * BATCH])
        for m in ms:
            f.write(json.dumps(slim(m), separators=(",", ":")) + "\n")
        f.flush()
        state["returned"] += len(ms); state["next_batch"] = b + 1
        tmp = state_p + ".tmp"; json.dump(state, open(tmp, "w")); os.replace(tmp, state_p)
        time.sleep(0.15)
done = state["next_batch"] >= nb
print(("DONE " if done else "PARTIAL ") + json.dumps(state), f"{round(time.time()-t0)}s")

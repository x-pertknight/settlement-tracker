#!/usr/bin/env python3
"""Stage 2b: /v2/resolutions for every in-window market of the S1 equal-probability sample.
Resumable (batch index checkpoint). Usage: python3 -I stage2b_resolutions_s1.py <s1.jsonl.gz> <out_dir> [max_seconds]
"""
import gzip, json, os, sys, time, urllib.request

S1, OUT = sys.argv[1], sys.argv[2]
MAX_S = int(sys.argv[3]) if len(sys.argv) > 3 else 540
UA = {"User-Agent": "settlement-tracker/0.1"}
os.makedirs(OUT, exist_ok=True)
rows = [json.loads(l) for l in gzip.open(S1, "rt")]
cids = sorted({r["conditionId"].lower() for r in rows if r.get("conditionId") and "2025-11-17" <= str(r["closedTime"])[:10] < "2026-11-17"})
state_p = os.path.join(OUT, "state.json")
state = json.load(open(state_p)) if os.path.exists(state_p) else {"next": 0, "n_cids": len(cids), "rows": 0}
t0 = time.time()
with gzip.open(os.path.join(OUT, "s1_resolutions.jsonl.gz"), "at") as f:
    while state["next"] < len(cids) and time.time() - t0 < MAX_S:
        batch = cids[state["next"]:state["next"] + 20]
        for attempt in range(6):
            try:
                with urllib.request.urlopen(urllib.request.Request("https://data-api.polymarket.com/v2/resolutions?condition=" + ",".join(batch), headers=UA), timeout=60) as r:
                    data = json.load(r).get("data", [])
                break
            except Exception:
                time.sleep(3 * (attempt + 1))
        else:
            raise RuntimeError("resolutions fetch failed")
        for x in data:
            f.write(json.dumps({k: x.get(k) for k in ("condition_id", "question_id", "status", "was_disputed", "extended_review", "proposed_price",
                                                      "reproposed_price", "price", "last_update_timestamp", "resolution_source")}, separators=(",", ":")) + "\n")
        f.flush()
        state["next"] += len(batch); state["rows"] += len(data)
        tmp = state_p + ".tmp"; json.dump(state, open(tmp, "w")); os.replace(tmp, state_p)
        time.sleep(0.15)
print(("DONE " if state["next"] >= len(cids) else "PARTIAL ") + json.dumps(state), f"{round(time.time()-t0)}s")

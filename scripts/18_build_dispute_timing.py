#!/usr/bin/env python3
"""Build data/disputes_timing.csv: one row per disputed question in data/disputes_final.json, in the same order,
with the time of its first DisputePrice event and its Polymarket event (the match, for sports).

Inputs: <out_dir>/dispute_events.jsonl from scripts/17_fetch_dispute_times.py, data/disputes_final.json,
and the public Gamma API (market id -> event id, slug, title). Network for Gamma only. Standard library only.
No wallet addresses are written: the file has question IDs, blocks, log indexes, times and public titles.
Usage: python3 -I scripts/18_build_dispute_timing.py <out_dir> data/disputes_timing.csv
"""
import collections, csv, datetime as dt, json, os, sys, time, urllib.parse, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GAMMA = "https://gamma-api.polymarket.com/markets"
UA = {"User-Agent": "settlement-tracker/0.1", "Accept": "application/json"}
COLS = ["qid", "path", "first", "final", "how", "mtype", "first_dispute_utc", "first_dispute_unix", "first_dispute_block",
        "first_dispute_log_index", "dispute_events", "market_title", "polymarket_market_id", "gamma_event_id",
        "gamma_event_slug", "gamma_event_title"]


def gamma_events(ids):
    """Market id -> (event id, slug, title), asking for open and closed markets in batches of 50."""
    out, ids = {}, sorted(ids)
    for i in range(0, len(ids), 50):
        for closed in ("true", "false"):
            q = urllib.parse.urlencode([("id", x) for x in ids[i:i + 50]] + [("closed", closed), ("limit", 100)])
            with urllib.request.urlopen(urllib.request.Request(f"{GAMMA}?{q}", headers=UA), timeout=60) as r:
                for m in json.load(r):
                    e = (m.get("events") or [{}])[0]
                    out[str(m["id"])] = (e.get("id"), e.get("slug"), e.get("title"))
            time.sleep(0.2)
    return out


def main():
    src = os.path.join(sys.argv[1], "dispute_events.jsonl")
    lines = open(src).read().splitlines()
    events = collections.defaultdict(list)
    for line in lines[1:]:
        e = json.loads(line); events[e["qid"]].append(e)
    rows = json.load(open(os.path.join(ROOT, "data", "disputes_final.json")))["rows"]
    mids = {e["market_id"] for evs in events.values() for e in evs if e["market_id"]}
    gm = gamma_events(mids)
    with open(sys.argv[2], "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(COLS)
        for r in rows:
            evs = events[r["qid"]]
            e0 = min(evs, key=lambda e: (e["time"], e["block"], e["log_index"]))
            mid = next((e["market_id"] for e in evs if e["market_id"]), "")
            g = gm.get(mid, (None, None, None))
            w.writerow([r["qid"], r["path"], r["first"], "" if r["final"] is None else r["final"], r["how"], r.get("mtype", ""),
                        dt.datetime.fromtimestamp(e0["time"], dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), e0["time"],
                        e0["block"], e0["log_index"], len(evs), e0["title"], mid, g[0] or "", g[1] or "", g[2] or ""])
    meta = json.loads(lines[0])
    print(json.dumps(dict(meta, rows=len(rows), gamma_markets_found=len(gm), gamma_markets_asked=len(mids))))


if __name__ == "__main__":
    main()

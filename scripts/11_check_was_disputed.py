#!/usr/bin/env python3
"""How often does data-api /v2/resolutions `was_disputed` flag questions disputed on-chain?
Input: disputes_mapped.json (direct-path questions map to Gamma by questionID). Usage: python3 -I 11_check_was_disputed.py disputes_mapped.json out.json"""
import json, sys, time, collections, urllib.request, urllib.parse
UA = {"User-Agent": "settlement-tracker/0.1", "Accept": "application/json"}
def get(u):
    for a in range(5):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
        except Exception: time.sleep(3 * (a + 1))
    raise RuntimeError(u)
rows = [r for r in json.load(open(sys.argv[1]))["rows"] if r["path"] == "MOOV2 direct" and r["category"] != "unmapped"]
qids = [r["qid"].lower() for r in rows]; cid = {}
for closed in ("true", "false"):
    todo = [q for q in qids if q not in cid]
    for i in range(0, len(todo), 20):
        for m in get("https://gamma-api.polymarket.com/markets?" + urllib.parse.urlencode([("question_ids", x) for x in todo[i:i+20]] + [("closed", closed), ("limit", "100")])):
            k = (m.get("questionID") or "").lower()
            if k in qids and k not in cid and m.get("conditionId"): cid[k] = m["conditionId"].lower()
        time.sleep(0.2)
cids = sorted(set(cid.values())); res = {}
for i in range(0, len(cids), 20):
    for x in get("https://data-api.polymarket.com/v2/resolutions?condition=" + ",".join(cids[i:i+20])).get("data", []):
        res[(x.get("condition_id") or "").lower()] = x
    time.sleep(0.2)
c = collections.Counter()
for q in qids:
    x = res.get(cid.get(q, ""))
    c["no_row" if x is None else ("flag_true" if x.get("was_disputed") else "flag_false")] += 1
out = {"direct_disputed_mapped": len(qids), "with_conditionId": len(cid), "was_disputed": dict(c)}
json.dump(out, open(sys.argv[2], "w"), indent=1); print(out)

#!/usr/bin/env python3
"""B3 check: is data-api last_update_timestamp the on-chain settlement time?
Public reads only. On-chain settlement = block time of the ConditionalTokens
ConditionResolution event for the market's conditionId."""
import collections, datetime as dt, json, statistics, sys, time, urllib.error, urllib.parse, urllib.request

UA = {"User-Agent": "settlement-tracker-gates/0.1"}
RPC = "https://polygon-bor-rpc.publicnode.com"
CTF = "0x4d97dcd97ec945f40cf65f87097ace5ea0476045"
COND_RES = "0xb44d84d3289691f71497564b85d4233648d9dbae8cbdbb4329f301c3a0185894"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
OUT = sys.argv[2] if len(sys.argv) > 2 else "raw/b3_check.json"


def get(u):
    time.sleep(0.3)
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
        return json.load(r)


def rpc(m, p):
    time.sleep(0.45)
    req = urllib.request.Request(RPC, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(),
                                 headers={**UA, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": e.read()[:150].decode(errors="ignore")}
    except Exception as e:
        return {"error": str(e)[:150]}


def to_ts(v):
    s = str(v)
    if s.isdigit():
        return int(s)
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def block_ts(bn_hex):
    b = rpc("eth_getBlockByNumber", [bn_hex, False]).get("result")
    return int(b["timestamp"], 16) if b else None


# 1. latest closed markets
markets = []
for off in range(0, N, 100):
    markets += get(f"https://gamma-api.polymarket.com/markets?closed=true&order=closedTime&ascending=false&limit=100&offset={off}")
markets = markets[:N]
by_cid = {m["conditionId"].lower(): m for m in markets if m.get("conditionId")}

# 2. resolutions
rows = []
cids = list(by_cid)
for i in range(0, len(cids), 20):
    rows += get("https://data-api.polymarket.com/v2/resolutions?condition=" + ",".join(cids[i:i + 20])).get("data", [])

head = int(rpc("eth_blockNumber", [])["result"], 16)
now = time.time()
results = []
for r in rows:
    cid = r["condition_id"].lower()
    m = by_cid.get(cid, {})
    lut = to_ts(r["last_update_timestamp"]) if r.get("last_update_timestamp") else None
    rec = {"condition_id": cid, "resolvedBy": m.get("resolvedBy"), "customLiveness": m.get("customLiveness"),
           "was_disputed": r.get("was_disputed"), "lut": lut, "lut_format": "epoch" if str(r.get("last_update_timestamp")).isdigit() else "iso",
           "found_via": None, "settle_ts": None, "diff_s": None}
    # a) is the API tx the settlement tx?
    rc = rpc("eth_getTransactionReceipt", [r["transaction_hash"]]).get("result") if r.get("transaction_hash") else None
    if rc:
        hit = [l for l in rc["logs"] if l["address"].lower() == CTF and l["topics"][0] == COND_RES
               and len(l["topics"]) > 3 and l["topics"][3].lower() == (r.get("question_id") or "").lower()]
        hit = hit or [l for l in rc["logs"] if l["address"].lower() == CTF and l["topics"][0] == COND_RES]
        if hit:
            rec["found_via"] = "api_tx"
            rec["settle_ts"] = block_ts(rc["blockNumber"])
    # b) otherwise scan blocks around lut for ConditionResolution of this condition
    if rec["settle_ts"] is None and lut:
        est = head - int((now - lut) / 2.1)
        for start in range(est - 60, est + 60, 10):
            x = rpc("eth_getLogs", [{"fromBlock": hex(start), "toBlock": hex(start + 9), "address": CTF,
                                     "topics": [COND_RES, cid]}])
            if x.get("result"):
                rec["found_via"] = "scan"
                rec["settle_ts"] = block_ts(x["result"][0]["blockNumber"])
                srec = rpc("eth_getTransactionReceipt", [x["result"][0]["transactionHash"]]).get("result") or {}
                rec["settle_emitters"] = sorted({l["address"].lower() for l in srec.get("logs", [])})
                break
            if "error" in x and "range" not in str(x["error"]):
                rec["scan_error"] = str(x["error"])[:100]
                break
    if rec["settle_ts"] and lut:
        rec["diff_s"] = rec["settle_ts"] - lut
    results.append(rec)

DOC = {"0xcb1822859cef82cd2eb4e6276c7916e692995130": "UMA (documented, adapter v1)",
       "0x6a9d222616c90fca5754cd1333cfd9b7fb6a4f74": "UMA (documented, adapter v2)",
       "0x157ce2d672854c848c9b79c49a8cc6cc89176a49": "UMA (documented, adapter v3.1)",
       "0x000012e0009c84078c4924fba808a41b9f67527f": "UMA (documented, V2 OOReporter)",
       "0xc12ec12e0000326890ca5560def5eb5c22b16814": "Chainlink (documented, V2 reporter)",
       "0x8ef9d6d668798b1f363b305d916f30739d2b0419": "Single key (documented, V2 EOAReporter)"}
UMA_OO = {"0x2c0367a9db231ddebd88a94b4f6461a6e47c58b1", "0xee3afe347d5c74317041e2618c49534daf887c24"}
for x in results:
    rb = (x["resolvedBy"] or "").lower()
    em = set(x.get("settle_emitters") or [])
    if rb in DOC:
        x["path"] = DOC[rb]
    elif em & UMA_OO:
        x["path"] = "UMA (inferred: oracle event in settlement tx)"
    elif em & set(DOC):
        x["path"] = DOC[sorted(em & set(DOC))[0]].replace("documented", "inferred from settlement tx")
    else:
        x["path"] = "unclassified"
json.dump(results, open(OUT, "w"), indent=1)
pc = collections.Counter(x["path"] for x in results)
print("PATHS:", dict(pc))
for p in pc:
    d = [x["diff_s"] for x in results if x["path"] == p and x["diff_s"] is not None]
    if d:
        print(f"  {p}: n={len(d)} median={statistics.median(d)} over1h={sum(1 for v in d if abs(v) > 3600)} max={max(d, key=abs)}")
print("resolvedBy x path:", dict(collections.Counter((x["resolvedBy"], x["path"]) for x in results)))
print("unclassified emitters sample:", [x.get("settle_emitters") for x in results if x["path"] == "unclassified"][:2])
found = [x for x in results if x["diff_s"] is not None]
diffs = [x["diff_s"] for x in found]
print("markets", len(markets), "resolution rows", len(rows))
print("on-chain settlement found:", len(found), "of", len(rows), collections.Counter(x["found_via"] for x in results))
print("lut format:", dict(collections.Counter(x["lut_format"] for x in results)))
if diffs:
    print("settle_ts - lut (s): exact 0:", sum(1 for d in diffs if d == 0), "| within 60s:", sum(1 for d in diffs if abs(d) <= 60),
          "| median", statistics.median(diffs), "| min", min(diffs), "| max", max(diffs))
print("by resolvedBy:", {k: [sum(1 for x in found if x["resolvedBy"] == k and abs(x["diff_s"]) <= 60),
                             sum(1 for x in results if x["resolvedBy"] == k)] for k in set(x["resolvedBy"] for x in results)})
print("disputed in sample:", sum(1 for x in results if x["was_disputed"]))
print("customLiveness set:", sum(1 for x in results if x["customLiveness"] not in (None, "", 0, "0")), "values",
      dict(collections.Counter(str(x["customLiveness"]) for x in results).most_common(5)))
print("not found examples:", [ {k: x[k] for k in ("resolvedBy", "lut_format", "found_via")} | {"err": x.get("scan_error")} for x in results if x["settle_ts"] is None][:4])

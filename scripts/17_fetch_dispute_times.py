#!/usr/bin/env python3
"""Refetch the time of every UMA DisputePrice event on the three Polymarket adapters, 11 Oct to 17 Nov 2026.

Public Polygon RPC, read only, standard library only. Writes one JSON line per DisputePrice event to
<out_dir>/dispute_events.jsonl with: oracle, requester (an adapter contract), questionID, block, log index,
exact block time, the block time as the census script estimated it (linear inside 5,000 block windows from the
window start, as in scripts/04_uma_onchain_census.py), request timestamp, and the market title and Polymarket
market id read from the ancillary data. Proposer and disputer (indexed topics), the tx hash and the
initializer address inside the ancillary data are NOT written.
Usage: python3 -I scripts/17_fetch_dispute_times.py <out_dir>
"""
import datetime as dt, json, os, re, sys, time, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script folder from the path
from keccak import keccak256

RPC = os.environ.get("ST_RPC", "https://polygon.gateway.tenderly.co")  # accepts wide eth_getLogs ranges
UA = {"User-Agent": "settlement-tracker/0.1", "Content-Type": "application/json"}
START = int(dt.datetime(2026, 10, 11, tzinfo=dt.timezone.utc).timestamp())
CUTOFF = int(dt.datetime(2026, 11, 17, tzinfo=dt.timezone.utc).timestamp())
ORACLES = {"0x2c0367a9db231ddebd88a94b4f6461a6e47c58b1": "MOOV2", "0xee3afe347d5c74317041e2618c49534daf887c24": "OOV2"}
ADAPTERS = ["0x65070be91477460d8a7aeeb94ef92fe056c2f2a7", "0x69c47de9d4d3dad79590d61b9e05918e03775f24",
            "0x2f5e3684cb1f318ec51b00edba38d79ac2c0aa9d"]
DISPUTE = "0x5165909c3d1c01c5d1e121ac6f6d01dda1ba24bc9e1f975b5a375339c15be7f3"
CENSUS_WIN = 5000   # window size of scripts/04_uma_onchain_census.py
STEP = 20000
_ts = {}


def rpc(method, params, tries=6):
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(), UA)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.load(r)
            if "result" in j:
                return j["result"]
            last = j.get("error")
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last = str(e)[:200]
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"rpc {method} failed: {last}")


def bts(n):
    """Exact block timestamp, cached."""
    if n not in _ts:
        _ts[n] = int(rpc("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)
    return _ts[n]


def block_at(ts, head):
    """First block with timestamp >= ts (binary search)."""
    lo, hi = 1, head
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if bts(mid) < ts: lo = mid
        else: hi = mid
    return hi


def census_time(blk, b0, b1):
    """The census estimate: exact times at the window ends, linear in between."""
    a = b0 + (blk - b0) // CENSUS_WIN * CENSUS_WIN
    b = min(b1 - 1, a + CENSUS_WIN - 1)
    ta, tb = bts(a), bts(b)
    return ta + round((tb - ta) * (blk - a) / max(1, b - a))


def decode(log, b0, b1):
    d = bytes.fromhex(log["data"][2:])
    off = int.from_bytes(d[64:96], "big"); ln = int.from_bytes(d[off:off + 32], "big")
    anc = d[off + 32:off + 32 + ln]
    text = anc.decode("utf-8", errors="replace")
    title = re.search(r"title:\s*(.*?),\s*description:", text, re.S)
    mid = re.search(r"market_id:\s*(\d+)", text)
    blk = int(log["blockNumber"], 16)
    return {"oracle": ORACLES[log["address"].lower()], "requester": "0x" + log["topics"][1][-40:],
            "qid": keccak256(anc), "block": blk, "log_index": int(log["logIndex"], 16),
            "time": bts(blk), "time_census": census_time(blk, b0, b1),
            "request_ts": int.from_bytes(d[32:64], "big"),
            "title": title.group(1).strip() if title else None, "market_id": mid.group(1) if mid else None}


def main():
    out_dir = sys.argv[1]; os.makedirs(out_dir, exist_ok=True)
    head = int(rpc("eth_blockNumber", []), 16)
    b0, b1 = block_at(START, head), block_at(CUTOFF, head)
    topics = [DISPUTE, ["0x" + "0" * 24 + a[2:] for a in ADAPTERS]]
    rows = []
    for a in range(b0, b1, STEP):
        b = min(b1 - 1, a + STEP - 1)   # the census reads up to end_block - 1
        logs = rpc("eth_getLogs", [{"fromBlock": hex(a), "toBlock": hex(b), "address": list(ORACLES), "topics": topics}])
        rows += [decode(l, b0, b1) for l in logs]
        print(f"blocks {a} to {b}: {len(logs)} disputes", file=sys.stderr)
    meta = {"fetched_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rpc": RPC,
            "start_block": b0, "end_block_exclusive": b1, "events": len(rows)}
    with open(os.path.join(out_dir, "dispute_events.jsonl"), "w") as f:
        f.write(json.dumps(meta) + "\n")
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()

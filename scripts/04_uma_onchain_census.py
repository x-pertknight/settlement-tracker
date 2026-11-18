#!/usr/bin/env python3
"""Stage 2d: on-chain census of UMA ProposePrice / DisputePrice / Settle on Polygon (MOOV2 + OOV2),
from 11 Oct 2026 to the study cutoff (17 Nov), the free-RPC log window. Public RPC, read-only. Resumable by window.
Block times: exact anchors every window (eth_getBlockByNumber at window start), linear interpolation inside.
Usage: python3 -I stage2d_onchain_census.py <out_dir> [max_seconds]
"""
import datetime as dt, gzip, json, os, sys, time, urllib.error, urllib.request
from Crypto.Hash import keccak

OUT = sys.argv[1]; MAX_S = int(sys.argv[2]) if len(sys.argv) > 2 else 540
RPC = "https://polygon-bor-rpc.publicnode.com"; UA = {"User-Agent": "settlement-tracker/0.1", "Content-Type": "application/json"}
CUTOFF = int(dt.datetime(2026, 11, 17, tzinfo=dt.timezone.utc).timestamp()); START = int(dt.datetime(2026, 10, 11, tzinfo=dt.timezone.utc).timestamp())  # free-RPC log window starts ~9 Oct (archive boundary), margin kept
OOS = {"0x2c0367a9db231ddebd88a94b4f6461a6e47c58b1": "MOOV2", "0xee3afe347d5c74317041e2618c49534daf887c24": "OOV2"}
T = {"0x6e51dd00371aabffa82cd401592f76ed51e98a9ea4b58751c70463a2c78b5ca1": "P",
     "0x5165909c3d1c01c5d1e121ac6f6d01dda1ba24bc9e1f975b5a375339c15be7f3": "D",
     "0x3f384afb4bd9f0aef0298c80399950011420eb33b0e1a750b20966270247b9a0": "S"}
WIN = 5000
os.makedirs(OUT, exist_ok=True)


def rpc(m, p, tries=6):
    last = None
    for attempt in range(tries):
        time.sleep(0.25)
        req = urllib.request.Request(RPC, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(), headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.load(r)
            if "result" in j:
                return j["result"]
            last = j.get("error")
        except urllib.error.HTTPError as e:
            last = e.read()[:200].decode(errors="ignore")
        except Exception as e:
            last = str(e)[:200]
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"rpc {m} failed: {last}")


def bts(n):
    return int(rpc("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)


def block_at(ts, head, htime):
    lo, hi = max(1, head - int((htime - ts) / 1.5)), head - int((htime - ts) / 2.8)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if bts(mid) < ts: lo = mid
        else: hi = mid
    return hi


def kh(b):
    h = keccak.new(digest_bits=256); h.update(b); return "0x" + h.hexdigest()


state_p = os.path.join(OUT, "state.json")
if os.path.exists(state_p):
    state = json.load(open(state_p))
else:
    head = int(rpc("eth_blockNumber", []), 16); htime = bts(head)
    b0, b1 = block_at(START, head, htime), block_at(CUTOFF, head, htime)
    state = {"start_block": b0, "end_block": b1, "next": b0, "events": 0, "part": 0}
    json.dump(state, open(state_p, "w"))
t0 = time.time()
with gzip.open(os.path.join(OUT, f"events-{state['part']:03d}.jsonl.gz"), "wt") as f:
    while state["next"] < state["end_block"] and time.time() - t0 < MAX_S:
        a = state["next"]; logs = None
        for w in (WIN, 2000, 1000, 400):
            b = min(state["end_block"] - 1, a + w - 1)
            try:
                logs = rpc("eth_getLogs", [{"fromBlock": hex(a), "toBlock": hex(b), "address": list(OOS), "topics": [list(T)]}], tries=2)
                break
            except RuntimeError as e:
                err = str(e)
        if logs is None:
            raise RuntimeError(f"window {a} failed at all sizes: {err}")
        ta, tb = bts(a), bts(b)
        for l in logs:
            ev = T[l["topics"][0]]; blk = int(l["blockNumber"], 16)
            d = bytes.fromhex(l["data"][2:])
            req_ts = int.from_bytes(d[32:64], "big"); off = int.from_bytes(d[64:96], "big")
            ln = int.from_bytes(d[off:off + 32], "big"); anc = d[off + 32:off + 32 + ln]
            price = int.from_bytes(d[96:128], "big", signed=True)
            rec = {"e": ev, "oo": OOS[l["address"].lower()], "req": "0x" + l["topics"][1][-40:], "rts": req_ts, "qid": kh(anc),
                   "b": blk, "t": ta + round((tb - ta) * (blk - a) / max(1, b - a)), "px": str(price), "tx": l["transactionHash"]}
            if ev == "P":
                rec["exp"] = int.from_bytes(d[128:160], "big")
            if ev == "S":
                rec["payout"] = str(int.from_bytes(d[128:160], "big"))
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
        state["events"] += len(logs); state["next"] = b + 1
        tmp = state_p + ".tmp"; json.dump(state, open(tmp, "w")); os.replace(tmp, state_p)
state["part"] += 1
tmp = state_p + ".tmp"; json.dump(state, open(tmp, "w")); os.replace(tmp, state_p)
done = state["next"] >= state["end_block"]
pct = round(100 * (state["next"] - state["start_block"]) / (state["end_block"] - state["start_block"]), 1)
print(("DONE " if done else "PARTIAL ") + json.dumps(state), f"{pct}% {round(time.time()-t0)}s")

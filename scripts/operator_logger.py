#!/usr/bin/env python3
"""Forward logger for Polymarket resolution admin events (3 UmaCtfAdapters + 2 NegRiskOperators) and UMA disputes (2 oracles, Polymarket adapters only) (settlement tracker, forward series).

Reads new events since the last checkpoint from the five mapped resolution contracts
via a public Polygon RPC (read-only eth_getLogs / eth_getBlockByNumber, no keys).
Python standard library only.

Usage:  python3 operator_logger.py [data_dir]
Run it on a schedule (hourly is enough: public RPC accepts ~2,000-block ranges near head).

Writes:
  <data_dir>/state.json                     last processed block
  <data_dir>/events-YYYY-MM.jsonl           one line per rare event, and every event on the 1h-delay operator
  <data_dir>/counts-YYYY-MM.jsonl           per-run counts of high-volume events on the 0-delay operator
  <data_dir>/gaps.jsonl                     block ranges that could not be read (never silently skipped)
  <data_dir>/errors.jsonl                   runs that stopped early (RPC head unreachable, unreadable state)

Re-reads after a gap are safe: events are de-duplicated on (tx, log_index) across all runs.
Note: counts-*.jsonl rows can overlap after a rewind; each row carries from_block/to_block,
so downstream must de-duplicate counts by block range.
"""
import datetime as dt, glob, json, os, sys, time, urllib.error, urllib.request

RPC = "https://polygon-bor-rpc.publicnode.com"
UA = {"User-Agent": "settlement-tracker/0.1", "Content-Type": "application/json"}
OPERATORS = {
 "0x661992aebf6becf7ba5abb66f6b0bf62aa7a2e93": {
  "kind": "operator",
  "route": "MOOV2 routed (operator, DELAY_PERIOD 0)",
  "keep_all": False
 },
 "0x71523d0f655b41e805cec45b17163f528b59b820": {
  "kind": "operator",
  "route": "OOV2 routed (operator, DELAY_PERIOD 1h)",
  "keep_all": True
 },
 "0x65070be91477460d8a7aeeb94ef92fe056c2f2a7": {
  "kind": "adapter",
  "route": "MOOV2 direct (adapter, SAFETY_PERIOD 1h)",
  "keep_all": False
 },
 "0x69c47de9d4d3dad79590d61b9e05918e03775f24": {
  "kind": "adapter",
  "route": "MOOV2 routed (adapter, SAFETY_PERIOD 1h)",
  "keep_all": False
 },
 "0x2f5e3684cb1f318ec51b00edba38d79ac2c0aa9d": {
  "kind": "adapter",
  "route": "OOV2 routed (adapter, EMERGENCY_SAFETY_PERIOD 2d)",
  "keep_all": True
 },
 # UMA oracles: only ProposePrice/DisputePrice/Settle requested by the three Polymarket adapters (topic1 filter)
 "0x2c0367a9db231ddebd88a94b4f6461a6e47c58b1": {
  "kind": "oracle",
  "route": "UMA ManagedOptimisticOracleV2",
  "keep_all": False,
  "topics_filter": [["0x6e51dd00371aabffa82cd401592f76ed51e98a9ea4b58751c70463a2c78b5ca1", "0x5165909c3d1c01c5d1e121ac6f6d01dda1ba24bc9e1f975b5a375339c15be7f3", "0x3f384afb4bd9f0aef0298c80399950011420eb33b0e1a750b20966270247b9a0"], ["0x00000000000000000000000065070be91477460d8a7aeeb94ef92fe056c2f2a7", "0x00000000000000000000000069c47de9d4d3dad79590d61b9e05918e03775f24", "0x0000000000000000000000002f5e3684cb1f318ec51b00edba38d79ac2c0aa9d"]]
 },
 "0xee3afe347d5c74317041e2618c49534daf887c24": {
  "kind": "oracle",
  "route": "UMA OptimisticOracleV2",
  "keep_all": False,
  "topics_filter": [["0x6e51dd00371aabffa82cd401592f76ed51e98a9ea4b58751c70463a2c78b5ca1", "0x5165909c3d1c01c5d1e121ac6f6d01dda1ba24bc9e1f975b5a375339c15be7f3", "0x3f384afb4bd9f0aef0298c80399950011420eb33b0e1a750b20966270247b9a0"], ["0x00000000000000000000000065070be91477460d8a7aeeb94ef92fe056c2f2a7", "0x00000000000000000000000069c47de9d4d3dad79590d61b9e05918e03775f24", "0x0000000000000000000000002f5e3684cb1f318ec51b00edba38d79ac2c0aa9d"]]
 }
}
# keccak256 of the event signatures in the verified NegRiskOperator source (validated against live logs 17 Nov 2026)
TOPICS = {
 "operator": {
  "QuestionFlagged": "0x2435a0347185933b12027c6f394a5fd9c03646dba233e956f50658719dfc0b35",
  "QuestionUnflagged": "0x052435bc04fc49113a7bfd9198a92c0852ca622a621800f6da66d4b29b786c05",
  "QuestionEmergencyResolved": "0xd1aea2ca9d3458614d11a93a203dd9fabbd3576aeb841422c46e235637333cb9",
  "QuestionReported": "0x504306b41b2531b3fd2bc5e1b32dc1fc87501906cfc63c1180e3873af20f0eae",
  "QuestionResolved": "0x5c3937ed929cd157b73b417381d743daf6e1ef65999e3ccb5dd64bc3247e28d6",
  "NewAdmin": "0xf9ffabca9c8276e99321725bcb43fb076a6c66a54b7f21c4e8146d8519b417dc",
  "RemovedAdmin": "0x787a2e12f4a55b658b8f573c32432ee11a5e8b51677d1e1e937aaf6a0bb5776e",
  "QuestionPrepared": "0xcdc45423ec79c60a3fe3de57272e598d71a4ec88822e822ac8e134184a8435aa",
  "MarketPrepared": "0x8138c0666fe0f752ff38486f542284f127aef02642c9c8db716ee1088839eeb0"
 },
 "oracle": {
  "ProposePrice": "0x6e51dd00371aabffa82cd401592f76ed51e98a9ea4b58751c70463a2c78b5ca1",
  "DisputePrice": "0x5165909c3d1c01c5d1e121ac6f6d01dda1ba24bc9e1f975b5a375339c15be7f3",
  "Settle": "0x3f384afb4bd9f0aef0298c80399950011420eb33b0e1a750b20966270247b9a0"
 },
 "adapter": {
  "QuestionInitialized": "0xeee0897acd6893adcaf2ba5158191b3601098ab6bece35c5d57874340b64c5b7",
  "QuestionPaused": "0x6ded7250a9d5f79aef5add44600fc20a74a0af6f4730baa4fc4ab87bf484b812",
  "QuestionUnpaused": "0x92d28918c5574e7fc0f4f948c39502682c81cfb4089b07b83f95b3264e5e5e06",
  "QuestionFlagged": "0x2435a0347185933b12027c6f394a5fd9c03646dba233e956f50658719dfc0b35",
  "QuestionUnflagged": "0x052435bc04fc49113a7bfd9198a92c0852ca622a621800f6da66d4b29b786c05",
  "QuestionReset": "0x7981b5832932948db4e32a4a16a0f44b2ce7ff088574afb9364b313f70f82e8f",
  "QuestionResolved": "0x566c3fbdd12dd86bb341787f6d531f79fd7ad4ce7e3ae2d15ac0ca1b601af9df",
  "QuestionManuallyResolved": "0x5909815fe7fe0a550d5fcb95fbf33821b580521d3c97089c6ce12808d1cd0566",
  "NewAdmin": "0xf9ffabca9c8276e99321725bcb43fb076a6c66a54b7f21c4e8146d8519b417dc",
  "RemovedAdmin": "0x787a2e12f4a55b658b8f573c32432ee11a5e8b51677d1e1e937aaf6a0bb5776e",
  "AncillaryDataUpdated": "0x0059e11815211969c0c4aaf3f498b52b6c2f2d14f286275d0862d70de22a836b",
  "QuestionEmergencyResolved": "0x6edb5841a476c9c29c34a652d1a44f785fe71a6157a3da9a6a6a589a1bd2945a"
 }
}
NAME = {kind: {v: k for k, v in t.items()} for kind, t in TOPICS.items()}
RARE = {"QuestionFlagged", "QuestionUnflagged", "QuestionEmergencyResolved", "QuestionManuallyResolved", "QuestionPaused",
        "QuestionUnpaused", "QuestionReset", "NewAdmin", "RemovedAdmin", "AncillaryDataUpdated", "DisputePrice"}
FIRST_RUN_LOOKBACK = 1500   # blocks
CHUNK = 2000                # blocks per eth_getLogs near head
SMALL = 10                  # fallback chunk when the node refuses wide ranges
MAX_SMALL_CALLS = 3000      # beyond this, record a gap instead of hammering the node
PACE = 0.35


def rpc(method, params):
    time.sleep(PACE)
    req = urllib.request.Request(RPC, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(), headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": e.read()[:200].decode(errors="ignore")}
    except Exception as e:
        return {"error": str(e)[:200]}


_bts = {}
def block_ts(n):
    if n not in _bts:
        r = rpc("eth_getBlockByNumber", [hex(n), False]).get("result")
        _bts[n] = int(r["timestamp"], 16) if r else None
    return _bts[n]


def get_logs(addr, a, b, small_budget, topics=None):
    """Return (logs, gaps, small_calls_used). topics: optional eth_getLogs topic filter."""
    logs, gaps, used = [], [], 0
    s = a
    while s <= b:
        e = min(b, s + CHUNK - 1)
        flt = {"fromBlock": hex(s), "toBlock": hex(e), "address": addr}
        if topics:
            flt["topics"] = topics
        r = rpc("eth_getLogs", [flt])
        if "result" in r:
            logs += r["result"]; s = e + 1; continue
        # node refused the wide range: fall back to small chunks within budget
        t = s
        while t <= e:
            if used >= small_budget:
                gaps.append({"address": addr, "from": t, "to": b, "reason": "small-chunk budget exhausted"})
                return logs, gaps, used
            flt2 = {"fromBlock": hex(t), "toBlock": hex(min(e, t + SMALL - 1)), "address": addr}
            if topics:
                flt2["topics"] = topics
            r2 = rpc("eth_getLogs", [flt2])
            used += 1
            if "result" in r2:
                logs += r2["result"]
            else:
                gaps.append({"address": addr, "from": t, "to": min(e, t + SMALL - 1), "reason": str(r2.get("error"))[:120]})
            t += SMALL
        s = e + 1
    return logs, gaps, used


def decode(addr, l):
    t0 = l["topics"][0]
    name = NAME[OPERATORS[addr]["kind"]].get(t0, "unknown")
    rec = {"operator": addr, "route": OPERATORS[addr]["route"], "event": name,
           "block": int(l["blockNumber"], 16), "tx": l["transactionHash"], "log_index": int(l["logIndex"], 16)}
    data = l.get("data", "0x")[2:]
    words = [data[i:i + 64] for i in range(0, len(data), 64)]
    if name in ("QuestionFlagged", "QuestionUnflagged", "QuestionEmergencyResolved", "QuestionReported", "QuestionResolved", "QuestionPrepared"):
        rec["question_id"] = l["topics"][1]
    if name == "QuestionReported" and len(words) >= 2:
        rec["request_id"] = "0x" + words[0]; rec["result"] = int(words[1], 16) == 1
    if OPERATORS[addr]["kind"] == "operator" and name in ("QuestionResolved", "QuestionEmergencyResolved") and words:
        rec["result"] = int(words[0], 16) == 1
    if OPERATORS[addr]["kind"] == "adapter" and name in ("QuestionResolved", "QuestionEmergencyResolved", "QuestionManuallyResolved", "QuestionReset",
                                                         "QuestionFlagged", "QuestionUnflagged", "QuestionPaused", "QuestionUnpaused", "AncillaryDataUpdated"):
        rec["question_id"] = l["topics"][1]
        rec["data_words"] = len(words)
    if name in ("NewAdmin", "RemovedAdmin") and len(l["topics"]) >= 3:
        rec["by"] = "0x" + l["topics"][1][-40:]; rec["target"] = "0x" + l["topics"][2][-40:]
    if OPERATORS[addr]["kind"] == "oracle":
        rec["requester"] = "0x" + l["topics"][1][-40:]
        if name == "DisputePrice" and len(words) >= 4:
            # data: identifier, request timestamp, offset(ancillaryData), proposedPrice, then ancillaryData bytes
            rec["request_timestamp"] = int(words[1], 16)
            v = int(words[3], 16)
            rec["proposed_price"] = str(v - (1 << 256) if v >> 255 else v)
            off = int(words[2], 16) * 2
            ln = int(data[off:off + 64], 16) * 2 if len(data) >= off + 64 else 0
            rec["ancillary_hex"] = "0x" + data[off + 64:off + 64 + ln]   # questionID = keccak256(ancillary), computed downstream
    if name == "unknown":
        rec["topic0"] = t0
    return rec


def log_error(data_dir, reason):
    """Record a run that stopped early, print it, and exit without touching state."""
    rec = {"run_at": dt.datetime.now(dt.timezone.utc).isoformat(), "error": reason}
    with open(os.path.join(data_dir, "errors.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec), file=sys.stderr)
    sys.exit(1)


def load_state(data_dir, state_p):
    """Missing state = first run. Unreadable state = stop: guessing a start block could skip a range."""
    if not os.path.exists(state_p):
        return {}
    try:
        with open(state_p) as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        log_error(data_dir, f"state.json unreadable, not overwritten: {e}"[:200])


def save_state(state_p, state):
    """Atomic write: a crash mid-write leaves the previous state.json intact."""
    tmp = state_p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, state_p)


def seen_keys(data_dir):
    """(tx, log_index) of every event already written, across all monthly files."""
    keys = set()
    for p in glob.glob(os.path.join(data_dir, "events-*.jsonl")):
        with open(p) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    keys.add((r["tx"], r["log_index"]))
                except (ValueError, KeyError):
                    continue  # a truncated last line from an interrupted run: skip, never crash
    return keys


def scan(data_dir, month, start, head, summary):
    """Read logs for every contract; write new kept events once. Returns all gaps."""
    budget, all_gaps, seen = MAX_SMALL_CALLS, [], seen_keys(data_dir)
    ev_p = os.path.join(data_dir, f"events-{month}.jsonl")
    # if an interrupted run left a half-written last line, start on a fresh line
    needs_nl = False
    if os.path.exists(ev_p) and os.path.getsize(ev_p) > 0:
        with open(ev_p, "rb") as f:
            f.seek(-1, os.SEEK_END); needs_nl = f.read(1) != b"\n"
    with open(ev_p, "a") as ev:
        if needs_nl:
            ev.write("\n")
        for addr, meta in OPERATORS.items():
            logs, gaps, used = get_logs(addr, start, head, budget, meta.get("topics_filter"))
            budget -= used; all_gaps += gaps
            counts, dupes = {}, 0
            for l in logs:
                rec = decode(addr, l)
                counts[rec["event"]] = counts.get(rec["event"], 0) + 1
                if not (rec["event"] in RARE or rec["event"] == "unknown" or meta["keep_all"]):
                    continue
                if (rec["tx"], rec["log_index"]) in seen:
                    dupes += 1; continue
                rec["block_time"] = block_ts(rec["block"])
                ev.write(json.dumps(rec) + "\n")
                seen.add((rec["tx"], rec["log_index"]))
            summary["by_operator"][addr] = {"route": meta["route"], "counts": counts,
                                            "gaps": len(gaps), "skipped_duplicates": dupes}
    return all_gaps


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "operator_log"
    os.makedirs(data_dir, exist_ok=True)
    state_p = os.path.join(data_dir, "state.json")
    state = load_state(data_dir, state_p)
    r = rpc("eth_blockNumber", [])
    if "result" not in r:
        log_error(data_dir, f"eth_blockNumber failed, state unchanged: {r.get('error')}"[:200])
    head = int(r["result"], 16)
    start = state.get("last_block", head - FIRST_RUN_LOOKBACK) + 1
    run_at = dt.datetime.now(dt.timezone.utc)
    month = run_at.strftime("%Y-%m")
    summary = {"run_at": run_at.isoformat(), "from_block": start, "to_block": head, "by_operator": {}}
    all_gaps = scan(data_dir, month, start, head, summary)
    with open(os.path.join(data_dir, f"counts-{month}.jsonl"), "a") as c:
        c.write(json.dumps(summary) + "\n")
    if all_gaps:
        with open(os.path.join(data_dir, "gaps.jsonl"), "a") as g:
            for x in all_gaps:
                g.write(json.dumps(x) + "\n")
    # checkpoint only up to the first unread block, so gaps are retried next run
    last_ok = min([x["from"] for x in all_gaps], default=head + 1) - 1
    state["last_block"] = last_ok
    state["updated_at"] = run_at.isoformat()
    save_state(state_p, state)
    rare = sum(v for o in summary["by_operator"].values() for k, v in o["counts"].items() if k in RARE)
    dupes = sum(o["skipped_duplicates"] for o in summary["by_operator"].values())
    print(json.dumps({"blocks": [start, head], "checkpoint": last_ok, "rare_events": rare,
                      "counts": {a[:10]: o["counts"] for a, o in summary["by_operator"].items()},
                      "gaps": len(all_gaps), "skipped_duplicates": dupes}))


if __name__ == "__main__":
    main()

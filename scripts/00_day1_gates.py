#!/usr/bin/env python3
"""Settlement tracker v1. Day-1 gates 0 to 3.

Public GET requests only (plus read-only JSON-RPC to public Polygon nodes).
No auth, no API keys, no proxies, no data collection beyond small test batches.
Python standard library only.

Usage:
  python3 day1_gates.py                 # defaults
  python3 day1_gates.py --keyset-seconds 600 --sample 200 --out gates_out

Outputs: <out>/gates_report.json and <out>/raw/*.json, plus a printed summary.
"""
import argparse, collections, datetime as dt, json, os, random, time
import urllib.error, urllib.parse, urllib.request

CUTOFF = dt.datetime(2026, 11, 17, tzinfo=dt.timezone.utc)
CUTOFF_TS = int(CUTOFF.timestamp())
WINDOW_START = CUTOFF - dt.timedelta(days=365)

GAMMA = "https://gamma-api.polymarket.com"
DATA = "https://data-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
RPCS = ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"]
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"  # Polymarket CTF Exchange (Polygon)

PACE = 0.25  # seconds between requests, about 4 per second
STATS = collections.defaultdict(lambda: {"n": 0, "ok": 0, "http429": 0, "errors": collections.Counter(), "t": []})


def _host(url):
    return urllib.parse.urlparse(url).netloc


def get(url, params=None, timeout=30, retries=2, body=None):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    h = _host(url)
    last = None
    for attempt in range(retries + 1):
        time.sleep(PACE)
        s = STATS[h]
        s["n"] += 1
        s["t"].append(time.time())
        t0 = time.time()
        try:
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(url, data=data, headers={
                "User-Agent": "settlement-tracker-gates/0.1", "Accept": "application/json",
                **({"Content-Type": "application/json"} if body is not None else {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                s["ok"] += 1
                try:
                    return r.status, json.loads(raw), None, time.time() - t0
                except ValueError:
                    return r.status, None, "non-json", time.time() - t0
        except urllib.error.HTTPError as e:
            if e.code == 429:
                s["http429"] += 1
                time.sleep(2 * (attempt + 1))
            s["errors"][f"HTTP {e.code}"] += 1
            try:
                payload = json.loads(e.read())
            except Exception:
                payload = None
            last = (e.code, payload, f"HTTP {e.code}", time.time() - t0)
            if e.code not in (429, 500, 502, 503, 504):
                return last
        except Exception as e:  # TLS reset, timeout, DNS
            s["errors"][type(e).__name__ + ": " + str(e)[:80]] += 1
            last = (0, None, type(e).__name__ + ": " + str(e)[:120], time.time() - t0)
            time.sleep(1 + attempt)
    return last


def rows(payload, *keys):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for k in keys + ("data", "markets", "trades", "history", "items", "results"):
            v = payload.get(k)
            if isinstance(v, list):
                return v
    return []


def iso_to_ts(s):
    if not s:
        return None
    s = str(s).replace(" ", "T").replace("Z", "+00:00")
    if s.endswith("+00"):
        s += ":00"
    try:
        return int(dt.datetime.fromisoformat(s).timestamp())
    except ValueError:
        return None


def jlist(v):
    if isinstance(v, list):
        return v
    try:
        return json.loads(v) if v else []
    except ValueError:
        return []


def save(out, name, obj):
    with open(os.path.join(out, "raw", name), "w") as f:
        json.dump(obj, f, indent=1, default=str)


# ---------------- Gate 0 ----------------
def gate0(out):
    probes = {
        "gamma /markets": f"{GAMMA}/markets?limit=1&closed=true",
        "data-api /v2/status": f"{DATA}/v2/status",
        "clob /time": f"{CLOB}/time",
        "clob /markets": f"{CLOB}/markets?limit=1",
        "kalshi /markets settled": f"{KALSHI}/markets?status=settled&limit=1",
    }
    res = {}
    for name, url in probes.items():
        tries = [get(url, retries=0, timeout=15) for _ in range(3)]
        res[name] = [{"status": t[0], "err": t[2], "secs": round(t[3], 3)} for t in tries]
    for rpc in RPCS:
        tries = [get(rpc, body={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []},
                     retries=0, timeout=15) for _ in range(3)]
        res["rpc " + _host(rpc)] = [{"status": t[0], "err": t[2], "secs": round(t[3], 3),
                                      "block": (t[1] or {}).get("result") if isinstance(t[1], dict) else None}
                                     for t in tries]
    save(out, "gate0.json", res)
    ok = {k: sum(1 for t in v if t["status"] == 200) for k, v in res.items()}
    blocked = [k for k in ("data-api /v2/status", "clob /time") if ok[k] < 3]
    return {"per_probe_ok_of_3": ok, "stop": bool(blocked), "failed_stop_hosts": blocked}


# ---------------- Gate 1 ----------------
def gate1(out, keyset_seconds, sample_n):
    params = {"closed": "true", "limit": 100,
              "end_date_min": WINDOW_START.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "end_date_max": CUTOFF.strftime("%Y-%m-%dT%H:%M:%SZ")}
    markets, cursor, pages, t0, complete, fail = [], None, 0, time.time(), False, None
    while time.time() - t0 < keyset_seconds:
        p = dict(params)
        if cursor:
            p["after_cursor"] = cursor
        st, js, err, _ = get(f"{GAMMA}/markets/keyset", p, timeout=60, retries=3)
        if st != 200 or not isinstance(js, dict):
            fail = err or f"status {st}"
            break
        page = js.get("markets") or []
        pages += 1
        for m in page:
            markets.append({k: m.get(k) for k in (
                "id", "conditionId", "questionID", "endDate", "closedTime", "umaResolutionStatus",
                "resolvedBy", "automaticallyResolved", "resolutionMechanism", "negRisk",
                "outcomes", "clobTokenIds", "outcomePrices", "volumeNum", "question")})
        cursor = js.get("next_cursor")
        if not cursor or not page:
            complete = True
            break
    elapsed = time.time() - t0
    save(out, "gate1_gamma_markets.json", markets)

    random.seed(17)
    seen, uniq = set(), []
    for m in markets:
        c = (m.get("conditionId") or "").lower()
        if c and c not in seen:
            seen.add(c); uniq.append(m)
    with_cid = uniq
    sample = random.sample(with_cid, min(sample_n, len(with_cid)))
    got, res_rows = set(), []
    for i in range(0, len(sample), 20):
        batch = [m["conditionId"] for m in sample[i:i + 20]]
        st, js, err, _ = get(f"{DATA}/v2/resolutions", {"condition": ",".join(batch)}, timeout=30)
        for r in rows(js, "resolutions"):
            res_rows.append(r)
            cid = r.get("condition") or r.get("condition_id") or r.get("conditionId")
            if cid:
                got.add(cid.lower())
    save(out, "gate1_resolutions_sample.json", res_rows)
    fields = collections.Counter(k for r in res_rows for k, v in r.items() if v not in (None, "", []))
    disputed = sum(1 for r in res_rows if r.get("was_disputed") is True)
    newv = sum(1 for r in res_rows if r.get("new_version_q"))
    status = collections.Counter(str(r.get("status")) for r in res_rows)
    source = collections.Counter(str(r.get("resolution_source")) for r in res_rows)
    joined = sum(1 for m in sample if m["conditionId"].lower() in got)
    return {
        "gamma_keyset": {"pages": pages, "markets": len(markets), "unique_conditionIds": len(with_cid), "complete": complete,
                         "stopped_reason": fail or (None if complete else f"time cap {keyset_seconds}s"),
                         "seconds": round(elapsed, 1),
                         "filter": "endDate in [cutoff-365d, cutoff); close_time (closedTime) checked separately"},
        "closedTime_outside_window": sum(1 for m in markets
                                         if (iso_to_ts(m.get("closedTime")) or 0) < WINDOW_START.timestamp()
                                         or (iso_to_ts(m.get("closedTime")) or 0) >= CUTOFF_TS),
        "resolutions_test_batch": {"requested": len(sample), "rows_returned": len(res_rows),
                                   "joined": joined, "join_rate": round(joined / max(1, len(sample)), 3),
                                   "field_nonnull_counts": dict(fields), "was_disputed_true": disputed,
                                   "new_version_q_nonnull": newv, "status": dict(status),
                                   "resolution_source": dict(source)},
    }, markets, sample


# ---------------- Gate 2 ----------------
def gate2(out):
    now = dt.datetime.now(dt.timezone.utc)
    p = {"closed": "true", "limit": 100,
         "end_date_min": (now - dt.timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "end_date_max": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    recent, cursor = [], None
    for _ in range(30):
        q = dict(p)
        if cursor:
            q["after_cursor"] = cursor
        st, js, err, _ = get(f"{GAMMA}/markets/keyset", q, timeout=60, retries=3)
        if st != 200 or not isinstance(js, dict):
            break
        recent += js.get("markets") or []
        cursor = js.get("next_cursor")
        if not cursor:
            break
    limbo = [m for m in recent if str(m.get("umaResolutionStatus")).lower() != "resolved"]
    probe = limbo[:40]
    oi_rows = []
    for i in range(0, len(probe), 20):
        batch = [m["conditionId"] for m in probe[i:i + 20] if m.get("conditionId")]
        st, js, err, _ = get(f"{DATA}/v2/oi", {"condition": ",".join(batch)}, timeout=30)
        oi_rows += rows(js, "open_interest")
    save(out, "gate2_pm_oi.json", {"limbo_markets": [{k: m.get(k) for k in (
        "conditionId", "question", "closedTime", "umaResolutionStatus")} for m in probe], "oi": oi_rows})

    k_rows, cursor = [], None
    for _ in range(5):
        q = {"status": "closed", "limit": 1000}
        if cursor:
            q["cursor"] = cursor
        st, js, err, _ = get(f"{KALSHI}/markets", q, timeout=30)
        if st != 200:
            break
        k_rows += js.get("markets") or []
        cursor = js.get("cursor")
        if not cursor:
            break
    mve = [m for m in k_rows if m.get("mve_collection_ticker") or str(m.get("ticker", "")).startswith("KXMVE")]
    keep = [m for m in k_rows if m not in mve]

    def fnum(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    save(out, "gate2_kalshi_closed.json", [{k: m.get(k) for k in (
        "ticker", "close_time", "status", "open_interest", "open_interest_fp", "result")} for m in keep])
    return {
        "polymarket": {"recent_closed_markets": len(recent), "closed_not_resolved": len(limbo),
                       "oi_probed": len(probe), "oi_rows_returned": len(oi_rows),
                       "oi_example": oi_rows[:2]},
        "kalshi": {"closed_not_settled": len(k_rows), "kxmve_excluded": len(mve),
                   "open_interest_fp_sum_contracts": round(sum(fnum(m.get("open_interest_fp")) for m in keep), 2),
                   "note": "open_interest_fp unit not verified (contracts vs USD); check docs before any USD figure"},
    }


# ---------------- Gate 3 ----------------
def gate3(out, pm_sample, n=50):
    random.seed(3)
    cands = [m for m in pm_sample if iso_to_ts(m.get("closedTime")) and jlist(m.get("clobTokenIds"))]
    cands = random.sample(cands, min(n, len(cands)))
    pm = {"tested": len(cands), "data_api_points_60m": 0, "data_api_points_24h": 0, "data_api_any": 0,
          "clob_any": 0, "trades_any": 0, "trades_last_within_60m": 0, "trades_last_within_24h": 0}
    raw = []
    for m in cands:
        close = iso_to_ts(m["closedTime"])
        outs, toks = jlist(m.get("outcomes")), jlist(m.get("clobTokenIds"))
        yi = next((i for i, o in enumerate(outs) if str(o).lower() == "yes"), 0)
        tok = toks[yi] if yi < len(toks) else toks[0]
        st, js, err, _ = get(f"{DATA}/v2/prices-history",
                             {"token_id": tok, "start": close - 3600, "end": close + 1, "bucket_seconds": 60}, timeout=30)
        pts = rows(js, "history", "points", "prices")
        ts = [int(p.get("t") or p.get("ts") or p.get("timestamp") or 0) for p in pts if isinstance(p, dict)]
        if pts:
            pm["data_api_any"] += 1
        if any(close - 3600 <= t <= close for t in ts):
            pm["data_api_points_60m"] += 1
        if any(close - 86400 <= t <= close for t in ts):
            pm["data_api_points_24h"] += 1
        st2, js2, err2, _ = get(f"{CLOB}/prices-history",
                                {"market": tok, "startTs": close - 3600, "endTs": close + 1, "fidelity": 1},
                                timeout=30)
        if rows(js2, "history"):
            pm["clob_any"] += 1
        st3, js3, err3, _ = get(f"{DATA}/v2/trades", {"condition": m["conditionId"], "limit": 5}, timeout=30)
        tr = rows(js3, "trades")
        tts = [iso_to_ts(t.get("block_timestamp")) if isinstance(t.get("block_timestamp"), str)
               else (t.get("block_timestamp") or t.get("timestamp")) for t in tr]
        tts = [int(x) for x in tts if x]
        if tr:
            pm["trades_any"] += 1
        before = [t for t in tts if t <= close]
        if before and close - max(before) <= 3600:
            pm["trades_last_within_60m"] += 1
        if before and close - max(before) <= 86400:
            pm["trades_last_within_24h"] += 1
        raw.append({"condition": m["conditionId"], "token": tok, "close": close,
                    "data_api_status": st, "data_api_n": len(pts), "data_api_sample": pts[:2],
                    "clob_status": st2, "clob_n": len(rows(js2, "history")),
                    "trades_status": st3, "trades_sample": tr[:1]})
    save(out, "gate3_pm.json", raw)

    # Kalshi: settled markets in window, non-KXMVE, last trade before close
    q = {"status": "settled", "limit": 1000, "min_close_ts": int(WINDOW_START.timestamp()), "max_close_ts": CUTOFF_TS}
    st, js, err, _ = get(f"{KALSHI}/markets", q, timeout=30)
    allk = (js or {}).get("markets", [])
    def vol(m):
        try:
            return float(m.get("volume_fp") or m.get("volume") or 0)
        except (TypeError, ValueError):
            return 0.0
    ks = [m for m in allk if vol(m) > 0 and not m.get("mve_collection_ticker")
          and not str(m.get("ticker", "")).startswith("KXMVE")]
    random.seed(5)
    n_eligible = len(ks)
    ks = random.sample(ks, min(n, len(ks)))
    kal = {"settled_page": len(allk), "with_volume_non_kxmve": n_eligible, "tested": len(ks), "trades_any": 0, "last_within_60m": 0, "last_within_24h": 0}
    kraw = []
    for m in ks:
        close = iso_to_ts(m.get("close_time"))
        st, js, err, _ = get(f"{KALSHI}/markets/trades", {"ticker": m["ticker"], "max_ts": close, "limit": 1},
                             timeout=30)
        tr = (js or {}).get("trades", []) if isinstance(js, dict) else []
        if tr:
            kal["trades_any"] += 1
            t = iso_to_ts(tr[0].get("created_time"))
            if t and close - t <= 3600:
                kal["last_within_60m"] += 1
            if t and close - t <= 86400:
                kal["last_within_24h"] += 1
        kraw.append({"ticker": m["ticker"], "close": close, "status": st, "trade": tr[:1]})
    save(out, "gate3_kalshi.json", kraw)

    # OrderFilled fallback: feasibility only (do public nodes serve exchange logs over a block range)
    fb = {}
    for rpc in RPCS:
        st, js, err, _ = get(rpc, body={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []})
        try:
            head = int(js["result"], 16)
        except Exception:
            fb[_host(rpc)] = {"error": err}
            continue
        out_r = {}
        for span in (100, 1000):
            st, js, err, _ = get(rpc, body={"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [{
                "address": CTF_EXCHANGE, "fromBlock": hex(head - span), "toBlock": hex(head)}]}, timeout=60)
            if isinstance(js, dict) and "result" in js:
                out_r[f"{span}_blocks"] = {"logs": len(js["result"]),
                                           "topic0_counts": dict(collections.Counter(
                                               l["topics"][0] for l in js["result"] if l.get("topics")).most_common(3))}
            else:
                out_r[f"{span}_blocks"] = {"error": (js or {}).get("error") if isinstance(js, dict) else err}
        fb[_host(rpc)] = out_r
    return {"polymarket": pm, "kalshi": kal, "orderfilled_fallback": fb,
            "note": "Polymarket: points_60m = 60s buckets in [closedTime-60m, closedTime]; points_24h key now also 60m window; trades = latest trades, last one before closedTime"}


def rate_summary():
    out = {}
    for h, s in STATS.items():
        span = (max(s["t"]) - min(s["t"])) / 60 if len(s["t"]) > 1 else 0
        out[h] = {"requests": s["n"], "ok": s["ok"], "http429": s["http429"],
                  "observed_rpm": round(s["n"] / span, 1) if span else None,
                  "errors": dict(s["errors"].most_common(5))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="gates_out")
    ap.add_argument("--keyset-seconds", type=int, default=300)
    ap.add_argument("--sample", type=int, default=200)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "raw"), exist_ok=True)
    report = {"cutoff": CUTOFF.isoformat(), "run_at": dt.datetime.now(dt.timezone.utc).isoformat()}

    report["gate0"] = g0 = gate0(a.out)
    print("GATE 0", json.dumps(g0, indent=1))
    if g0["stop"]:
        report["stopped"] = "Gate 0 failed on a stop host; gates 1 to 3 not run"
    else:
        g1, markets, sample = gate1(a.out, a.keyset_seconds, a.sample)
        report["gate1"] = g1
        print("GATE 1", json.dumps(g1, indent=1, default=str))
        report["gate2"] = g2 = gate2(a.out)
        print("GATE 2", json.dumps(g2, indent=1, default=str))
        report["gate3"] = g3 = gate3(a.out, sample)
        print("GATE 3", json.dumps(g3, indent=1, default=str))
    report["rate_limits"] = rl = rate_summary()
    print("RATES", json.dumps(rl, indent=1))
    with open(os.path.join(a.out, "gates_report.json"), "w") as f:
        json.dump(report, f, indent=1, default=str)
    print("Wrote", os.path.join(a.out, "gates_report.json"))


if __name__ == "__main__":
    main()

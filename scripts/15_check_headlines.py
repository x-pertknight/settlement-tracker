#!/usr/bin/env python3
"""Recompute the README and RESULTS.md headline figures from the files shipped in data/ and compare.

Standard library only, no network. Exits 1 if any recomputed figure differs from the published one.
The 98, 65 and interval figures are in scripts/reproduce_headlines.py. Figures that need working files
not shipped in this repo are listed at the end, with the missing file.
Usage (from the repo root): python3 -I scripts/15_check_headlines.py
"""
import csv, gzip, json, os, statistics, sys

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
PATHS = ("MOOV2 direct", "MOOV2 routed", "OOV2 routed")
FAILS = []


def check(name, got, want):
    """Print one PASS or FAIL line and remember failures."""
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {got}" + ("" if ok else f" (published {want})"))
    if not ok:
        FAILS.append(name)


def pct(a, b):
    return round(100 * a / b, 1)


def dispute_counts(rows):
    """Per path: disputed, settled (final answer known), changed, open, decided by vote."""
    out = {}
    for p in PATHS + ("All",):
        rs = [r for r in rows if p == "All" or r["path"] == p]
        done = [r for r in rs if r["final"] is not None]
        out[p] = {"disputed": len(rs), "settled": len(done),
                  "changed": sum(1 for r in done if r["final"] != r["first"]),
                  "open": len(rs) - len(done), "vote": sum(1 for r in rs if r["how"] == "vote")}
    return out


def check_disputes(d):
    """RESULTS.md section 2 table and README finding 1, recomputed from the per question rows."""
    c = dispute_counts(d["rows"])
    want = {"MOOV2 direct": (692, 635, 181, 57, 30, 28.5), "MOOV2 routed": (327, 283, 41, 44, 2, 14.5),
            "OOV2 routed": (18, 11, 1, 7, 1, 9.1), "All": (1037, 929, 223, 108, 33, 24.0)}
    for p, (n, s, ch, op, v, share) in want.items():
        x = c[p]
        check(f"{p}: disputed questions", x["disputed"], n)
        check(f"{p}: settled by cutoff", x["settled"], s)
        check(f"{p}: final outcome differs from first proposal", x["changed"], ch)
        check(f"{p}: share changed of settled (%)", pct(x["changed"], x["settled"]), share)
        check(f"{p}: still open at cutoff", x["open"], op)
        check(f"{p}: outcome set by the UMA vote", x["vote"], v)
        # The stored summary must agree with the rows it was built from.
        s_ = d["by_path"][p]
        check(f"{p}: by_path summary agrees with rows",
              (s_["disputed"], s_["market_settled"], s_["outcome_changed"]), (x["disputed"], x["settled"], x["changed"]))
    a = c["All"]
    check("bound if all open kept the first answer (%)", pct(a["changed"], a["disputed"]), 21.5)
    check("bound if all open changed (%)", pct(a["changed"] + a["open"], a["disputed"]), 31.9)


def check_lines_binary(d):
    """RESULTS.md section 2: lines vs binary on the direct path (only that path carries market type)."""
    rows = [r for r in d["rows"] if r["path"] == "MOOV2 direct"]
    for t, n, s, ch, share in (("line", 540, 491, 128, 26.1), ("binary", 151, 144, 53, 36.8)):
        rs = [r for r in rows if r["mtype"] == t]
        done = [r for r in rs if r["final"] is not None]
        changed = sum(1 for r in done if r["final"] != r["first"])
        check(f"direct path {t}: disputed", len(rs), n)
        check(f"direct path {t}: changed of settled", (changed, len(done), pct(changed, len(done))), (ch, s, share))


def check_timing(d):
    """data/disputes_timing.csv must carry the same questions, in the same order, as data/disputes_final.json."""
    rows = list(csv.DictReader(open(os.path.join(DATA, "disputes_timing.csv"), newline="", encoding="utf-8")))
    same = all((t["qid"], t["path"], t["first"], t["final"], t["how"]) ==
               (f["qid"], f["path"], str(f["first"]), "" if f["final"] is None else str(f["final"]), f["how"])
               for t, f in zip(rows, d["rows"]))
    check("disputes_timing.csv matches disputes_final.json row by row", (len(rows), same), (len(d["rows"]), True))
    for p, n in (("MOOV2 direct", 38), ("MOOV2 routed", 10), ("OOV2 routed", 1)):
        check(f"{p}: went to a second dispute", sum(1 for r in rows if r["path"] == p and int(r["dispute_events"]) >= 2), n)


def wq(pairs, q):
    """Weighted quantile, same rule as scripts/12_pm_lag_windows.py."""
    pairs = sorted(pairs); tot = sum(w for _, w in pairs); acc = 0
    for v, w in pairs:
        acc += w
        if acc >= q * tot:
            return v


def check_markets(rows):
    """Lag figures from the market file: RESULTS.md section 3 and README findings 4 and limits."""
    pm = [r for r in rows if r["venue"] == "polymarket"]
    ks = [r for r in rows if r["venue"] == "kalshi"]
    check("Polymarket rows in the subsample", len(pm), 3105)
    check("Polymarket estimated markets in window (M)", round(sum(float(r["weight"]) for r in pm) / 1e6, 2), 5.48)
    lag = [r for r in pm if r["lag_status"] == "in lag"]
    pts = [(float(r["lag_hours"]), float(r["weight"])) for r in lag]
    check("Polymarket markets in the lag", len(lag), 1337)
    check("Polymarket median lag, end date to settlement (h)", round(wq(pts, .5), 1), 4.0)
    check("Polymarket p90 lag (h)", round(wq(pts, .9), 1), 10.3)
    check("Polymarket p99 lag (h)", round(wq(pts, .99)), 54)
    crypto = [(float(r["lag_hours"]), float(r["weight"])) for r in lag if r["category"] == "crypto_other"]
    check("Polymarket crypto price markets: n, median (min)", (len(crypto), round(wq(crypto, .5) * 60)), (391, 13))
    sched = [r for r in pm if r["class"] == "scheduled" and r["path"] in ("UMA MOOV2 direct", "UMA MOOV2 routed")]
    padded = [r for r in sched if r["lag_status"].startswith("excluded")]
    check("scheduled MOOV2 markets excluded for padded end date", (len(padded), len(sched)), (377, 1714))
    check("of which sports", sum(1 for r in padded if r["category"] == "sports"), 302)
    mins = sorted(float(r["lag_hours"]) * 60 for r in ks)
    check("Kalshi markets", len(mins), 19373)
    check("Kalshi median lag, close to settlement (min)", round(statistics.median(mins), 1), 2.9)
    # Same index rule as scripts/10_kalshi_cluster_ci.py: xs[int(q * (n - 1))].
    check("Kalshi p90 lag (min)", round(mins[int(.9 * (len(mins) - 1))]), 64)
    check("Kalshi p99 lag (h)", round(mins[int(.99 * (len(mins) - 1))] / 60, 1), 10.8)


NOT_SHIPPED = [
    ("1.43M (1,434,227) questions with a proposal, the per path denominators and the 0.07% dispute rate",
     "census output of scripts/04_uma_onchain_census.py (events-NNN.jsonl.gz, raw on-chain events)"),
    ("660 / 580 / 550 too early; 169 of 243 on the facts; the vote split table",
     "s2d_disputed_questions.json (input of scripts/09 and 14)"),
    ("13 re-asks, dispute to settle medians and the share settled within 4 and 24 hours",
     "s2d_disputed_questions.json (needs proposal and settle times per round)"),
    ("29 of 691 was_disputed", "disputes_mapped.json and the data-api reads of scripts/11 (stored total only)"),
    ("53,801 sampled markets and the path mix (64.8%, 16.8%, ...)", "sample.jsonl.gz from scripts/01"),
    ("Kalshi traded only 6,532 and the minute resampled intervals", "kalshi_minutes.jsonl.gz from scripts/05"),
    ("124 of 124 timestamps within 47 s", "raw/b3_check.json from scripts/08"),
    ("money waiting ($5.8M, $5.0M, ...)", "the 18 Nov 2026 API snapshots (point in time reads)"),
]


def main():
    d = json.load(open(os.path.join(DATA, "disputes_final.json")))
    rows = list(csv.DictReader(gzip.open(os.path.join(DATA, "settlement_tracker_v1_markets.csv.gz"), "rt")))
    check_disputes(d)
    check_lines_binary(d)
    check_timing(d)
    check_markets(rows)
    print("\nNot recomputed here (needs inputs not shipped):")
    for what, missing in NOT_SHIPPED:
        print(f"  {what}: needs {missing}")
    print(f"\n{'FAILED: ' + ', '.join(FAILS) if FAILS else 'All recomputed figures match.'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

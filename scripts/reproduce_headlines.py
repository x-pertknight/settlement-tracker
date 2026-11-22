#!/usr/bin/env python3
"""Print the dispute headline figures of README finding 1 and RESULTS.md section 2, computed from shipped data only.

Reads data/disputes_timing.csv (one row per disputed question, first dispute time, Polymarket event).
Offline, standard library only. Exits 1 if a figure differs from the published one.
The interval uses the method of scripts/14_dispute_vote_split.py: settled markets grouped by the UTC hour of
their first dispute, 4,000 resamples of whole hours, random.Random(1), 2.5% and 97.5% order statistics.
Usage (from the repo root): python3 -I scripts/reproduce_headlines.py
"""
import collections, csv, os, random, sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "disputes_timing.csv")
FAILS = []


def show(label, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f" (published {want})"))
    if not ok:
        FAILS.append(label)


def cluster_ci(groups, stat, reps=4000, seed=1):
    """Same as scripts/14_dispute_vote_split.py: resample whole hours, keep the 2.5% and 97.5% values."""
    keys, rng, out = list(groups), random.Random(seed), []
    for _ in range(reps):
        sample = [x for k in rng.choices(keys, k=len(keys)) for x in groups[k]]
        out.append(stat(sample))
    out.sort()
    return round(out[int(reps * .025)], 1), round(out[int(reps * .975) - 1], 1)


def pct_changed(rows):
    return 100 * sum(r["changed"] for r in rows) / len(rows)


def match(r):
    """Gamma splits one match into several events ("X vs. Y - Exact Score"); the match is the part before " - "."""
    return r["gamma_event_title"].split(" - ")[0].strip()


def load():
    rows = list(csv.DictReader(open(SRC, newline="", encoding="utf-8")))
    for r in rows:
        r["settled"] = r["final"] != ""
        r["changed"] = r["settled"] and r["final"] != r["first"]
        r["t"] = int(r["first_dispute_unix"])
    return rows


def totals(rows):
    settled = [r for r in rows if r["settled"]]
    changed = sum(r["changed"] for r in settled)
    show("disputed questions", len(rows), 1037)
    show("settled by cutoff", len(settled), 929)
    show("final outcome differs from first proposal", changed, 223)
    show("share changed of settled (%)", round(100 * changed / len(settled), 1), 24.0)
    show("still open at cutoff", len(rows) - len(settled), 108)
    show("outcome set by the UMA vote", sum(r["how"] == "vote" for r in rows), 33)


def bursts(rows):
    settled = [r for r in rows if r["settled"]]
    per_match = collections.Counter(match(r) for r in settled if r["gamma_event_title"])
    name, n = per_match.most_common(1)[0]
    mins = collections.Counter(r["t"] // 60 for r in settled if match(r) == name)
    two = max(mins[m] + mins.get(m + 1, 0) for m in mins)
    show(f"most settled disputes on one match ({name})", n, 98)
    show("of which in two consecutive minutes", two, 62)
    by_min = collections.Counter(r["t"] // 60 for r in rows)
    minute, size = by_min.most_common(1)[0]
    burst = [r for r in rows if r["t"] // 60 == minute]
    names = sorted({match(r) for r in burst})
    show(f"largest one minute burst ({', '.join(names)})", size, 65)
    show("of the burst, still open at cutoff (outside the 24.0%)", sum(not r["settled"] for r in burst), 65)


def interval(rows):
    by_hour = collections.defaultdict(list)
    for r in rows:
        if r["settled"]:
            by_hour[r["t"] // 3600].append(r)
    show("hours with settled disputes", len(by_hour), 199)
    show("95% interval, whole hours resampled (%)", cluster_ci(by_hour, pct_changed), (16.6, 35.0))


def main():
    rows = load()
    totals(rows)
    bursts(rows)
    interval(rows)
    print("FAILED: " + ", ".join(FAILS) if FAILS else "All figures reproduced.")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

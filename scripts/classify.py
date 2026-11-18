"""A1 classifier: Polymarket market -> scheduled / by-date / unclassified.

Uses only question text, event series and event tags. Timing, price and
outcome fields are refused, so the outcome can never shape the class.

Usage (stdlib only, no network):
  python3 -I classify.py classify gamma_dump.json  > classes.csv
  python3 -I classify.py sample   gamma_dump.json  handcheck_100.csv
gamma_dump.json = list of Gamma market objects (collection output).
"""
import csv, json, random, re, sys

FORBIDDEN = {"endDate", "closedTime", "umaEndDate", "outcomePrices",
             "lastTradePrice", "umaResolutionStatus", "umaResolutionStatuses"}

# Whole words only: "by market cap" must not read as "by" + March (fixed 18 Nov 2026 after the hand-check).
MONTH = (r"(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|june?|july?|aug(ust)?|"
         r"sep(t(ember)?)?|oct(ober)?|nov(ember)?|dec(ember)?)\b")
DATE_EXPR = rf"({MONTH}|end of|the end of|q[1-4]\b|20\d\d|\d{{1,2}}/\d{{1,2}})"
# "by"/"before" must be followed by a date, so "win by 10 points" does not match.
BY_DATE = re.compile(
    rf"\b(by|before)\s+(the\s+)?{DATE_EXPR}|\bin\s+20\d\d\b|\bthis\s+(year|month|week)\b",
    re.I)

# "on <month> <day>" or "on <m>/<d>" in the question = a fixed resolution date (weather, price-at-date markets).
ON_DATE = re.compile(rf"\bon\s+({MONTH}\s+\d{{1,2}}|\d{{1,2}}/\d{{1,2}})", re.I)

SPORTS = {"sports", "nfl", "nba", "mlb", "nhl", "soccer", "football", "tennis",
          "mma", "ufc", "boxing", "cricket", "golf", "f1", "esports", "ncaa"}
UPDOWN = re.compile(r"up[\s-]*or[\s-]*down", re.I)
MACRO = re.compile(r"\b(cpi|inflation report|jobs report|nonfarm|payrolls|fomc|"
                   r"fed (rate|decision)|interest rate decision|gdp|pce|ppi)\b", re.I)


def labels(m):
    """Lower-cased series titles/slugs and tag labels/slugs from the market's events."""
    out = []
    for ev in m.get("events") or []:
        for key in ("series", "tags"):
            for item in ev.get(key) or []:
                out += [str(item.get(k, "")).lower() for k in ("slug", "title", "label")]
        out.append(str(ev.get("category", "")).lower())
    return [x for x in out if x]


def classify(m):
    """Return (class, reason). Raises if a timing/outcome field is passed in."""
    leaked = FORBIDDEN & set(m)
    if leaked:
        raise ValueError(f"timing/outcome fields passed to classifier: {sorted(leaked)}")
    q = m.get("question") or ""
    lab = labels(m)
    if BY_DATE.search(q):
        return "by-date", "question: by/before + date"
    words = {w for l in lab for w in re.split(r"[^a-z0-9]+", l)}
    if words & SPORTS:
        return "scheduled", "tag/series: sports"
    if UPDOWN.search(q) or any(UPDOWN.search(l) for l in lab):
        return "scheduled", "crypto up/down"
    if MACRO.search(q) or any(MACRO.search(l) for l in lab):
        return "scheduled", "scheduled macro release"
    if ON_DATE.search(q):
        return "scheduled", "question: on + date"   # added 18 Nov 2026 before the hand-check (text only)
    return "unclassified", "no rule matched"


def slim(m):
    """Drop forbidden fields before classifying (a raw Gamma object contains them)."""
    return {k: v for k, v in m.items() if k not in FORBIDDEN}


def sample(markets, n_sched=40, n_by=40, n_unc=20, seed=20261117):
    """Fixed-seed sample, round-robin across first tag so one category cannot fill a class."""
    rng = random.Random(seed)
    pools = {"scheduled": {}, "by-date": {}, "unclassified": {}}
    for m in markets:
        cls, why = classify(slim(m))
        tag = (labels(slim(m)) or ["none"])[0]
        pools[cls].setdefault(tag, []).append((m, cls, why))
    rows = []
    for cls, n in (("scheduled", n_sched), ("by-date", n_by), ("unclassified", n_unc)):
        buckets = [rng.sample(v, len(v)) for _, v in sorted(pools[cls].items())]
        picked = []
        while len(picked) < n and any(buckets):
            for b in buckets:
                if b and len(picked) < n:
                    picked.append(b.pop())
        rows += picked
    return rows


def main():
    cmd, src = sys.argv[1], sys.argv[2]
    markets = json.load(open(src))
    if cmd == "classify":
        w = csv.writer(sys.stdout)
        w.writerow(["id", "class", "reason"])
        for m in markets:
            w.writerow([m.get("id"), *classify(slim(m))])
    elif cmd == "sample":
        with open(sys.argv[3], "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "question", "labels", "rule_class", "rule_reason", "hand_class", "notes"])
            for m, cls, why in sample(markets):
                w.writerow([m.get("id"), m.get("question"), "|".join(labels(slim(m))), cls, why, "", ""])


if __name__ == "__main__":
    main()

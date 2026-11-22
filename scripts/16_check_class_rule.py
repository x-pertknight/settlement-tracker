#!/usr/bin/env python3
"""Rerun classify.py on the 100 market check in data/class_check_100.csv and compare with RESULTS.md section 3.

The file keeps each market's question text and its tag and series labels, which is all the classifier reads.
Checks: (1) the rule today gives rule_class_now for all 100; (2) the hand check agrees with the rule at
sampling in 39 of 40 scheduled and 20 of 40 by-date markets; (3) 12 of the 20 unclassified are fixed moment
(hand checked as scheduled). Standard library only. Usage (from the repo root): python3 -I scripts/16_check_class_rule.py
"""
import collections, csv, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script folder from the path
from classify import classify

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "class_check_100.csv")


def as_market(row):
    """Rebuild the minimal market object classify() reads: question plus labels as tags."""
    tags = [{"slug": label} for label in row["labels"].split("|") if label]
    return {"id": row["id"], "question": row["question"], "events": [{"tags": tags}]}


def main():
    rows = list(csv.DictReader(open(SRC, newline="")))
    same = sum(1 for r in rows if classify(as_market(r))[0] == r["rule_class_now"])
    agree = collections.Counter((r["rule_class_at_sampling"], r["agree_at_sampling"]) for r in rows)
    unc_fixed = sum(1 for r in rows if r["rule_class_at_sampling"] == "unclassified" and r["check_class"] == "scheduled")
    results = [("rule today matches rule_class_now", same, 100),
               ("scheduled: hand check agrees", agree[("scheduled", "yes")], 39),
               ("by-date: hand check agrees", agree[("by-date", "yes")], 20),
               ("unclassified that are fixed moment", unc_fixed, 12)]
    fails = 0
    for name, got, want in results:
        print(f"{'PASS' if got == want else 'FAIL'}  {name}: {got}" + ("" if got == want else f" (published {want})"))
        fails += got != want
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

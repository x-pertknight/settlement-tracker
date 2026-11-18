"""Offline tests for classify.py on synthetic market objects."""
import unittest
from classify import classify, sample, slim


def mk(q, tags=(), series=()):
    return {"id": q, "question": q, "events": [{"tags": [{"slug": t} for t in tags],
                                               "series": [{"slug": s} for s in series]}]}


class TestClassify(unittest.TestCase):
    def test_cases(self):
        cases = [
            (mk("Will the Chiefs win by 10+ points?", ["nfl"]), "scheduled"),
            (mk("Will BTC hit $150k by December 31?", ["crypto"]), "by-date"),
            (mk("Will X happen before 2027?"), "by-date"),
            (mk("Will Y be released in 2026?"), "by-date"),
            (mk("Bitcoin Up or Down - Nov 17, 3PM ET", ["crypto"], ["btc-up-or-down-hourly"]), "scheduled"),
            (mk("Will October CPI come in above 3.0%?", ["economy"]), "scheduled"),
            (mk("Will Lakers beat Celtics?", ["nba"]), "scheduled"),
            (mk("Will Z win by KO?", ["ufc"]), "scheduled"),
            (mk("Who will be the next UK PM?", ["politics"]), "unclassified"),
            (mk("Will the highest temperature in Seoul be 19°C or higher on November 11?", ["weather"]), "scheduled"),
            (mk("Will Bitcoin be above $95,000 on Nov 17?", ["crypto"]), "scheduled"),
            (mk("Will BTC reach $150k by Nov 30?", ["crypto"]), "by-date"),     # by-date still wins over on-date
            (mk("Will NVIDIA be the largest company in the world by market cap on January 31?"), "scheduled"),  # not "by" + March
            (mk("Will X happen by Mar 5?"), "by-date"),
            (mk("Will X happen by Sept. 30?"), "by-date"),
            (mk("Will Marseille win by more than one goal?", ["soccer"]), "scheduled"),
        ]
        for m, want in cases:
            self.assertEqual(classify(m)[0], want, m["question"])

    def test_rejects_timing_fields(self):
        with self.assertRaises(ValueError):
            classify({**mk("Will A win?", ["nba"]), "closedTime": "2026-01-01"})

    def test_slim_then_classify_ok(self):
        self.assertEqual(classify(slim({**mk("Will A win?", ["nba"]), "endDate": "x"}))[0], "scheduled")

    def test_sample_sizes_and_seed(self):
        ms = [mk(f"Game {i}?", ["nba" if i % 2 else "nfl"]) for i in range(100)]
        ms += [mk(f"Event {i} by March 2026?", ["politics" if i % 2 else "crypto"]) for i in range(100)]
        ms += [mk(f"Who wins thing {i}?", ["culture"]) for i in range(100)]
        rows = sample(ms)
        counts = {c: sum(r[1] == c for r in rows) for c in ("scheduled", "by-date", "unclassified")}
        self.assertEqual(counts, {"scheduled": 40, "by-date": 40, "unclassified": 20})
        self.assertEqual([r[0]["id"] for r in rows], [r[0]["id"] for r in sample(ms)])
        sched_tags = [r[0]["events"][0]["tags"][0]["slug"] for r in rows if r[1] == "scheduled"]
        self.assertEqual(sched_tags.count("nba"), 20)  # round-robin across tags


if __name__ == "__main__":
    unittest.main()

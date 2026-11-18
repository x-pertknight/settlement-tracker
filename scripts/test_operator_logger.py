"""Offline tests for operator_logger.py: fake RPC, no network."""
import json, os, sys, tempfile, unittest
import operator_logger as ol

ADAPTER = "0x65070be91477460d8a7aeeb94ef92fe056c2f2a7"
FLAG = ol.TOPICS["adapter"]["QuestionFlagged"]
RESOLVED = ol.TOPICS["adapter"]["QuestionResolved"]
QID = "0x" + "ab" * 32


def log(topic, block, tx, idx):
    return {"topics": [topic, QID], "blockNumber": hex(block), "transactionHash": tx,
            "logIndex": hex(idx), "data": "0x" + "00" * 32}


ORACLE = "0x2c0367a9db231ddebd88a94b4f6461a6e47c58b1"
ANC = b"q: title: Test market?"


def oracle_log(topic, block, tx, idx):
    words = ["00" * 32, format(1_700_000_000, "064x"), format(4 * 32, "064x"), format(10**18, "064x"),
             format(len(ANC), "064x"), ANC.hex().ljust(64, "0")]
    return {"topics": [topic, "0x" + "0" * 24 + ADAPTER[2:], "0x" + "11" * 32, "0x" + "22" * 32],
            "blockNumber": hex(block), "transactionHash": tx, "logIndex": hex(idx), "data": "0x" + "".join(words)}


class FakeChain:
    """eth_blockNumber -> head; eth_getLogs -> fixed logs on ADAPTER within the range."""
    def __init__(self, head=1000, fail_head=False):
        self.head, self.fail_head = head, fail_head
        self.logs = [log(FLAG, 990, "0xf1", 3), log(RESOLVED, 995, "0xr1", 1)]
        self.oracle_logs = [oracle_log(ol.TOPICS["oracle"]["ProposePrice"], 991, "0xp1", 7),
                            oracle_log(ol.TOPICS["oracle"]["DisputePrice"], 992, "0xd1", 8)]

    def __call__(self, method, params):
        if method == "eth_blockNumber":
            return {"error": "timeout"} if self.fail_head else {"result": hex(self.head)}
        if method == "eth_getBlockByNumber":
            return {"result": {"timestamp": hex(1_700_000_000)}}
        q = params[0]
        a, b = int(q["fromBlock"], 16), int(q["toBlock"], 16)
        if q["address"] == ADAPTER:
            return {"result": [l for l in self.logs if a <= int(l["blockNumber"], 16) <= b]}
        if q["address"] == ORACLE:
            return {"result": [l for l in self.oracle_logs if a <= int(l["blockNumber"], 16) <= b]}
        return {"result": []}


class TestLogger(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.state = os.path.join(self.dir, "state.json")
        ol.PACE = 0
        ol._bts.clear()

    def run_logger(self, chain):
        ol.rpc = chain
        sys.argv = ["operator_logger.py", self.dir]
        ol.main()

    def event_lines(self):
        out = []
        for f in os.listdir(self.dir):
            if f.startswith("events-"):
                out += open(os.path.join(self.dir, f)).read().splitlines()
        return out

    def set_last_block(self, n):
        json.dump({"last_block": n}, open(self.state, "w"))

    def test_rewind_writes_no_duplicates(self):
        self.set_last_block(900)
        self.run_logger(FakeChain())
        self.assertEqual(len(self.event_lines()), 2)          # flag + oracle dispute kept; resolved, proposal only counted
        self.set_last_block(800)                               # simulate a gap rewind
        self.run_logger(FakeChain())
        self.assertEqual(len(self.event_lines()), 2)          # no duplicate lines
        self.assertEqual(json.load(open(self.state))["last_block"], 1000)

    def test_oracle_dispute_kept_proposal_counted(self):
        self.set_last_block(900)
        self.run_logger(FakeChain())
        recs = [json.loads(x) for x in self.event_lines()]
        disputes = [r for r in recs if r["event"] == "DisputePrice"]
        self.assertEqual(len(disputes), 1)
        d = disputes[0]
        self.assertEqual(d["requester"], ADAPTER)
        self.assertEqual(d["request_timestamp"], 1_700_000_000)
        self.assertEqual(d["proposed_price"], str(10**18))
        self.assertEqual(bytes.fromhex(d["ancillary_hex"][2:]), ANC)
        self.assertFalse(any(r["event"] == "ProposePrice" for r in recs))
        self.set_last_block(800)
        self.run_logger(FakeChain())
        self.assertEqual(sum(1 for x in self.event_lines() if "DisputePrice" in x), 1)

    def test_head_failure_exits_cleanly_state_unchanged(self):
        self.set_last_block(900)
        before = open(self.state).read()
        with self.assertRaises(SystemExit) as cm:
            self.run_logger(FakeChain(fail_head=True))
        self.assertEqual(cm.exception.code, 1)
        self.assertEqual(open(self.state).read(), before)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "errors.jsonl")))

    def test_corrupt_state_is_not_overwritten(self):
        open(self.state, "w").write('{"last_block": 9')     # truncated write
        with self.assertRaises(SystemExit):
            self.run_logger(FakeChain())
        self.assertEqual(open(self.state).read(), '{"last_block": 9')

    def test_atomic_save_leaves_no_temp(self):
        ol.save_state(self.state, {"last_block": 5})
        self.assertEqual(json.load(open(self.state))["last_block"], 5)
        self.assertFalse(os.path.exists(self.state + ".tmp"))

    def test_truncated_event_line_is_skipped(self):
        with open(os.path.join(self.dir, "events-2026-11.jsonl"), "w") as f:
            f.write('{"tx": "0xa", "log_index": 1}\n{"tx": "0xb", "log_')
        self.assertEqual(ol.seen_keys(self.dir), {("0xa", 1)})


if __name__ == "__main__":
    unittest.main()

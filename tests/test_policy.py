import json
import unittest
from pathlib import Path

from custody.policy import APPROVE, DENY, PENDING, allocation_check, evaluate, parse_time

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
POLICY = json.loads((EXAMPLES / "policy.json").read_text(encoding="utf-8"))
DATA = json.loads((EXAMPLES / "requests.json").read_text(encoding="utf-8"))
NOW = parse_time("2026-10-06T12:00:00Z")


def run(request_id):
    request = next(r for r in DATA["requests"] if r["id"] == request_id)
    return evaluate(request, POLICY, NOW, DATA["history"])


class DecisionTests(unittest.TestCase):
    EXPECTED = {
        "W-01": APPROVE,   # small hot withdrawal, allowlisted, one valid approver
        "W-02": DENY,      # above the hot per-transaction limit
        "W-03": DENY,      # would break the hot 24-hour limit
        "W-04": PENDING,   # warm: only 1 of 2 approvals, no risk approver
        "W-05": APPROVE,   # warm: operations + risk
        "W-06": DENY,      # destination not allowlisted
        "W-07": PENDING,   # address added 16 h ago, cooling period is 48 h
        "W-08": PENDING,   # requester approved their own request
        "W-09": PENDING,   # cold: time lock not yet passed
        "W-10": APPROVE,   # cold: quorum met and time lock passed
        "W-11": DENY,      # blocklisted destination
    }

    def test_every_example_request(self):
        for request_id, expected in self.EXPECTED.items():
            with self.subTest(request=request_id):
                self.assertEqual(run(request_id)["decision"], expected)

    def test_reasons_are_explained(self):
        self.assertTrue(any("per-transaction limit" in r for r in run("W-02")["reasons"]))
        self.assertTrue(any("last 24 h" in r for r in run("W-03")["reasons"]))
        self.assertTrue(any("role 'risk'" in r for r in run("W-04")["reasons"]))
        self.assertTrue(any("cooling period" in r for r in run("W-07")["reasons"]))
        self.assertTrue(any("cannot also approve" in r for r in run("W-08")["reasons"]))
        self.assertTrue(any("time lock" in r for r in run("W-09")["reasons"]))
        self.assertTrue(any("blocklist" in r for r in run("W-11")["reasons"]))

    def test_old_history_outside_24h_is_ignored(self):
        # 165k in the last 24 h + 20k = 185k <= 200k; the 90k from two days ago doesn't count
        self.assertEqual(run("W-01")["reasons"], [])

    def test_duplicate_approvals_count_once(self):
        request = dict(next(r for r in DATA["requests"] if r["id"] == "W-05"), approvals=["alice", "alice"])
        self.assertEqual(evaluate(request, POLICY, NOW, [])["decision"], PENDING)

    def test_unknown_tier_denied(self):
        request = dict(DATA["requests"][0], tier="lukewarm")
        self.assertEqual(evaluate(request, POLICY, NOW)["decision"], DENY)


class AllocationTests(unittest.TestCase):
    def test_hot_wallet_over_limit(self):
        balances = json.loads((EXAMPLES / "balances.json").read_text(encoding="utf-8"))
        breaches = allocation_check(balances, POLICY)
        self.assertEqual([b["tier"] for b in breaches], ["hot"])
        # hot is 3.5 % of 100M, limit 2 % -> move 1.5M
        self.assertAlmostEqual(breaches[0]["excess_usd"], 1_500_000)

    def test_balanced(self):
        self.assertEqual(allocation_check({"hot": 1, "warm": 5, "cold": 94}, POLICY), [])


if __name__ == "__main__":
    unittest.main()

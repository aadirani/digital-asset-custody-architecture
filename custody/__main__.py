"""Command line:
  python -m custody evaluate   --policy examples/policy.json --requests examples/requests.json --now 2026-10-06T12:00:00Z
  python -m custody allocation --policy examples/policy.json --balances examples/balances.json
"""

import argparse
import json
from pathlib import Path

from .policy import allocation_check, evaluate, parse_time


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_evaluate(a):
    policy, data = load(a.policy), load(a.requests)
    now = parse_time(a.now)
    for request in data["requests"]:
        result = evaluate(request, policy, now, data.get("history", []))
        print(f"{result['id']:<6} {request['tier']:<5} ${float(request['amount_usd']):>11,.0f}  {result['decision']}")
        for reason in result["reasons"]:
            print(f"         - {reason}")


def cmd_allocation(a):
    policy, balances = load(a.policy), load(a.balances)
    total = sum(balances.values())
    for tier, value in balances.items():
        limit = policy["tiers"][tier].get("max_share_of_aum", 1.0)
        print(f"{tier:<5} ${value:>14,.0f}  {value / total:6.1%}  (max {limit:.0%})")
    breaches = allocation_check(balances, policy)
    for b in breaches:
        print(f"REBALANCE: move ${b['excess_usd']:,.0f} out of {b['tier']} to a colder tier")
    if not breaches:
        print("All tiers within their limits.")


def main(argv=None):
    p = argparse.ArgumentParser(prog="custody", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    e = sub.add_parser("evaluate", help="check withdrawal requests against the policy")
    e.add_argument("--policy", default="examples/policy.json")
    e.add_argument("--requests", default="examples/requests.json")
    e.add_argument("--now", required=True, help="evaluation time, e.g. 2026-10-06T12:00:00Z")
    e.set_defaults(func=cmd_evaluate)
    r = sub.add_parser("allocation", help="check hot/warm/cold balances against tier limits")
    r.add_argument("--policy", default="examples/policy.json")
    r.add_argument("--balances", default="examples/balances.json")
    r.set_defaults(func=cmd_allocation)
    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()

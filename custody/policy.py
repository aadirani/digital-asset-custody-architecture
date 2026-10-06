"""Withdrawal policy engine.

Every withdrawal request is checked BEFORE anything is signed:
  1. destination: blocklist, allowlist, cooling period for newly added addresses
  2. limits: per-transaction and rolling 24-hour limits for the wallet tier
  3. approvals: quorum and required roles; the requester can't approve their own request
  4. time lock: cold-storage withdrawals wait a fixed time after the request

Result: APPROVE, PENDING (waiting for approvals or time) or DENY, always with reasons.
This is a reference model of the logic, not a production system. No keys, no blockchain access.
"""

from datetime import datetime, timedelta

APPROVE, PENDING, DENY = "APPROVE", "PENDING", "DENY"


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _hours(delta):
    return delta.total_seconds() / 3600


def evaluate(request, policy, now, history=()):
    """Return {"id", "decision", "reasons"} for one withdrawal request.

    history: already executed withdrawals [{"tier", "amount_usd", "executed_at"}] for velocity limits.
    """
    tier_name = request["tier"]
    tier = policy["tiers"].get(tier_name)
    if tier is None:
        return {"id": request["id"], "decision": DENY, "reasons": [f"unknown wallet tier '{tier_name}'"]}

    deny, pending = [], []
    amount = float(request["amount_usd"])
    destination = request["destination"]

    # 1. Destination
    if destination in policy.get("blocklist", []):
        deny.append("destination is on the blocklist")
    allowed = {a["address"]: a for a in policy.get("allowlist", [])}
    if destination not in allowed:
        deny.append("destination is not on the allowlist")
    else:
        age = _hours(now - parse_time(allowed[destination]["added_at"]))
        cooling = policy.get("allowlist_cooling_hours", 0)
        if age < cooling:
            pending.append(f"address was allowlisted {age:.0f} h ago; usable after the {cooling} h cooling period")

    # 2. Limits
    max_tx = tier.get("max_per_tx_usd")
    if max_tx is not None and amount > max_tx:
        deny.append(f"amount ${amount:,.0f} exceeds the {tier_name} per-transaction limit of ${max_tx:,.0f}")
    max_day = tier.get("max_24h_usd")
    if max_day is not None:
        since = now - timedelta(hours=24)
        spent = sum(float(h["amount_usd"]) for h in history
                    if h["tier"] == tier_name and parse_time(h["executed_at"]) > since)
        if spent + amount > max_day:
            deny.append(f"would bring {tier_name} withdrawals in the last 24 h to ${spent + amount:,.0f}, "
                        f"above the ${max_day:,.0f} limit")

    # 3. Approvals (maker-checker: the requester's own approval never counts)
    roles = policy.get("approvers", {})
    valid = []
    for name in dict.fromkeys(request.get("approvals", [])):  # removes duplicates, keeps order
        if name == request["requested_by"]:
            pending.append(f"{name} requested this withdrawal and cannot also approve it")
        elif name not in roles:
            pending.append(f"{name} is not an authorised approver")
        else:
            valid.append(name)
    need = tier["approvals"]
    if len(valid) < need["total"]:
        pending.append(f"{len(valid)} of {need['total']} required approvals")
    for role, count in need.get("roles", {}).items():
        have = sum(1 for n in valid if roles[n] == role)
        if have < count:
            pending.append(f"needs {count} approval(s) from role '{role}', has {have}")

    # 4. Time lock
    lock = tier.get("time_lock_hours", 0)
    waited = _hours(now - parse_time(request["requested_at"]))
    if waited < lock:
        ready = parse_time(request["requested_at"]) + timedelta(hours=lock)
        pending.append(f"time lock: executable from {ready.isoformat().replace('+00:00', 'Z')}")

    decision = DENY if deny else PENDING if pending else APPROVE
    return {"id": request["id"], "decision": decision, "reasons": deny + pending}


def allocation_check(balances_usd, policy):
    """Compare each tier's share of total assets with its maximum.

    Returns a list of {"tier", "share", "max_share", "excess_usd"} for tiers above their limit:
    the excess should be moved to a colder tier.
    """
    total = sum(balances_usd.values())
    breaches = []
    for name, balance in balances_usd.items():
        limit = policy["tiers"][name].get("max_share_of_aum", 1.0)
        share = balance / total if total else 0
        if share > limit:
            breaches.append({"tier": name, "share": share, "max_share": limit,
                             "excess_usd": balance - limit * total})
    return breaches

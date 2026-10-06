# Institutional Digital Asset Custody Architecture

![tests](https://github.com/aadirani/digital-asset-custody-architecture/actions/workflows/tests.yml/badge.svg)

A reference design for how an institution can **hold and move crypto assets safely**, plus a working **withdrawal-policy engine** that decides, before anything is signed, whether a withdrawal is approved, pending or denied, and why.

## The idea in one paragraph

Crypto transfers can't be reversed, and whoever controls the keys controls the money. So institutions keep most assets **offline (cold)**, a small amount **online (hot)** for daily withdrawals, and something in between (**warm**). Every withdrawal goes through a **policy engine** first: is the destination pre-approved? Is the amount within limits? Have enough of the *right* people approved, and not the person who asked? Has the waiting period passed? Only then do the signers, using techniques such as **MPC** or **multisig**, sign the exact transaction that was approved.

## Try the policy engine

Needs Python 3.9+, nothing to install. All names, addresses and limits are fictional.

```bash
python -m custody evaluate --now 2026-10-06T12:00:00Z
python -m custody allocation
```

Part of the output:

```
W-01   hot   $     20,000  APPROVE
W-02   hot   $     80,000  DENY
         - amount $80,000 exceeds the hot per-transaction limit of $50,000
         - would bring hot withdrawals in the last 24 h to $245,000, above the $200,000 limit
W-04   warm  $    300,000  PENDING
         - 1 of 2 required approvals
         - needs 1 approval(s) from role 'risk', has 0
W-08   hot   $      5,000  PENDING
         - alice requested this withdrawal and cannot also approve it
         - 0 of 1 required approvals
W-09   cold  $  5,000,000  PENDING
         - time lock: executable from 2026-10-07T09:00:00Z
```

## What's inside

| Path | What it is |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Wallet tiers, architecture and transaction lifecycle diagrams, MPC vs multisig vs HSM, 7 ADRs, STRIDE threat model, risks, cost categories |
| [custody/policy.py](custody/policy.py) | The policy engine and the tier-allocation check |
| [examples/](examples/) | Example policy, 11 withdrawal requests covering every outcome, and balances |
| [docs/code-walkthrough.md](docs/code-walkthrough.md) | Plain-language explanation |

## Scope

This is a study design and a model of the policy logic. It holds no keys, connects to no blockchain, and doesn't describe any real institution's setup.

# Code walkthrough

A plain-language guide for explaining this project in an interview.

## Vocabulary

- **Hot / warm / cold wallet:** how "online" the keys are. Hot keys sign automatically, cold keys are offline.
- **MPC (multi-party computation):** the key exists only as shares held by different parties, and a threshold of them signs together without ever rebuilding the full key.
- **Multisig:** the blockchain itself demands M-of-N separate signatures.
- **Allowlist:** pre-approved destination addresses.
- **Maker-checker:** the person who asks for something can't be the person who approves it.
- **Quorum:** the minimum number of approvals needed.
- **Time lock:** a forced waiting period before execution.

## `custody/policy.py`

**`evaluate(request, policy, now, history)`** runs four groups of checks and collects reasons in two lists, `deny` and `pending`:

1. **Destination:** on the **blocklist** → deny. Not on the **allowlist** → deny. On the allowlist but added less than 48 hours ago → pending (cooling period).
2. **Limits:** above the tier's per-transaction limit → deny. It also adds up the same tier's withdrawals in the **last 24 hours** from `history` (the "velocity" check). If this one would push the total over the daily limit → deny.
3. **Approvals:** duplicates are removed, the requester's own approval is ignored (maker-checker), and unknown names are ignored. Then it checks the **total** (e.g. 2) and the **roles** (e.g. at least one from `risk`). Missing ones → pending.
4. **Time lock:** if the tier has one (cold = 24 h) and it hasn't passed → pending, with the exact time it becomes executable.

**The result:** any deny reason → **DENY**. Otherwise any pending reason → **PENDING**. Otherwise → **APPROVE**. The reasons are always returned, so a person can see exactly why.

**`allocation_check(balances, policy)`** works out each tier's share of the total. If the hot wallet holds 3.5% but may hold only 2%, it reports the excess ($1.5M of $100M) that should move to a colder tier.

## `examples/`

- `policy.json`: three tiers with limits, approvers and their roles, allowlist (with dates added), blocklist.
- `requests.json`: 11 requests, each built to trigger one rule, plus recent withdrawal history.
- `balances.json`: tier balances for the allocation check.

## The tests

Each of the 11 example requests has an expected decision (`W-01` approve, `W-02` deny over limit, … `W-11` deny blocklisted), and the reasons are checked too. Extra tests cover: history older than 24 h being ignored, duplicate approvals counting once, an unknown tier being denied, and the allocation maths.

## Likely interview questions

- **"MPC or multisig?"** It depends. MPC works across many chains and allows signer changes without moving funds. Multisig is transparent on-chain but differs per chain. A hybrid with MPC for operational wallets and offline keys for cold storage is common (ADR-002).
- **"What would have prevented incidents where signers approved a malicious transaction?"** Each signer verifies the exact payload on an independent device rather than trusting a shared web interface (ADR-005, §4 in ARCHITECTURE.md).
- **"Why a cooling period on new addresses?"** Attackers who get in often add their own address and withdraw immediately. A 48-hour delay gives monitoring time to catch it (ADR-004).
- **"Why can't the requester approve?"** So one person, or one stolen account, can never move funds alone.
- **"Have you run custody in production?"** Be accurate: this is a study design with a working model of the policy rules, built from hands-on trading and OTC experience.

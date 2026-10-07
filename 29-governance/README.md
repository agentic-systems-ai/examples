# 29 · Governance for agents: what policy and compliance teams need

Companion code for the post [Governance for agents](https://www.agenticsystems.ai/blog/governance-for-agents/).

An **agent register** with evidence checks. No API calls, no dependencies.

- `agents.json` declares each agent: owner, purpose, users, pinned model, data, tools (with their effect: read, internal, external, money, destructive), risk tier, incident contact, and controls.
- Each control names its **evidence** as `path/in/examples::text`, a file in this repository and something it must contain, such as a function.
- `register.py` maps controls to the eleven practice categories in ISACA's 2026 *Cybersecurity Recommendations for Securing AI Agents*, checks the categories each risk tier requires, verifies every piece of evidence exists, and flags findings such as an unpinned model.

```bash
python register.py              # text report
python register.py --markdown   # a register entry to paste into a wiki
```

The two sample agents:

- **refund-agent** (medium risk), the agent from post #25. Every control links to working code from earlier posts: delegated tokens (24), the approval policy (22), the eval gate (27), shadow mode and the kill switch (25), traces and audit logs (15, 24). → READY FOR REVIEW
- **sales-followup-agent** (high risk): no owner or incident contact, model set to "latest", two controls whose evidence doesn't exist, ten of eleven categories uncovered. → NOT READY

The checker proves that evidence *exists*, not that a control is *adequate*. That's still the reviewer's job.

## Things to try

1. **Register one of your agents.** Fill in `agents.json` honestly and see what's missing.
2. **Tighten the tiers.** Change `REQUIRED_BY_TIER` to match your organization's policy.
3. **Wire it into CI** so a pull request that adds an agent without a complete register entry fails.

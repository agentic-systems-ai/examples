# 25 · Rolling out agents safely: shadow mode, canaries and kill switches

Companion code for the post [Rolling out agents safely](https://www.agenticsystems.ai/blog/rolling-out-agents/).

A refund agent (Claude, with real lookups and three actions: `issue_refund`, `deny_request`, `escalate`) goes through a staged rollout:

1. **Shadow mode** (`python rollout.py shadow`): the agent works 20 historical tickets from `data.py`. Lookups are real; actions are recorded, not executed. Each proposal is compared with what the support team actually did: **match**, **safer** (pays less or escalates) or **riskier** (pays more). The data includes three tickets where people departed from the written policy: two goodwill exceptions and one mistake.
2. **Gate** (`python rollout.py gate`): promotion criteria written before the run: at least 20 tickets, at least 80% agreement, zero riskier proposals, under $0.10 per ticket.
3. **Canary** (`python rollout.py canary`): the agent acts for real on a stable 15% slice of 100 new tickets. Every action passes `guarded_execute()`, which checks a **kill switch** (the `KILL_SWITCH` file) and **tripwires**: a cap on any single refund, and a refund *rate* far above what shadow mode measured. A tripwire flips the switch for every instance.

`python rollout.py canary --bad-change` adds an innocent-looking prompt edit ("customer happiness is our top priority… refund in full") to show the tripwires catching a behaviour change.

## Run it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...

python rollout.py all                    # shadow, gate, and (if the gate passes) canary
python rollout.py canary --bad-change    # the regression the tripwires are for
```

In a scripted test of `--bad-change`, the refund rate hit 100%, the rate tripwire switched the agent off on the 8th action, and the rest of the canary went back to people. Seven bad refunds went out first: tripwires limit damage, they don't prevent it.

## Things to try

1. **Make the gate stricter** and read which tickets block promotion.
2. **Change the base rate.** Add more refundable tickets and watch the rate tripwire's false-alarm risk; retune it on the shadow data.
3. **Shadow the bad change.** Run `shadow` with `BAD_CHANGE` appended to the prompt and see how many riskier proposals it would have shown before it ever acted.

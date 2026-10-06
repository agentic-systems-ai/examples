# 03 · Context is a budget

Companion code for the post [Context is a budget: a practical guide to context engineering](https://www.agenticsystems.ai/blog/context-is-a-budget/).

An agent has to read 24 incident reports (about 45k tokens in total) to answer one question: *which service had the most downtime, how much, and what usually caused it?* You run the same task under three context strategies and compare what each one costs.

| Strategy | What happens to old tool results |
|---|---|
| `naive` | Everything stays. The context grows with every report read. |
| `clear` | The **server** drops old tool results once the context passes 12k tokens, keeping the last two. Our message list stays append-only. |
| `compact` | Above 15k tokens, the agent writes a progress summary, then **restarts** from task + summary + saved notes. |

In all three, the agent saves a one-line note per report with a `save_note` tool. The notes live outside the context window, which is why clearing and compaction don't lose the facts.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."

python agent.py --strategy naive
python agent.py --strategy clear
python agent.py --strategy compact
```

The first run generates `workspace/` with a fixed random seed, so everyone gets the same 24 reports and the same correct answer.

Each step prints how many tokens the model read, how many of those came from the cache, and a bar for the context size. The run ends with a summary line:

```
=== clear: peak context … tokens | read … (of which cached …) | wrote … | est. $…
ground truth: auth, 760 minutes, mostly database failover
```

The cost estimate uses Claude Opus 5.5 prices as of October 2026, set in `PRICE` in `agent.py`. Check current pricing.

## Our results

One run each against Claude Opus 5.5; all three answered correctly:

| Strategy | Peak context | Tokens read | From cache | Est. cost |
|---|---|---|---|---|
| naive | 72,432 | 546,693 | 87% | $0.51 |
| clear | 11,620 | 274,673 | 38% | $0.96 |
| compact | 25,456 | 204,873 | 74% | $0.38 |

`clear` had the smallest context and the *highest* cost. With the deliberately low threshold, the server re-cleared on every request, the cache kept rebuilding, and some results were cleared before the agent had noted them. In real use, clear rarely and in big chunks (raise `CLEAR_AT`, keep more results, and consider `clear_at_least`).

## What to look for

1. **Peak context:** `naive` keeps climbing, while `clear` and `compact` level off.
2. **Cached share:** with a stable system prompt and an append-only history, most tokens on most steps are cache reads, which are far cheaper. Watch what happens to the cache on the step right after clearing or compaction.
3. **Correctness:** compare each answer with the ground truth. Then delete the `save_note` tool and the system-prompt line about notes, and run `clear` again to see what clearing does without notes.

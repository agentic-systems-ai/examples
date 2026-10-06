# 16 · Small models, big systems

Companion code for the post [Small models, big systems: routing for agent cost](https://www.agenticsystems.ai/blog/routing-for-agent-cost/).

Twelve tasks with exact answers in three tiers (`tasks.py`): four **easy** (classify, extract), four **medium** (a little reasoning or arithmetic), four **hard** (multi-step, constraints). `route.py` runs them under four strategies and reports accuracy and cost from the actual token usage:

| Strategy | What it does |
|---|---|
| `opus` | Claude Opus 5.5 on everything, at medium effort |
| `opus-low` | Claude Opus 5.5 on everything, at **low effort**: the cheapest change to try first |
| `haiku` | Claude Haiku 4.5 on everything |
| `routed` | Haiku rates each task's difficulty; easy goes to Haiku, medium to Sonnet 5.5 (low effort), hard to Opus 5.5. The router's own cost is included. |

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."

python route.py --strategy opus
python route.py --strategy opus-low
python route.py --strategy haiku
python route.py --strategy routed
```

Each run prints, per task, which model answered and what it cost, then a summary:

```
=== routed: …/12 correct (easy …/4, medium …/4, hard …/4) | total $…
```

Prices are list prices as of October 2026, set in `PRICE` in `route.py`. Check current pricing. Twelve tasks is a *demonstration*, not a benchmark. Run each strategy more than once (see post #12) before drawing conclusions.

## Things to try

1. **Find the router's mistakes.** Print the router's rating for each task. A hard task routed to Haiku is the expensive failure mode.
2. **Add your own tasks** to `tasks.py`, with exact answers, from your real workload. Routing only pays off if your traffic really has an easy tier.
3. **Count the cache.** The router adds a model call to every task. In a long agent conversation, switching models also loses the prompt cache, which is model-specific. Measure that before routing *within* a conversation.

# 12 · Evals for agents

Companion code for the post [Evals for agents: pass@k is lying to you](https://www.agenticsystems.ai/blog/evals-for-agents/).

| File | What it does |
|---|---|
| `metrics.py` | **pass@k** (at least one of k trials succeeds) and **pass^k** (all k succeed), using the standard unbiased estimators, plus a rough confidence interval. Run it on its own to see a worked, *hypothetical* example. |
| `suite.py` | Runs the six CRM questions from [04-tools](../04-tools) as an eval: repeated, **isolated** trials (each a fresh conversation), a **code-based grader** that checks the final answer, results saved to `results.json`, and a pass@k / pass^k table. |

## Run it

```bash
python metrics.py                        # the maths, on hypothetical numbers (no API key needed)

python -m venv .venv
source .venv/bin/activate                # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...             # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."

python suite.py --trials 5               # 6 tasks x 5 trials = 30 agent runs
python suite.py --from results.json      # recompute the table later, no API calls
```

The output shows each task's trials (`✓✗✓✓✓`) and then a table like this:

```
 k   pass@k   pass^k
 1      …        …
 5      …        …
```

pass@k only goes up as k grows. pass^k only goes down. The gap between them is how *inconsistent* your agent is.

## Things to try

1. **Read the failures.** Open `results.json` and read every failed answer. Is the agent wrong, or is the grader too strict? Fix whichever it is. That loop *is* evaluation.
2. **Run it twice.** Compare the two pass@1 numbers. The difference between two identical runs is your noise floor; any "improvement" smaller than that isn't one.
3. **Change something real.** Switch `crm.TOOLSETS["v2"]` to `"v1"` in `trial()` (the API-wrapper tools from post #4) and compare pass^5.

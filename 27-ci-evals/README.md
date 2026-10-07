# 27 · Testing agents in CI

Companion code for the post [Testing agents in CI](https://www.agenticsystems.ai/blog/testing-agents-in-ci/).

An eval gate for an order-support agent:

| File | What it is |
|---|---|
| `agent_under_test.py` | The agent: five tools, prompt loaded from `prompts/` |
| `prompts/system.md` | The prompt under test |
| `prompts/system_regressed.md` | A "harmless" edit: a friendlier opening, and two policy lines tidied away |
| `suite.py` | Eight regression tasks, each with a grader in code that checks what the agent *did* and says why it failed |
| `ci_eval.py` | The gate: k trials per task, budget cap, comparison with the baseline, exit code for CI, summary for the job page |
| `workflow.example.yml` | A GitHub Actions workflow to copy into your repository as `.github/workflows/agent-evals.yml` |

The gate fails the build on a **hard regression** (a task that passed k/k on the baseline passes 0/k now) or a **soft regression** (the overall pass rate drops more than chance explains, one-sided 95%). Smaller changes are warnings. An incomplete run (budget stop or infrastructure errors) fails, and is never written as a baseline.

## Run it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...

python ci_eval.py --write-baseline                     # record the baseline from prompts/system.md
python ci_eval.py                                      # compare the same prompt: should pass
python ci_eval.py --prompt system_regressed.md         # should fail, naming the broken behaviours
```

Options: `--k` trials per task (default 3), `--budget` dollars per run (default 2.00), `--workers` parallel trials (default 4).

A scripted test of the regressed prompt produced:

```
## Agent eval gate: FAIL
- :x: hard regression: 'address-shipped' passed 3/3 on main, 0/3 now
- :x: hard regression: 'return-late' passed 3/3 on main, 0/3 now
- :x: soft regression: pass rate 100% on main -> 75% (drop 25% > noise 16%)
```

## Things to try

1. **Break something subtler.** Remove only the tracking-number rule and see whether the gate catches it, and at what k.
2. **Upgrade the model.** Change `MODEL` in `agent_under_test.py` and run the gate: a model change is a change like any other.
3. **Add a capability suite** of harder tasks that runs nightly, and graduate the ones that reach 100%.

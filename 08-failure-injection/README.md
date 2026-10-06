# 08 · Why multi-agent systems fail

Companion code for the post [Why multi-agent systems fail](https://www.agenticsystems.ai/blog/why-multi-agent-systems-fail/).

Three small two-agent setups, each reproducing one failure mode from the **MAST** taxonomy (*Why Do Multi-Agent LLM Systems Fail?*, Cemri et al.). Each comes in a `broken` and a `fixed` variant, and plain code grades the result.

| Scenario | MAST failure mode | Broken | Fixed |
|---|---|---|---|
| `termination` | FM-1.5 Unaware of termination conditions | A reviewer is asked to "suggest improvements", so it never runs out of suggestions | The reviewer gets acceptance criteria and must approve once they're met |
| `withholding` | FM-2.4 Information withholding | The lead hands off a one-line brief; the "username must be lowercase" rule gets lost | The hand-off has a `constraints` field and includes the original request verbatim |
| `verification` | FM-3.2 / 3.3 No or incorrect verification | The verifier checks that the answer *looks* plausible | The verifier gets the source data and must recompute the answer |

The verification scenario uses **failure injection**: the worker is plain code that deliberately drops one row, so the question is only whether the verifier notices. Injecting known faults is how you test a checker. You can't wait for the model to make a mistake on cue.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."

python failures.py --scenario termination  --variant broken
python failures.py --scenario termination  --variant fixed
python failures.py --scenario withholding  --variant broken
python failures.py --scenario withholding  --variant fixed
python failures.py --scenario verification --variant broken
python failures.py --scenario verification --variant fixed
```

Each run prints what the agents did and ends with `=== PASS` or `=== FAIL`.

**Run each several times.** Our results over six runs each against Claude Opus 5.5:

| Scenario | Broken variant failed | Fixed variant failed |
|---|---|---|
| `termination` | 3 of 6 (rewrites grew to 164–176 words and were approved anyway) | 0 of 6 |
| `withholding` | 0 of 6 (the lead applied the lowercase rule itself, inside its brief) | 0 of 6 |
| `verification` | 1 of 6 (approved the wrong total) | 0 of 6 |

A current model often compensates for a weak design, and sometimes fails in a *different* way than the one you planned for. That's the lesson: a design that relies on the model happening to do the right thing will pass your demo and fail in production. The fixed variants are guarantees, not averages.

## Things to try

1. In `verification`, replace the model verifier with three lines of code that re-sum `ORDERS`. When a check *can* be done in code, it should be.
2. In `withholding`, keep the one-line brief but give the worker's `create_account` tool a description that states the lowercase rule. Which fix is more robust?
3. In `termination`, keep the vague reviewer prompt but lower `max_rounds` to 2. A round limit stops the loop, but does it produce a good blurb?

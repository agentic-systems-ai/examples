# 02 · Workflows vs. agents: five patterns you actually need

Companion code for the post [Workflows vs. agents: five patterns you actually need](https://www.agenticsystems.ai/blog/five-workflow-patterns/).

All five patterns work on the same job: answering a support inbox for **Larkspur**, a fictional SaaS product. The sample tickets and the support policy are in [`tickets.py`](tickets.py). Each script prints what each step decided, then a usage line, so you can compare the patterns on cost and speed:

```
--- routing: 2 model calls, <input> input + <output> output tokens, <seconds>s ---
```

| Script | Pattern | Default ticket |
|---|---|---|
| `p1_chaining.py` | Prompt chaining: extract → code gate → draft | `billing` |
| `p2_routing.py` | Routing: classify → specialist prompt | `bug` |
| `p3_parallel.py` | Parallelization: sectioned review + majority vote | `bug` |
| `p4_orchestrator.py` | Orchestrator-workers: plan → parallel workers → synthesize | `mixed` |
| `p5_evaluator.py` | Evaluator-optimizer: draft → grade → revise loop | `mixed` |

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."

python p2_routing.py             # default ticket
python p2_routing.py billing     # or pick one: billing | bug | mixed
```

## How the code is organized

- `common.py` has one `ask()` helper. It makes one model call and returns either text or a validated Pydantic object, and it keeps a running count of calls and tokens. Every pattern is built only from `ask()`, plain Python and `asyncio.gather`. No framework is involved.
- Steps default to `effort="low"`. Steps that need real judgment, such as drafting the final reply or grading, ask for `"medium"`.

## Things to try

1. Run every pattern on the `mixed` ticket and compare the usage lines.
2. In `p1_chaining.py`, remove the invoice number from the billing ticket and watch the code gate stop the chain.
3. In `p3_parallel.py`, the sample draft promises a fix "by Friday". Check that the policy reviewer catches it.
4. In `p5_evaluator.py`, set `MAX_ROUNDS = 1` and compare reply quality.

# 19 · Inside a coding agent

Companion code for the post [Inside a coding agent](https://www.agenticsystems.ai/blog/inside-a-coding-agent/).

A coding agent in about 170 lines, working on `toyrepo/`: a tiny invoicing package with a real bug, where two of four tests fail. The agent has the same kinds of tools real coding agents use:

| Tool | Why it's shaped this way |
|---|---|
| `list_files`, `read_file` (with line numbers), `search` (regex) | Explore before editing; line numbers make code easy to reference |
| `edit_file(path, old, new)` | Exact, single-occurrence string replacement: small, reviewable edits. Ambiguous matches are rejected with advice. |
| `run_tests` | Returns the *tail* of the pytest output: the summary, not pages of log |

Two rules are enforced **in code**, not in the prompt:
- the agent may not write to `tests/`
- the task counts as done only if the tests pass **and** the tests are byte-for-byte unchanged

Each run copies `toyrepo/` to `work/`, so the original is never modified.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # or: export LLM_PROVIDER=bedrock AWS_REGION=us-east-1

python agent.py
```

The output is a step-by-step trace, the agent's summary, the diff it made, and a verdict. Here's the shape from a scripted test run, which deliberately included an attempt to edit a test:

```
[step  2] run_tests({}) -> 2 failed, 2 passed
[step  4] edit_file({"path": "tests/test_invoicing.py", ...}) -> ERROR PermissionError: Editing tests is not allowed...
[step  5] edit_file({"path": "invoicing/totals.py", ...}) -> Edited invoicing/totals.py.
[step  6] run_tests({}) -> 4 passed

--- a/invoicing/totals.py
+++ b/invoicing/totals.py
-    return round(discounted * tax_rate, 2)
+    return round(discounted * (1 + tax_rate), 2)

=== DONE: tests pass=True, tests unchanged=True | 7 steps, 7 tool calls, …
```

## Things to try

1. **Make the bug harder.** Put a second, interacting bug in `discounts.py`, or a misleading comment, and watch how the exploration changes.
2. **Remove the test guard.** Delete the `tests/` check in `edit_file` and ask yourself whether you'd notice if the agent "fixed" a test instead of the code. That's why the gate also hashes the tests.
3. **Trace it.** Add the OpenTelemetry spans from post #15 and see where the steps and tokens go.

# 01 · The agent loop, from first principles

Companion code for the post [The agent loop, from first principles](https://agenticsystems.ai/blog/the-agent-loop/).

A complete agent in about 100 lines of Python, with no framework. It has:

- **three tools**: `list_files`, `read_file` and `calculate`, which work over a small sandboxed `workspace/`
- **a loop**: call the model, run any tools it asks for, append the results, and repeat until it stops asking
- **guard rails**: a step limit, tool errors returned to the model as observations, a workspace path check, and handling for refusals and truncated output

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
python agent.py "Which region had the highest Q3 revenue, and by how much did it beat the runner-up?"
```

You'll see one trace line per tool call, then the final answer:

```
[step 1] list_files({}) -> 'notes.md\nsales.csv'
[step 2] read_file({"name": "sales.csv"}) -> 'region,quarter,revenue_usd\n...'
[step 3] calculate({"expression": "214900 - 201250"}) -> '13650'
South led Q3 with $214,900, beating North (the runner-up) by $13,650.
```

The exact steps vary from run to run. That is the point of an agent: the model chooses the path.

## Things to try

1. Ask something the data can't answer ("What was Q4 revenue?") and watch the agent say so instead of guessing.
2. Ask it to read `../agent.py`. The sandbox check returns an error, and the model adapts.
3. Set `MAX_STEPS = 2` and see how the loop ends when the budget runs out.
4. Delete the `calculate` tool and compare how often the arithmetic is right.

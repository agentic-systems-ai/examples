# 06 · Stop calling tools, start writing code

Companion code for the post [Stop calling tools, start writing code](https://www.agenticsystems.ai/blog/stop-calling-tools-start-writing-code/).

One data task (*for every Lisbon customer with an open ticket, list name and total spend, then count and total them*) needs 32 tool calls: one list, then 31 profile lookups. `compare.py` runs it two ways:

| Mode | How it works | Where tool results go |
|---|---|---|
| `direct` | The model calls `list_customers` and `get_customer` as ordinary tools. | Every result enters the model's context, and is re-read on every later step. |
| `code` | The model writes Python that calls the same tools as async functions. The code runs in Anthropic's code-execution sandbox, which pauses whenever it calls one of *our* tools, so we run the tool and hand the result back. | The results go to the running code. Only what the code prints returns to the model. |

Code mode uses the Claude API's **programmatic tool calling**: add the code-execution tool, and mark your tools with `allowed_callers: ["code_execution_20260120"]`. The model's code never runs on your machine, and your tools never run in the sandbox.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."

python compare.py --mode direct
python compare.py --mode code
```

Each run prints the answer, then a summary line and the correct answer to compare against:

```
=== code: … API requests, 32 tool calls, … tokens read
ground truth: 13 customers, $10,255 combined, highest spend: Ironbridge Robotics
```

In code mode, every tool call still makes one HTTP round trip to your app (the sandbox pauses and waits for you), but the model isn't re-run between those calls. Compare `tokens read` across the two modes, not just the request counts.

## Things to try

1. **Change the city.** Lisbon has 31 customers; pick a city with fewer and watch the gap between the modes shrink.
2. **Make the task conversational.** Ask about a *single* customer. With only one or two sequential calls, code mode adds overhead and saves nothing.
3. **Read the code it wrote.** In code mode, print the `server_tool_use` block's `input["code"]` to see the program the model wrote.

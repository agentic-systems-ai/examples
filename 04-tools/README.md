# 04 · Designing tools agents can actually use

Companion code for the post [Designing tools agents can actually use](https://www.agenticsystems.ai/blog/designing-tools-for-agents/).

The same fictional CRM (240 customers, with their orders and support tickets) gets two tool sets, and a small eval scores each on six questions whose answers are known.

| | v1: "API wrapper" | v2: "agent-shaped" |
|---|---|---|
| Finding a customer | `list_customers()` returns all 240 as JSON (~37k characters) | `search_customers(query, city?, limit=5)` returns matching lines |
| Identifiers | UUIDs | readable IDs like `C-1003` |
| Customer details | separate `get_orders` and `get_tickets`, raw JSON | one `get_customer_context`, concise by default, `detailed` on request |
| Errors | raw exceptions (`KeyError: 'C-1003'`) | what went wrong and what to do next |
| Descriptions | "Get orders." | when to use the tool, what it returns, examples for each parameter |

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."

python eval.py --tools v1
python eval.py --tools v2
```

Each task prints PASS or FAIL, along with its tool calls, errors and tokens read. The last line summarizes the whole run:

```
=== v2: …/6 correct | … tool calls, … errors, … tokens per task
```

Our results against Claude Opus 5.5 (one run each): both versions got **6/6**, but v1 read **38,960 tokens per task** and v2 **2,792**. A strong model gets the right answers through a bad interface; it just costs about 14 times as much.

The grader is deliberately simple: each expected value must appear in the answer as a whole word or number. Read the printed answers to check it, and add your own tasks to `TASKS` in `eval.py`.

## Things to try

1. **Change one thing at a time.** Give v1 good descriptions but keep everything else, and measure. Then switch v2 back to raw errors and measure again.
2. **Make search fail.** Ask about "Riverside Legal LLC" and watch v2's error message steer the agent to a shorter query.
3. **Add a misleading tool.** Give v2 a third tool that overlaps `search_customers`, e.g. `find_client`, and see whether the agent's choices get worse.

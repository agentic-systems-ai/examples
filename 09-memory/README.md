# 09 · Memory that learns

Companion code for the post [Memory that learns: from CLIN to ReasoningBank](https://www.agenticsystems.ai/blog/memory-that-learns/).

An agent answers a stream of six different questions about the CRM from earlier posts. The tools have one realistic gotcha: **`get_orders` returns amounts in cents**, in a field called `amount` that doesn't say so, as many payment APIs do. Four of the six questions are about money.

| Mode | What happens between tasks |
|---|---|
| `--memory off` | Nothing. Every task starts from scratch. |
| `--memory on` | After each task the agent gets feedback (correct or not, and the expected answer), **reflects**, and writes at most two general lessons to `memory.json`. The next task gets those lessons in its system prompt. |

The reflection prompt follows the two ideas the post traces from CLIN to ReasoningBank: write **causal, transferable** lessons ("tool X returns Y, so do Z"), and learn from **failures as well as successes**. It is told never to store a task's answer.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."

python learn.py --memory off
python learn.py --memory on --reset
```

With memory on, you'll see lessons appear as the stream runs:

```
[FAIL] task 1 (4 steps, 0 lessons in memory): How much has Riverside Legal spent in total, in dollars?
       + lesson: …
[PASS] task 3 (4 steps, 1 lessons in memory): What is Bluebird Dental's total spend, in dollars?
```

**Results vary.** A capable model sometimes spots that `4900` looks like cents and gets task 1 right with no help, in which case memory has less to add. Run both modes a few times. What memory buys you is that a mistake made once **stays fixed**, without anyone editing a prompt or a tool.

## Our results

Against Claude Opus 5.5, graded on the committed `FINAL:` line only: **memory off 4/6**, with the cents mistake on tasks 1 and 4. **Memory on 5/6**: it failed task 1, then got every later question right. After six tasks the store held twelve lessons, five of them saying "amounts are cents" in different words, which shows why the *manage* step matters.

An early version of the grader accepted any answer that *contained* the right number, and hedged answers ("197,200, or $1,972 if these are cents") passed. Grading a single committed answer fixed that.

## Things to try

1. **Run `--memory on` twice without `--reset`.** The second run starts with the lessons from the first.
2. **Poison the memory.** Add a wrong lesson to `memory.json` ("amounts are in thousandths of a dollar") and watch the agent faithfully apply it. This is why memory needs managing.
3. **Remove the feedback.** Change `feedback` to `"No feedback available."` so the agent has to judge its own answers, the setting ReasoningBank studies. Does it still learn the lesson?

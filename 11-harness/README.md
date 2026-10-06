# 11 · Harness engineering

Companion code for the post [Harness engineering: the runtime is the product](https://www.agenticsystems.ai/blog/harness-engineering/).

A small long-running harness (about 170 lines) that summarizes incident reports one at a time. It's built around the properties the post argues matter more than any prompt:

| Property | Where |
|---|---|
| **Explicit work list**, created before any agent runs | `load_progress()` writes `run/progress.json` |
| **One fresh context per work item**: no context ever grows across items | `work_on()` |
| **Durable state outside the model**: progress file plus an append-only event log | `run/progress.json`, `run/events.jsonl` |
| **Verification in code** before an item counts as done; failures are retried with the reason | `verify()` |
| **Bounded effort**: step limit per item, attempt limit per item, then "needs a human" | `MAX_STEPS_PER_ITEM`, `MAX_ATTEMPTS` |
| **One interface to the "hands"**, so tools can move into a sandbox or a remote service | `execute(name, args)` |
| **Resume after a crash** without redoing verified work | re-run the same command |

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."

python harness.py --limit 8 --crash-after 3     # stops ("crashes") after 3 verified items
python harness.py --limit 8                     # resumes at item 4
```

Example output from the first command:

```
  INC-1001: verified (attempt 1)
  INC-1002: FAILED verification - must give the impact (113 minutes) (attempt 1)
  INC-1002: verified (attempt 2)
  INC-1003: verified (attempt 1)

!!! simulated crash after 3 items - run the same command again to resume
```

That transcript is from a test run with a scripted stand-in model, which got one summary wrong on purpose to exercise the retry path. With a real model, which items fail, if any, will vary.

Then look inside `run/`:
- `progress.json`: each item's status, attempt count, and the reason it last failed verification
- `events.jsonl`: every model call (with token counts), tool call and verification, in order
- `summaries/`: the output

Delete `run/` to start over.

## Things to try

1. **Kill it for real.** Press Ctrl+C in the middle of an item, then rerun. The interrupted item is retried; everything verified is kept.
2. **Tighten the gate.** Lower the word limit in `verify()` to 15 and watch more items need a second attempt, or end up as "needs a human".
3. **Move the hands.** Make `execute()` call an HTTP service or a container instead of reading local files. Nothing else in the harness has to change.

# 26 · Background agents: async tools and long tasks

Companion code for the post [Background agents: async tools and long tasks](https://www.agenticsystems.ai/blog/background-agents/).

A finance assistant runs the same conversation two ways:

| Design | Tools | What happens |
|---|---|---|
| `--blocking` | `run_job` | the call returns only when the job is done; the job's mid-way question can't reach anyone, so it falls back to a default |
| background (default) | `start_job`, `check_job`, `answer_job` | the job returns a task handle at once; a watcher polls the durable task store and turns changes into notifications; the job's question goes to the user |

`jobs.py` is the job runner: MCP-style task handles (`taskId`, `status`, `pollIntervalMs`, `ttlMs`) with the states `working`, `input_required`, `completed`, `failed`, `cancelled`, stored in `tasks.json` so a restarted client can resume by id. The job is a Q3 revenue reconciliation (about 15 seconds) that pauses to ask whether billing or the general ledger is authoritative.

The scripted user asks for the job, then asks an unrelated question while it runs, and answers the job's question with "Use the general ledger."

## Run it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...

python agent.py             # background
python agent.py --blocking  # blocking
```

Each run prints a timestamped transcript and a summary: when the first reply arrived, when the unrelated question was answered, whether the job's question reached the user, and the result (including which ledger was used).

## Live results (Claude API, Claude Opus 5.5, 2 runs each)

| Design | First reply | Unrelated question answered at | Job's question reached user | Ledger used | Calls / input tokens |
|---|---|---|---|---|---|
| blocking | 22.6–24.2 s | 25.7–28.3 s | no | billing (default) | 4 / ~3,600 |
| background | 6.4–6.5 s | 11.1–14.8 s | yes | general ledger | 8 / ~11,500 |

## Things to try

1. **Kill it mid-job.** Stop the script while the job is `working`, restart, and resume watching the task id in `tasks.json`. What would you need to make the job itself resumable?
2. **Two jobs at once.** Ask for two reconciliations and see how the agent keeps them apart in its replies.
3. **Push instead of poll.** Replace the watcher with a callback from `jobs._update()` and compare the code.

# 07 · One agent or many?

Companion code for the post [One agent or many? Reading the evidence](https://www.agenticsystems.ai/blog/one-agent-or-many/).

The same task from [03-context](../03-context) (24 incident reports, one question with a known answer) runs under three topologies:

| Topology | Who splits the work | Who combines it | Agents |
|---|---|---|---|
| `single` | nobody: one agent reads all 24 reports | the same agent | 1 |
| `workers` | **code**: 4 fixed batches | **code**: parses the sub-agents' lines and adds them up | 4 |
| `orchestrator` | **a lead model**, through a `delegate` tool it can call several times at once | the lead model | 1 + however many it delegates to |

Sub-agents start with a fresh context, can read only the files they were given, and return one line per report (`INC-1001 | service | minutes | root cause`).

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."

python topologies.py --topology single
python topologies.py --topology workers
python topologies.py --topology orchestrator
```

Each run ends with a summary line and the correct answer to compare against:

```
=== workers: 4 agents | … tokens read in total | largest single context … | …s
ground truth: auth, 760 minutes, mostly database failover
```

Compare three things:
- **Total tokens:** the cost of the whole system.
- **Largest single context:** how much any one agent had to hold at once.
- **Time:** sub-agents run in parallel.

## Things to try

1. **Change the number of workers** in `workers(n=4)`. More workers means smaller contexts and more total overhead.
2. **Break the hand-off.** Change `EXTRACT` so sub-agents return prose instead of the fixed line format, and watch `workers` fail: code can't parse prose. The orchestrator copes, at a cost in tokens.
3. **Make the task sequential.** Ask a question where each step depends on the last, e.g. "follow the chain of incidents caused by the first one". Splitting stops helping.

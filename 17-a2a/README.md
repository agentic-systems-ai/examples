# 17 · Agents talking to agents: A2A explained

Companion code for the post [Agents talking to agents: A2A explained](https://www.agenticsystems.ai/blog/a2a-explained/).

A from-scratch implementation of the core of **A2A 1.0** (Agent2Agent protocol) over JSON-RPC, in Python's standard library plus the Anthropic SDK. For real systems, use an official A2A SDK; this one exists so you can see the protocol itself.

| File | What it does |
|---|---|
| `remote_agent.py` | An A2A server. It publishes an **Agent Card** at `/.well-known/agent-card.json` and handles `SendMessage`, `GetTask` and `CancelTask` at `/a2a`. Behind it is the tool-using CRM agent from post #4, which callers never see. |
| `client.py` | A client that does what a calling agent would: discover the card, delegate a task, poll a long task, answer the agent's clarifying question in the same task, and handle protocol errors. |
| `provider.py` | Runs the remote agent on the Claude API (default) or Amazon Bedrock (`LLM_PROVIDER=bedrock`). |

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # or: export LLM_PROVIDER=bedrock AWS_REGION=us-east-1 (with AWS credentials)

python remote_agent.py --port 9001   # terminal 1
python client.py                     # terminal 2
```

The client walks through five steps:

```
1. Discover: read the Agent Card
2. Delegate a task and wait for the answer (blocking SendMessage)
3. Delegate without waiting, then poll (returnImmediately + GetTask)
4. An ambiguous request: the agent asks a question instead of guessing
     state: TASK_STATE_INPUT_REQUIRED
     agent asks: There are at least 15 customers called "Bluebird" (...). Which one do you mean?
     -> answering in the same task
     state: TASK_STATE_COMPLETED
     artifact: Bluebird Dental (C-1058, Lisbon, Starter plan) has spent $1,120 in total, across 8 orders. ...
5. Errors are part of the protocol
     unknown task: -32001 ...
     old protocol version: -32009 ...
```

**Tested** on the Claude API (Claude Opus 5.5), 3 runs: every answer matched the CRM data, and the agent asked which "Bluebird" was meant every time. The Bedrock path (`LLM_PROVIDER=bedrock`) is exercised with a stubbed client only.

## What's deliberately left out

Streaming (`SendStreamingMessage`), push notifications, `ListTasks`, signed Agent Cards and authentication. The post explains each of them; the [specification](https://a2a-protocol.org/latest/specification/) has the details. Tasks live in memory here; a real agent stores them durably (see post #11).

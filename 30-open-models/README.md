# 30 · Open-weight models for agents

Companion code for the post [Open-weight models for agents](https://www.agenticsystems.ai/blog/open-weight-models-for-agents/).

A support-triage worker on twelve tickets with known answers (`tickets.py`). It must look the customer up, then file one ticket with a category from a fixed list and a priority that follows written rules, including a one-level bump for Enterprise customers. Every `file_ticket` call is validated in code, so the results separate **wrong answers** from **invalid tool calls**.

Three modes:

| `--backend` | What runs |
|---|---|
| `claude` | Claude Opus 5.5 through the Anthropic SDK |
| `local` | any open-weight model behind an OpenAI-compatible server: Ollama (default URL), vLLM, LM Studio, llama.cpp |
| `mixed` | local first; if it can't file a valid ticket after two invalid attempts, escalate that ticket to Claude |
| `both` / `all` | Claude and local / all three |

## Run it

You need a local model server for the `local` and `mixed` modes. With [Ollama](https://ollama.com):

```bash
ollama pull qwen3:8b            # about 5 GB; fits a 12 GB GPU
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...

python worker.py --backend all --model qwen3:8b
python worker.py --backend local --base-url http://localhost:8000/v1 --model openai/gpt-oss-20b   # e.g. vLLM
```

Measured on 2026-10-07: two runs with Claude Opus 5.5 (low effort) and Qwen3 8B on Ollama 0.40 (RTX 3060, 12 GB, default settings). Both runs were identical:

```
model                                 correct  not filed  invalid calls  escalated  s/ticket    API $
claude-opus-5-5                        12/12           0              0          0       5.3   0.1390
qwen3:8b                                8/12           0              0          0      16.4   0.0000
mixed (qwen3:8b + escalation)           8/12           0              0          0      17.4   0.0000
```

Qwen3 8B made **no invalid tool calls**. Its four misses were all *valid*: a $98 double charge rated P2 (should be P3), a $1,080 invoice error rated P1 (P2), a broken calendar sync filed as an outage (bug), and "Do you have an Android app?" filed as a feature request (question). Because nothing was invalid, the mixed mode never escalated and scored the same as the local model. Validators protect the format; only an eval catches the judgment. (The API cost is an upper bound: cached input is priced as fresh input.)

**Windows note:** on recent Windows 11 builds, Ollama can fail with `The path cannot be traversed because it contains an untrusted mount point` after a successful pull. Ollama stores the manifest under `%USERPROFILE%\.ollama\models\manifests-v2\...` as a symbolic link to a blob, and Windows refuses to follow it. Replacing that one link with a copy of the blob it points to fixes it.

## Things to try

1. **Put the arithmetic in code.** The billing thresholds ($500) are deterministic: compute the base priority in the validator (or before the model call) and see whether the billing misses go away.
2. **Try another model** (`gpt-oss:20b`, a larger Qwen3) and compare invalid calls, not just accuracy.
3. **Count the money.** Multiply the API cost by your daily ticket volume, and compare with a GPU's monthly cost, including the people to run it.

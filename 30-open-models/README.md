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

The summary table:

```
model                                 correct  not filed  invalid calls  escalated  s/ticket    API $
claude-opus-5-5                          …/12          …              …          …         …        …
qwen3:8b                                 …/12          …              …          …         …   0.0000
mixed (qwen3:8b + escalation)            …/12          …              …          …         …        …
```

A test with a simulated weak local model showed the point of the design: invalid categories and malformed JSON were caught and corrected, escalation sent unfileable tickets to Claude, but tickets where the model forgot the Enterprise rule were *valid*, so they passed the validator (8/12 correct). Validators protect the format; only an eval catches the judgment.

## Things to try

1. **Put the Enterprise rule in code.** Make the validator reject a non-bumped priority for Enterprise customers, and watch correctness change.
2. **Try another model** (`gpt-oss:20b`, a larger Qwen3) and compare invalid calls, not just accuracy.
3. **Count the money.** Multiply the API cost by your daily ticket volume, and compare with a GPU's monthly cost, including the people to run it.

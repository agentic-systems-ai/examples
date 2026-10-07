# 23 · Prompt caching, done properly

Companion code for the post [Prompt caching, done properly](https://www.agenticsystems.ai/blog/prompt-caching-properly/).

An operations agent answers one question ("which warehouse got worse at on-time shipping, and why?") with three tools. The script:

1. **records** one real run of the agent, saving every request it made to `transcript.json`;
2. **replays** exactly that sequence of requests under five ways of assembling the prompt, and reports cache reads, writes, hit rate, input cost, and what **cache diagnostics** says changed.

| Variant | What it does |
|---|---|
| `stable` | Fixed tools, frozen system prompt with an explicit breakpoint, automatic caching for the conversation, append-only history |
| `timestamp` | Puts the current time at the top of the system prompt |
| `tool_order` | Sends the same tools in a different order on each request |
| `history_edit` | Injects a reminder into the newest turn and removes it from older ones |
| `no_cache` | No `cache_control` at all (the cost baseline) |

Replays use `max_tokens: 0`: the prompt is processed and the cache updated, but nothing is generated, so a replay costs only its input tokens. Each variant gets a unique tag at the start of its system prompt so variants can't read each other's cache entries.

**Thinking blocks are stripped from the replays.** On Claude Opus 5.5 a thinking block is bound to the exact prompt that produced it, and replaying it after the system prompt, tools or history changed is rejected on accounts where that check is enforced. Stripping them is the documented recovery, applied to every variant so they stay comparable.

## Run it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...

python agent.py all       # record, then replay
python agent.py replay    # replay an existing transcript.json again
```

Cache diagnostics is available on the Claude API only; with `LLM_PROVIDER=bedrock` the replay still reports usage, without diagnostics (Bedrock path stub-tested only).

## Things to try

1. **Longer runs.** Ask a question that needs more steps and watch the stable hit rate climb.
2. **Fix the timestamp properly.** Move the date into the first user message and confirm the cache comes back.
3. **Find a breaker in your own agent.** Log two consecutive request bodies, strip `cache_control`, and diff them; the first difference in the overlapping part is your breaker.

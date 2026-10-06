# 18 · What it really costs to run an agent

Companion code for the post [What it really costs to run an agent](https://www.agenticsystems.ai/blog/what-agents-cost/).

`cost_model.py` estimates the model cost of an agent workload from a handful of numbers: steps per task, starting context, tokens added per step, output per step, caching, success rate and model. **No API calls**: it's arithmetic on token counts and list prices.

The model is checked against a real run. `measured_run.json` holds the step-by-step token counts of one real run of [03-context](../03-context) (naive strategy, Claude Opus 5.5):

```
Validation against a measured run (post #3, naive strategy, Claude Opus 5.5)
  input tokens read : model   548,610   measured   546,693
  of which cached   : model   476,182   measured   474,231
  cost              : model $0.51       measured $0.51
```

## Run it

```bash
python cost_model.py                                               # validation + what-if table
python cost_model.py --tasks-per-day 500 --steps 12 --growth 3000  # your own workload
```

The what-if table shows which changes move the bill most:

```
  baseline (as measured)                             $ 0.512   ( 1.0x)
  twice the steps                                    $ 1.275   ( 2.5x)
  half the growth per step (leaner tools, post #4)   $ 0.288   ( 0.6x)
  no prompt caching                                  $ 2.242   ( 4.4x)
  80% success rate (retries)                         $ 0.641   ( 1.2x)
  Sonnet 5.5 instead of Opus 5.5                     $ 0.304   ( 0.6x)
  Haiku 4.5 instead of Opus 5.5                      $ 0.152   ( 0.3x)
```

Prices are list prices as of October 2026 (`PRICES` in the script). Check current pricing. The model assumes an append-only history with prompt caching. Strategies that rewrite or clear the context (post #3) break that assumption and cost more than it predicts.

## Getting your own numbers

Take them from traces, not guesses. With the tracing from [15-observability](../15-observability), the `gen_ai.usage.input_tokens` of the first and last model call in a task give you `start` and an average `growth`; count the `chat` spans for `steps`.

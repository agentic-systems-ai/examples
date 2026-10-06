"""A cost model for agent workloads, checked against a real measured run.

Companion code for https://www.agenticsystems.ai/blog/what-agents-cost/
Usage:  python cost_model.py                 # validate against the measured run, then print what-if tables
        python cost_model.py --tasks-per-day 500 --steps 12 --growth 3000

No API calls: this is arithmetic on token counts and list prices.

The model. An agent re-reads its whole context on every step, and the context grows as it works:
    context at step k      = start + k * growth                    (k = 0 .. steps-1)
    input tokens per task  = steps * start + growth * steps * (steps - 1) / 2      <- grows with steps squared
With prompt caching and an append-only history, each new token is written to the cache once and read back on
every later step, so almost all input is billed at the (much cheaper) cache-read price.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

# USD per million tokens, list prices as of October 2026 - check current pricing.
# Cache writes are the 5-minute TTL rate (1.25x input).
PRICES = {
    "claude-opus-5-5":   {"input": 4.00, "cache_write": 5.00, "cache_read": 0.20, "output": 20.00},
    "claude-sonnet-5-5": {"input": 2.00, "cache_write": 2.50, "cache_read": 0.20, "output": 10.00},
    "claude-haiku-4-5":  {"input": 1.00, "cache_write": 1.25, "cache_read": 0.10, "output": 5.00},
}


@dataclass
class Workload:
    steps: int = 15                 # model calls per task
    start: int = 720                # tokens on the first call: system prompt, tools, task
    growth: int = 5_100             # tokens added to the context per step: tool results + the model's output
    output_per_step: int = 190      # tokens the model writes per step (thinking included)
    cached: bool = True             # prompt caching on, with an append-only history
    success_rate: float = 1.0       # fraction of tasks that finish correctly; failures are paid for too
    model: str = "claude-opus-5-5"


def per_task(w: Workload) -> dict:
    p = PRICES[w.model]
    total_input = w.steps * w.start + w.growth * w.steps * (w.steps - 1) // 2
    if w.cached:
        written = w.start + w.growth * (w.steps - 1)   # every token enters the cache once
        read, uncached = total_input - written, 0
    else:
        written, read, uncached = 0, 0, total_input
    output = w.steps * w.output_per_step
    cost = (uncached * p["input"] + written * p["cache_write"] + read * p["cache_read"] + output * p["output"]) / 1e6
    return {"input_tokens": total_input, "cache_read": read, "cache_write": written, "output_tokens": output,
            "cost_per_attempt": cost, "cost_per_completed_task": cost / w.success_rate}


def monthly(w: Workload, tasks_per_day: float) -> float:
    return per_task(w)["cost_per_completed_task"] * tasks_per_day * 30


def validate() -> None:
    """Compare the model with a real run: post #3's naive strategy, 15 steps, measured step by step."""
    run = json.loads((Path(__file__).parent / "measured_run.json").read_text())
    steps = run["steps"]
    start, final = steps[0]["context"], steps[-1]["context"]
    w = Workload(steps=len(steps), start=start, growth=(final - start) // (len(steps) - 1),
                 output_per_step=run["output_tokens"] // len(steps))
    est = per_task(w)
    print("Validation against a measured run (post #3, naive strategy, Claude Opus 5.5)")
    print(f"  input tokens read : model {est['input_tokens']:>9,}   measured {run['input_tokens_read']:>9,}")
    print(f"  of which cached   : model {est['cache_read']:>9,}   measured {run['cache_read']:>9,}")
    print(f"  cost              : model ${est['cost_per_attempt']:.2f}       measured ${run['estimated_cost']:.2f}\n")


def what_if(base: Workload) -> None:
    print("What drives the cost? (per completed task, starting from the measured run)")
    rows = [
        ("baseline (as measured)", base),
        ("twice the steps", Workload(**{**base.__dict__, "steps": base.steps * 2})),
        ("half the growth per step (leaner tools, post #4)", Workload(**{**base.__dict__, "growth": base.growth // 2})),
        ("no prompt caching", Workload(**{**base.__dict__, "cached": False})),
        ("80% success rate (retries)", Workload(**{**base.__dict__, "success_rate": 0.8})),
        ("Sonnet 5.5 instead of Opus 5.5", Workload(**{**base.__dict__, "model": "claude-sonnet-5-5"})),
        ("Haiku 4.5 instead of Opus 5.5", Workload(**{**base.__dict__, "model": "claude-haiku-4-5"})),
    ]
    base_cost = per_task(base)["cost_per_completed_task"]
    for label, w in rows:
        c = per_task(w)["cost_per_completed_task"]
        print(f"  {label:<50} ${c:6.3f}   ({c / base_cost:4.1f}x)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-per-day", type=float)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--start", type=int)
    parser.add_argument("--growth", type=int)
    parser.add_argument("--model", choices=list(PRICES))
    args = parser.parse_args()

    if args.tasks_per_day:
        w = Workload(**{k: v for k, v in {"steps": args.steps, "start": args.start, "growth": args.growth,
                                          "model": args.model}.items() if v is not None})
        est = per_task(w)
        print(f"{w}\n  per task ${est['cost_per_completed_task']:.4f}  |  per month ${monthly(w, args.tasks_per_day):,.2f}")
    else:
        validate()
        what_if(Workload())

"""Compare four ways to spend a model budget on the same 12 tasks: accuracy and cost, measured.

Companion code for https://www.agenticsystems.ai/blog/routing-for-agent-cost/
Usage:  python route.py --strategy opus|opus-low|haiku|routed
"""

import argparse
import re
from concurrent.futures import ThreadPoolExecutor

import anthropic

from tasks import TASKS

client = anthropic.Anthropic()
OPUS, SONNET, HAIKU = "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"

# USD per million tokens (input, output), list prices as of Oct 2026 - check current pricing before relying on them.
PRICE = {OPUS: (4.00, 20.00), SONNET: (2.00, 10.00), HAIKU: (1.00, 5.00)}


def ask(model: str, prompt: str, effort: str | None = None) -> tuple[str, float]:
    """One call; returns (text, cost in USD). Haiku 4.5 doesn't take an effort setting, so it gets none."""
    kwargs = dict(model=model, max_tokens=16000, messages=[{"role": "user", "content": prompt}])
    if model == HAIKU:
        r = client.messages.create(**kwargs)
    else:
        r = client.beta.messages.create(**kwargs, output_config={"effort": effort or "medium"},
                                        betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    u = r.usage
    tokens_in = u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0)
    price_in, price_out = PRICE[model]
    cost = (tokens_in * price_in + u.output_tokens * price_out) / 1e6  # thinking tokens are billed as output
    return "".join(b.text for b in r.content if b.type == "text").strip(), cost


def route(prompt: str) -> tuple[str, str | None, float]:
    """A cheap router: the small model rates difficulty, and the rating picks the model for the real call."""
    rating, cost = ask(HAIKU, "Rate how hard this task is for an AI model: easy (lookup or classification), medium "
                              "(a little reasoning or arithmetic), or hard (multi-step reasoning or constraints). "
                              f"Reply with one word.\n\nTask:\n{prompt}")
    tier = next((t for t in ("hard", "medium", "easy") if t in rating.lower()), "hard")  # unsure -> play safe
    return {"easy": (HAIKU, None), "medium": (SONNET, "low"), "hard": (OPUS, "medium")}[tier] + (cost,)


def solve(strategy: str, prompt: str) -> tuple[str, float, str]:
    if strategy == "opus":
        model, effort, overhead = OPUS, "medium", 0.0
    elif strategy == "opus-low":
        model, effort, overhead = OPUS, "low", 0.0
    elif strategy == "haiku":
        model, effort, overhead = HAIKU, None, 0.0
    else:
        model, effort, overhead = route(prompt)
    answer, cost = ask(model, prompt, effort)
    return answer, cost + overhead, model


def correct(answer: str, expected: str) -> bool:
    a = answer.strip().strip(".").replace("$", "").replace(",", "").lower()
    e = expected.lower()
    try:
        return abs(float(a) - float(e)) < 1e-6
    except ValueError:
        return a == e or re.search(rf"(?<![\w-]){re.escape(e)}(?![\w-])", a) is not None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=["opus", "opus-low", "haiku", "routed"], required=True)
    strategy = parser.parse_args().strategy

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda t: solve(strategy, t[1]), TASKS))

    total, by_tier = 0.0, {}
    for (tier, question, expected), (answer, cost, model) in zip(TASKS, results):
        ok = correct(answer, expected)
        total += cost
        by_tier.setdefault(tier, []).append(ok)
        print(f"[{'PASS' if ok else 'FAIL'}] {tier:<6} {model:<18} ${cost:.5f}  expected {expected!r}, got {answer[:40]!r}")
    accuracy = ", ".join(f"{t} {sum(v)}/{len(v)}" for t, v in by_tier.items())
    print(f"\n=== {strategy}: {sum(sum(v) for v in by_tier.values())}/{len(TASKS)} correct ({accuracy}) | "
          f"total ${total:.4f}")

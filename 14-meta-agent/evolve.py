"""A tiny reflective prompt-evolution loop in the style of GEPA: run, reflect on failures, propose, keep the Pareto front.

Companion code for https://www.agenticsystems.ai/blog/agents-that-design-agents/
Usage:  python evolve.py --rounds 6

The "agent" being improved is a single prompt that classifies support tickets. The loop never sees the test set;
the final comparison on held-out tickets shows whether it learned rules or just memorised training examples.
"""

import argparse
import random
from concurrent.futures import ThreadPoolExecutor

import anthropic
from pydantic import BaseModel

from data import LABELS, TEST, TRAIN

MODEL = "claude-opus-5-5"
client = anthropic.Anthropic()
SEED_PROMPT = f"Classify the support ticket into exactly one category: {', '.join(LABELS)}. Reply with the category only."


def call(prompt: str, effort: str = "low") -> str:
    r = client.beta.messages.create(model=MODEL, max_tokens=16000, output_config={"effort": effort},
                                    messages=[{"role": "user", "content": prompt}],
                                    betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    return "".join(b.text for b in r.content if b.type == "text").strip()


def classify(system_prompt: str, ticket: str) -> str:
    answer = call(f"{system_prompt}\n\nTicket: {ticket}").lower()
    return next((label for label in LABELS if label in answer), answer[:30])


def evaluate(system_prompt: str, data: list) -> list[bool]:
    """Per-example correctness. Code grades it, so every score is exact."""
    with ThreadPoolExecutor(max_workers=6) as pool:
        predictions = list(pool.map(lambda item: classify(system_prompt, item[0]), data))
    return [p == label for p, (_, label) in zip(predictions, data)], predictions


class Proposal(BaseModel):
    diagnosis: str
    new_prompt: str


def reflect(prompt: str, failures: list) -> Proposal:
    """The GEPA step: read concrete failures in natural language and propose a better instruction."""
    shown = "\n".join(f"- Ticket: {t}\n  Predicted: {p}\n  Correct: {y}" for t, p, y in failures)
    out = client.beta.messages.parse(
        model=MODEL, max_tokens=16000, output_config={"effort": "medium"}, output_format=Proposal,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        messages=[{"role": "user", "content":
            f"This instruction is used to classify support tickets:\n\n{prompt}\n\nIt got these wrong:\n{shown}\n\n"
            "Diagnose what general rule the instruction is missing, then write an improved instruction. State rules "
            "that generalize to new tickets; do not list or quote these specific tickets. Keep the same output format."}],
    )
    return out.parsed_output


def pareto_front(candidates: list[dict]) -> list[dict]:
    """Keep every candidate that is the best (or tied best) on at least one training example."""
    n = len(TRAIN)
    best = [max(c["scores"][i] for c in candidates) for i in range(n)]
    return [c for c in candidates if any(c["scores"][i] and best[i] for i in range(n))] or candidates


def main(rounds: int, seed: int) -> None:
    rng = random.Random(seed)
    scores, _ = evaluate(SEED_PROMPT, TRAIN)
    candidates = [{"prompt": SEED_PROMPT, "scores": scores, "round": 0}]
    print(f"round 0 (seed prompt): train {sum(scores)}/{len(TRAIN)}")

    for r in range(1, rounds + 1):
        parent = rng.choice(pareto_front(candidates))  # sampling the front keeps diverse partial solutions alive
        fresh, preds = evaluate(parent["prompt"], TRAIN)  # a fresh run: outputs vary, so use this run's own grades
        failures = [(t, p, y) for (t, y), p, ok in zip(TRAIN, preds, fresh) if not ok]
        if not failures:
            print(f"round {r}: parent already perfect on train; stopping")
            break
        proposal = reflect(parent["prompt"], failures[:4])
        child_scores, _ = evaluate(proposal.new_prompt, TRAIN)
        candidates.append({"prompt": proposal.new_prompt, "scores": child_scores, "round": r})
        print(f"round {r}: parent train {sum(parent['scores'])}/{len(TRAIN)} -> child {sum(child_scores)}/{len(TRAIN)}"
              f"   diagnosis: {proposal.diagnosis[:90]}")

    best = max(candidates, key=lambda c: (sum(c["scores"]), -c["round"]))
    seed_test, _ = evaluate(SEED_PROMPT, TEST)
    best_test, _ = evaluate(best["prompt"], TEST)
    print(f"\n=== held-out test: seed prompt {sum(seed_test)}/{len(TEST)}  vs  evolved prompt (round {best['round']}) "
          f"{sum(best_test)}/{len(TEST)}")
    print(f"\nEvolved prompt:\n{best['prompt']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    main(args.rounds, args.seed)

"""Estimate an agent's time horizon the way METR does: fit P(success) against log(human task time).

Companion code for https://www.agenticsystems.ai/blog/time-horizons/
Usage:  python fit_horizon.py                      # synthetic demo: recover a KNOWN horizon from noisy data
        python fit_horizon.py --csv my_tasks.csv   # your own results: columns human_minutes,success (0/1)

No API key and no third-party packages needed.

The model:  P(success | task) = 1 / (1 + exp(-(a + b * log2(human_minutes))))
The 50% time horizon is the task length where P = 0.5:  log2(h50) = -a / b
The 80% horizon is where P = 0.8:                       log2(h80) = (log(4) - a) / b
"""

import argparse
import csv
import math
import random


def fit_logistic(x: list[float], y: list[int], iters: int = 50) -> tuple[float, float]:
    """Maximum-likelihood logistic regression with one feature, by Newton's method."""
    a, b = 0.0, 0.0
    for _ in range(iters):
        ga = gb = haa = hab = hbb = 0.0
        for xi, yi in zip(x, y):
            p = 1 / (1 + math.exp(-(a + b * xi)))
            w = p * (1 - p) + 1e-9
            ga += yi - p
            gb += (yi - p) * xi
            haa += w
            hab += w * xi
            hbb += w * xi * xi
        det = haa * hbb - hab * hab
        a += (hbb * ga - hab * gb) / det
        b += (haa * gb - hab * ga) / det
    return a, b


def horizons(a: float, b: float) -> tuple[float, float]:
    """Return the 50% and 80% horizons in minutes. b must be negative (longer tasks are harder)."""
    return 2 ** (-a / b), 2 ** ((math.log(4) - a) / b)


def bootstrap(minutes: list[float], success: list[int], rounds: int = 500, seed: int = 0):
    """Resample tasks with replacement and refit; return 90% intervals for both horizons."""
    rng, h50s, h80s = random.Random(seed), [], []
    x = [math.log2(m) for m in minutes]
    for _ in range(rounds):
        idx = [rng.randrange(len(x)) for _ in x]
        a, b = fit_logistic([x[i] for i in idx], [success[i] for i in idx])
        if b < 0:
            h50, h80 = horizons(a, b)
            h50s.append(h50)
            h80s.append(h80)
    pct = lambda v, q: sorted(v)[int(q * (len(v) - 1))]
    return (pct(h50s, 0.05), pct(h50s, 0.95)), (pct(h80s, 0.05), pct(h80s, 0.95))


def fmt(minutes: float) -> str:
    return f"{minutes:.0f} min" if minutes < 120 else f"{minutes / 60:.1f} h"


def report(minutes: list[float], success: list[int]) -> None:
    a, b = fit_logistic([math.log2(m) for m in minutes], success)
    if b >= 0:
        print("No downward trend: success doesn't fall with task length in this data, so there is no horizon to fit.")
        return
    h50, h80 = horizons(a, b)
    (lo50, hi50), (lo80, hi80) = bootstrap(minutes, success)
    print(f"{len(minutes)} tasks, {sum(success)} successes")
    print(f"50% time horizon: {fmt(h50):>8}   (90% interval {fmt(lo50)} – {fmt(hi50)})")
    print(f"80% time horizon: {fmt(h80):>8}   (90% interval {fmt(lo80)} – {fmt(hi80)})")


def synthetic_demo(n_tasks: int, seed: int = 42) -> None:
    """Simulate an agent whose TRUE 50% horizon is 60 minutes, then check we can recover it."""
    rng = random.Random(seed)
    true_h50, slope = 60.0, -0.9  # the slope controls how sharply success falls with task length
    a_true = -slope * math.log2(true_h50)
    minutes = [2 ** rng.uniform(math.log2(1), math.log2(16 * 60)) for _ in range(n_tasks)]  # 1 min to 16 h
    success = [int(rng.random() < 1 / (1 + math.exp(-(a_true + slope * math.log2(m))))) for m in minutes]
    t50, t80 = horizons(a_true, slope)
    print(f"SYNTHETIC agent - true 50% horizon {fmt(t50)}, true 80% horizon {fmt(t80)}\n")
    report(minutes, success)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", help="file with columns human_minutes,success")
    parser.add_argument("--tasks", type=int, default=150, help="number of synthetic tasks")
    args = parser.parse_args()
    if args.csv:
        rows = list(csv.DictReader(open(args.csv)))
        report([float(r["human_minutes"]) for r in rows], [int(r["success"]) for r in rows])
    else:
        synthetic_demo(args.tasks)

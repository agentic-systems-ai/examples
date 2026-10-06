"""pass@k and pass^k from repeated trials, using the standard unbiased estimators.

pass@k: probability that AT LEAST ONE of k independent trials succeeds   (Chen et al., 2021, the Codex paper)
pass^k: probability that ALL k independent trials succeed                 (Yao et al., 2024, tau-bench)

For a task run n times with c successes, both are estimated by counting subsets of size k:
    pass@k = 1 - C(n - c, k) / C(n, k)
    pass^k =     C(c, k)     / C(n, k)
A suite's score is the mean over tasks.
"""

from math import comb, sqrt


def pass_at_k(n: int, c: int, k: int) -> float:
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    return comb(c, k) / comb(n, k)


def suite_scores(results: dict[str, list[bool]], k: int) -> dict[str, float]:
    """`results` maps task -> list of trial outcomes. Every task must have at least k trials."""
    at, hat = [], []
    for outcomes in results.values():
        n, c = len(outcomes), sum(outcomes)
        at.append(pass_at_k(n, c, k))
        hat.append(pass_hat_k(n, c, k))
    return {"pass@k": sum(at) / len(at), "pass^k": sum(hat) / len(hat)}


def pass1_with_interval(results: dict[str, list[bool]]) -> tuple[float, float]:
    """Mean per-task success rate, with a rough 95% interval (normal approximation over tasks).
    With a handful of tasks this interval is wide - which is exactly the point."""
    rates = [sum(o) / len(o) for o in results.values()]
    mean = sum(rates) / len(rates)
    var = sum((r - mean) ** 2 for r in rates) / max(1, len(rates) - 1)
    return mean, 1.96 * sqrt(var / len(rates))


def report(results: dict[str, list[bool]]) -> None:
    n = min(len(o) for o in results.values())
    mean, half = pass1_with_interval(results)
    print(f"{len(results)} tasks x {n} trials | pass@1 = {mean:.0%} (95% interval roughly ±{half:.0%})\n")
    print(" k   pass@k   pass^k")
    for k in range(1, n + 1):
        s = suite_scores(results, k)
        print(f"{k:>2}   {s['pass@k']:6.0%}   {s['pass^k']:6.0%}")


if __name__ == "__main__":
    # A HYPOTHETICAL worked example (not measured): four tasks, five trials each.
    example = {
        "always works":    [True, True, True, True, True],
        "usually works":   [True, True, True, True, False],
        "coin flip":       [True, False, True, False, True],
        "rarely works":    [False, False, True, False, False],
    }
    print("Hypothetical example - illustrates the maths, not any real agent:\n")
    report(example)

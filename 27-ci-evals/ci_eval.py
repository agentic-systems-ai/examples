"""Eval gate for CI: run the regression suite k times per task, compare with main's baseline, fail on real regressions.

Companion code for https://www.agenticsystems.ai/blog/testing-agents-in-ci/
Usage:  python ci_eval.py --write-baseline                    # on main: record the baseline
        python ci_eval.py                                     # on a pull request: compare with the baseline
        python ci_eval.py --prompt system_regressed.md        # try a change that should fail the gate

Exit code 0 = pass, 1 = regression or incomplete run. In GitHub Actions the summary also goes to the job page.

Two rules, because agents are stochastic:
  hard  a task that passed all k trials on main and now passes none: something broke. Fails the build.
  soft  the overall pass rate dropped by more than chance explains (one-sided 95%, binomial). Fails the build.
Tasks that went from k/k to partly passing are reported as warnings: often noise, sometimes the first sign.
"""

import argparse
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import agent_under_test
from suite import SUITE

HERE = Path(__file__).parent
PRICE_IN, PRICE_OUT = 4.00, 20.00  # $/M tokens, Claude Opus 5.5; an upper bound, since cache reads cost less


def run_suite(prompt: str, k: int, budget: float, workers: int) -> dict:
    trials = [(name, msg, grader, i) for name, msg, grader in SUITE for i in range(k)]
    results, spent, stopped = {name: [] for name, _, _ in SUITE}, 0.0, False
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(agent_under_test.run, msg, prompt): (name, grader) for name, msg, grader, _ in trials}
        for f in as_completed(futures):
            name, grader = futures[f]
            try:
                r = f.result()
                passed, why = grader(r)
                spent += (r["usage"]["input"] * PRICE_IN + r["usage"]["output"] * PRICE_OUT) / 1e6
            except Exception as exc:  # an infrastructure error is not a model failure: record it separately
                passed, why = None, f"error: {type(exc).__name__}: {exc}"
            results[name].append({"passed": passed, "why": why})
            if spent > budget and not stopped:
                stopped = True
                for other in futures:
                    other.cancel()
    return {"prompt": prompt, "k": k, "spent": round(spent, 4), "over_budget": stopped, "tasks": results}


def summarize(run: dict) -> dict:
    k, tasks = run["k"], run["tasks"]
    graded = {n: [t["passed"] for t in ts if t["passed"] is not None] for n, ts in tasks.items()}
    total = sum(len(v) for v in graded.values())
    passes = sum(sum(v) for v in graded.values())
    return {"trial_pass_rate": passes / total if total else 0.0, "trials": total,
            "errors": sum(t["passed"] is None for ts in tasks.values() for t in ts),
            "complete": all(len(v) == k for v in graded.values()),
            "per_task": {n: {"passes": sum(v), "of": len(v)} for n, v in graded.items()},
            "pass_hat_k": sum(len(v) == k and all(v) for v in graded.values()) / len(graded)}


def compare(new: dict, base: dict) -> tuple[list, list]:
    failures, warnings = [], []
    for name, b in base["per_task"].items():
        n = new["per_task"].get(name, {"passes": 0, "of": 0})
        if b["passes"] == b["of"] and n["of"] and n["passes"] == 0:
            failures.append(f"hard regression: '{name}' passed {b['passes']}/{b['of']} on main, 0/{n['of']} now")
        elif b["passes"] == b["of"] and n["passes"] < n["of"]:
            warnings.append(f"'{name}' went from {b['passes']}/{b['of']} to {n['passes']}/{n['of']}")
    p0, n0, p1, n1 = base["trial_pass_rate"], base["trials"], new["trial_pass_rate"], new["trials"]
    se = math.sqrt(max(p0 * (1 - p0), 1 / n0) / n0 + max(p1 * (1 - p1), 1 / n1) / n1)  # floor avoids se=0 at 100%
    if p0 - p1 > 1.645 * se:
        failures.append(f"soft regression: pass rate {p0:.0%} on main -> {p1:.0%} (drop {p0 - p1:.0%} > noise {1.645 * se:.0%})")
    return failures, warnings


def report(run: dict, s: dict, base: dict | None, failures: list, warnings: list, ok: bool) -> str:
    lines = [f"## Agent eval gate: {'PASS' if ok else 'FAIL'}", "",
             f"prompt `{run['prompt']}`, k={run['k']}, spent ${run['spent']:.2f}"
             + (" **(stopped at budget)**" if run["over_budget"] else ""), "",
             "| task | passes | main |", "|---|---|---|"]
    for name, t in s["per_task"].items():
        b = base["per_task"].get(name) if base else None
        main = f"{b['passes']}/{b['of']}" if b else "-"
        lines.append(f"| {name} | {t['passes']}/{t['of']} | {main} |")
    lines += ["", f"trial pass rate {s['trial_pass_rate']:.0%}" + (f" (main {base['trial_pass_rate']:.0%})" if base else "")
              + f", pass^{run['k']} {s['pass_hat_k']:.0%}, infrastructure errors {s['errors']}"]
    lines += [f"- :x: {f}" for f in failures] + [f"- :warning: {w}" for w in warnings]
    for name, ts in run["tasks"].items():
        for t in ts:
            if t["passed"] is False:
                lines.append(f"  - `{name}` failed: {t['why']}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="system.md")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--budget", type=float, default=2.00, help="stop the run if spend exceeds this many dollars")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--baseline", default=str(HERE / "baseline.json"))
    ap.add_argument("--write-baseline", action="store_true")
    args = ap.parse_args()

    run = run_suite(args.prompt, args.k, args.budget, args.workers)
    s = summarize(run)
    (HERE / "results.json").write_text(json.dumps({"run": run, "summary": s}, indent=1), encoding="utf-8")
    if args.write_baseline:
        if not s["complete"]:
            print("not writing a baseline from an incomplete run (budget stop or errors)")
            sys.exit(1)
        Path(args.baseline).write_text(json.dumps(s, indent=1), encoding="utf-8")
        print(f"baseline written: pass rate {s['trial_pass_rate']:.0%}, pass^{args.k} {s['pass_hat_k']:.0%}")
        sys.exit(0)

    base = json.loads(Path(args.baseline).read_text(encoding="utf-8")) if Path(args.baseline).exists() else None
    failures, warnings = compare(s, base) if base else ([], ["no baseline found: nothing to compare with"])
    if not s["complete"]:
        failures.append("incomplete run (budget stop or errors): can't vouch for this change")
    ok = not failures
    text = report(run, s, base, failures, warnings, ok)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    sys.exit(0 if ok else 1)

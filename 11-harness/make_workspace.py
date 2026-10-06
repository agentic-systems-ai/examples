"""Generate a deterministic workspace of incident reports, and return the true answer to the task.

Each report is ~1,600 tokens: mostly routine log lines, with the facts that matter
(service, customer impact, root cause) spread through it, so an agent has to read the whole file.
"""

import random
from collections import Counter, defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).parent / "workspace"
SERVICES = ["checkout", "search", "auth", "payments", "notifications", "inventory"]
CAUSES = ["bad deploy", "database failover", "expired certificate", "memory leak", "dependency timeout", "config change"]
N_REPORTS = 24


def _log_line(rng: random.Random, service: str, day: int) -> str:
    level = rng.choices(["INFO", "INFO", "INFO", "WARN", "DEBUG"])[0]
    msg = rng.choice([
        f"request completed status=200 latency_ms={rng.randint(20, 400)}",
        f"cache refresh finished keys={rng.randint(100, 9000)}",
        f"health check ok upstream={rng.choice(SERVICES)}",
        f"retrying call attempt={rng.randint(1, 3)} backoff_ms={rng.randint(50, 800)}",
        f"queue depth={rng.randint(0, 500)} consumers={rng.randint(2, 12)}",
    ])
    return f"2026-09-{day:02d}T{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}Z {level:5} {service}-{rng.randint(1000, 9999):x}  {msg}"


def build() -> dict:
    rng = random.Random(7)  # fixed seed: every reader gets the same files and the same answer
    WORKSPACE.mkdir(exist_ok=True)
    downtime: dict[str, int] = defaultdict(int)
    causes: dict[str, Counter] = defaultdict(Counter)

    for i in range(1, N_REPORTS + 1):
        service, cause = rng.choice(SERVICES), rng.choice(CAUSES)
        minutes, day = rng.randint(5, 180), rng.randint(1, 28)
        downtime[service] += minutes
        causes[service][cause] += 1
        logs = [_log_line(rng, service, day) for _ in range(70)]
        body = "\n".join(
            [f"# Incident report INC-{1000 + i}", f"Service: {service}", f"Date: 2026-09-{day:02d}", "", "## Timeline"]
            + logs[:35]
            + ["", f"Customer impact: {minutes} minutes of degraded or unavailable service.", "", "## Logs"]
            + logs[35:]
            + ["", "## Postmortem", f"Root cause: {cause}.", "Follow-up actions are tracked in the reliability backlog."]
        )
        (WORKSPACE / f"INC-{1000 + i}.md").write_text(body + "\n", encoding="utf-8")

    worst = max(downtime, key=downtime.get)
    return {"service": worst, "minutes": downtime[worst], "root_cause": causes[worst].most_common(1)[0][0]}


if __name__ == "__main__":
    print(build())

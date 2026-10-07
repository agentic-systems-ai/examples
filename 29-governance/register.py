"""An agent register: what policy and compliance teams need, checked against evidence in code.

Companion code for https://www.agenticsystems.ai/blog/governance-for-agents/
Usage:  python register.py                 # report on every agent in agents.json
        python register.py --markdown      # the same, as a markdown register to paste into a wiki

Each agent declares its owner, purpose, data, tools and controls. Each control names its evidence: a file and a
function or text in this repository. The checker maps controls to the eleven practice categories in ISACA's 2026
"Cybersecurity Recommendations for Securing AI Agents", verifies that every piece of evidence actually exists, and
reports gaps. No API calls.
"""

import argparse
import json
from pathlib import Path

HERE = Path(__file__).parent
EXAMPLES = HERE.parent

CATEGORIES = [  # ISACA (2026), figure 2, in order
    "Governance, asset inventory and risk ownership",
    "Secure development, change management and continuous assurance",
    "Identity, authentication and authorization",
    "Segmentation, isolation and sandboxed execution",
    "Defense against prompt injection and untrusted content",
    "Data protection, secrets and memory security",
    "Secure tool and API integrations",
    "Policy enforcement, output control and human oversight",
    "Logging, monitoring, detection and incident response",
    "Model, provider and software supply chain",
    "Reliability, resilience, kill switches and safe degradation",
]
REQUIRED_FIELDS = ["name", "owner", "purpose", "users", "model", "data", "tools", "risk_tier", "incident_contact"]
# Higher risk tiers must show evidence in more categories.
REQUIRED_BY_TIER = {
    "low": {0, 2, 8},
    "medium": {0, 1, 2, 6, 7, 8, 10},
    "high": set(range(len(CATEGORIES))),
}


def evidence_exists(ev: str) -> bool:
    """'path/to/file.py::needle' passes if the file exists and contains the needle."""
    path, _, needle = ev.partition("::")
    f = EXAMPLES / path
    return f.is_file() and (not needle or needle in f.read_text(encoding="utf-8", errors="ignore"))


def assess(agent: dict) -> dict:
    missing_fields = [f for f in REQUIRED_FIELDS if not agent.get(f)]
    covered, broken = {}, []
    for c in agent.get("controls", []):
        if all(evidence_exists(e) for e in c["evidence"]):
            covered.setdefault(c["category"], []).append(c["control"])
        else:
            broken.append(c["control"])
    needed = REQUIRED_BY_TIER[agent.get("risk_tier", "high")]
    gaps = [CATEGORIES[i] for i in sorted(needed) if i not in covered]
    tools_high = [t["name"] for t in agent.get("tools", []) if t.get("effect") in ("money", "external", "destructive")]
    findings = []
    if "latest" in str(agent.get("model", "")).lower():
        findings.append("model is not pinned: behaviour can change without any change on your side")
    ok = not missing_fields and not broken and not gaps and not findings
    return {"ok": ok, "missing_fields": missing_fields, "covered": covered, "broken_evidence": broken,
            "gaps": gaps, "findings": findings, "consequential_tools": tools_high}


def text_report(agent: dict, a: dict) -> str:
    lines = [f"\n=== {agent['name']}  (risk tier: {agent.get('risk_tier', '?')}, owner: {agent.get('owner') or 'NONE'})",
             f"    purpose: {agent.get('purpose') or 'NONE'}",
             f"    consequential tools: {', '.join(a['consequential_tools']) or 'none'}"]
    for i, cat in enumerate(CATEGORIES):
        needed = i in REQUIRED_BY_TIER[agent.get("risk_tier", "high")]
        controls = a["covered"].get(i, [])
        mark = "ok  " if controls else ("GAP " if needed else "-   ")
        lines.append(f"    {mark} {cat}: {'; '.join(controls) or ('required for this tier' if needed else 'not required')}")
    for f in a["missing_fields"]:
        lines.append(f"    MISSING field: {f}")
    for b in a["broken_evidence"]:
        lines.append(f"    CLAIMED BUT NOT FOUND: {b}")
    for f in a["findings"]:
        lines.append(f"    FINDING: {f}")
    lines.append(f"    => {'READY FOR REVIEW' if a['ok'] else 'NOT READY: fix the gaps above'}")
    return "\n".join(lines)


def markdown(agent: dict, a: dict) -> str:
    rows = "\n".join(f"| {cat} | {'; '.join(a['covered'].get(i, [])) or '—'} |" for i, cat in enumerate(CATEGORIES))
    return (f"### {agent['name']}\n\n| Field | Value |\n|---|---|\n"
            + "\n".join(f"| {f} | {json.dumps(agent.get(f)) if isinstance(agent.get(f), list) else agent.get(f, '—')} |" for f in REQUIRED_FIELDS)
            + f"\n\n| ISACA practice category | Controls with evidence |\n|---|---|\n{rows}\n\n"
            + f"**Status:** {'ready for review' if a['ok'] else 'not ready'}"
            + (f"; gaps: {', '.join(a['gaps'])}" if a["gaps"] else "")
            + (f"; claimed without evidence: {', '.join(a['broken_evidence'])}" if a["broken_evidence"] else "") + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()
    agents = json.loads((HERE / "agents.json").read_text(encoding="utf-8"))
    for agent in agents:
        a = assess(agent)
        print(markdown(agent, a) if args.markdown else text_report(agent, a))

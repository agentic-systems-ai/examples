"""A triage worker that can run on Claude or on an open-weight model you host, compared on the same 12 tickets.

Companion code for https://www.agenticsystems.ai/blog/open-weight-models-for-agents/
Usage:  python worker.py --backend claude
        python worker.py --backend local --model qwen3:8b       # any OpenAI-compatible server, Ollama by default
        python worker.py --backend local --base-url http://localhost:8000/v1 --model openai/gpt-oss-20b   # e.g. vLLM
        python worker.py --backend both --model qwen3:8b
        python worker.py --backend mixed --model qwen3:8b      # local first, escalate to Claude when output is invalid

The worker must look the customer up, then file exactly one ticket with a valid category and priority. Every
file_ticket call is validated against its schema, so the table separates *wrong answers* from *invalid tool calls*,
which is where smaller models usually differ.
"""

import argparse
import json
import time
import urllib.request

from tickets import CUSTOMERS, RULES, TICKETS

CLAUDE_MODEL = "claude-opus-5-5"
CLAUDE_PRICE = (4.00, 20.00)  # $/M input, output tokens
SYSTEM = "You are a support triage worker. " + RULES
CATEGORIES = ["outage", "billing", "account", "bug", "feature_request", "security", "question"]
PRIORITIES = ["P1", "P2", "P3", "P4"]

TOOLS = [
    {"name": "lookup_customer", "description": "Find a customer by email. Returns customer_id and plan.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["email"],
                      "properties": {"email": {"type": "string"}}}},
    {"name": "file_ticket", "description": "File the triaged ticket. Call exactly once, after the lookup.",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "required": ["customer_id", "category", "priority", "summary"],
                      "properties": {"customer_id": {"type": "string"},
                                     "category": {"type": "string", "enum": CATEGORIES},
                                     "priority": {"type": "string", "enum": PRIORITIES},
                                     "summary": {"type": "string", "description": "One sentence."}}}},
]


def validate(args: dict) -> str | None:
    """The checks a strict API would do. Returns an error message, or None if the call is valid."""
    schema = TOOLS[1]["input_schema"]
    missing = [k for k in schema["required"] if k not in args]
    extra = [k for k in args if k not in schema["properties"]]
    if missing or extra:
        return f"missing {missing} / unexpected {extra}"
    if args["category"] not in CATEGORIES:
        return f"category {args['category']!r} is not one of {CATEGORIES}"
    if args["priority"] not in PRIORITIES:
        return f"priority {args['priority']!r} is not one of {PRIORITIES}"
    return None


def run_tool(name: str, args: dict, state: dict) -> tuple[str, bool]:
    if name == "lookup_customer":
        c = CUSTOMERS.get(str(args.get("email", "")).lower())
        return (json.dumps(c) if c else "No customer with that email."), False
    if name == "file_ticket":
        err = validate(args)
        if err:
            state["invalid_calls"] += 1
            return f"Invalid file_ticket call: {err}. Fix it and call again.", True
        state["filed"].append(args)
        return "Ticket filed.", False
    state["invalid_calls"] += 1
    return f"Unknown tool {name!r}.", True


# --------------------------------------------------------------------------- backends

class Claude:
    label = CLAUDE_MODEL

    def __init__(self):
        from provider import make_client, model_id, request_options
        self.client, self.model, self.opts = make_client(), model_id(CLAUDE_MODEL), request_options()

    def run(self, message: str, state: dict) -> None:
        messages = [{"role": "user", "content": message}]
        for _ in range(6):
            r = self.client.beta.messages.create(model=self.model, max_tokens=2000, system=SYSTEM, tools=TOOLS,
                                                 messages=messages, output_config={"effort": "low"}, **self.opts)
            state["tokens_in"] += r.usage.input_tokens + (r.usage.cache_read_input_tokens or 0)
            state["tokens_out"] += r.usage.output_tokens
            state["frontier_in"] = state.get("frontier_in", 0) + r.usage.input_tokens + (r.usage.cache_read_input_tokens or 0)
            state["frontier_out"] = state.get("frontier_out", 0) + r.usage.output_tokens
            messages.append({"role": "assistant", "content": r.content})
            calls = [b for b in r.content if b.type == "tool_use"]
            if not calls:
                return
            results = []
            for c in calls:
                out, err = run_tool(c.name, c.input, state)
                results.append({"type": "tool_result", "tool_use_id": c.id, "content": out, "is_error": err})
            messages.append({"role": "user", "content": results})
            if state["filed"]:
                return


class OpenAICompatible:
    """Any server that speaks the OpenAI chat-completions format with tools: Ollama, vLLM, LM Studio, llama.cpp."""

    def __init__(self, base_url: str, model: str):
        self.url, self.model, self.label = base_url.rstrip("/") + "/chat/completions", model, model
        self.tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                         "parameters": t["input_schema"]}} for t in TOOLS]

    def _post(self, payload: dict) -> dict:
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer local"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read())

    def run(self, message: str, state: dict) -> None:
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": message}]
        for _ in range(6):
            r = self._post({"model": self.model, "messages": messages, "tools": self.tools, "temperature": 0})
            usage = r.get("usage") or {}
            state["tokens_in"] += usage.get("prompt_tokens", 0)
            state["tokens_out"] += usage.get("completion_tokens", 0)
            msg = r["choices"][0]["message"]
            messages.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
            calls = msg.get("tool_calls") or []
            if not calls:
                return
            for c in calls:
                try:
                    args = json.loads(c["function"]["arguments"] or "{}") if isinstance(c["function"]["arguments"], str) \
                        else c["function"]["arguments"]
                    out, _ = run_tool(c["function"]["name"], args, state)
                except json.JSONDecodeError:
                    state["invalid_calls"] += 1
                    out = "Your tool arguments were not valid JSON. Call the tool again."
                messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": out})
            if state["filed"]:
                return


class Mixed:
    """Open-weight model first; escalate to Claude when the local model fails to file a valid ticket. The validator
    catches *invalid* output. It can't catch output that is valid but wrong: that's what the eval is for."""

    def __init__(self, local: OpenAICompatible, frontier: Claude):
        self.local, self.frontier, self.label = local, frontier, f"mixed ({local.label} + escalation)"
        self.escalations = 0

    def run(self, message: str, state: dict) -> None:
        try:
            self.local.run(message, state)
        except Exception:
            pass
        if not state["filed"] or state["invalid_calls"] >= 2:
            self.escalations += 1
            state["filed"].clear()
            state["escalated"] = True
            self.frontier.run(message, state)


# --------------------------------------------------------------------------- evaluation

def evaluate(backend) -> dict:
    rows, t0 = [], time.time()
    for email, text, category, priority in TICKETS:
        state = {"filed": [], "invalid_calls": 0, "tokens_in": 0, "tokens_out": 0, "escalated": False,
                 "frontier_in": 0, "frontier_out": 0}
        started = time.time()
        try:
            backend.run(f"Ticket from {email}:\n{text}", state)
            error = None
        except Exception as exc:  # a crashed or unreachable server is reported, not hidden
            error = f"{type(exc).__name__}: {exc}"
        got = state["filed"][0] if state["filed"] else {}
        rows.append({"ticket": text[:40], "expected": (category, priority),
                     "got": (got.get("category"), got.get("priority")),
                     "correct": got.get("category") == category and got.get("priority") == priority
                     and got.get("customer_id") == CUSTOMERS[email]["customer_id"],
                     "filed": bool(got), "invalid_calls": state["invalid_calls"], "error": error,
                     "seconds": round(time.time() - started, 1), "tokens_in": state["tokens_in"],
                     "tokens_out": state["tokens_out"], "escalated": state["escalated"],
                     "frontier_in": state["frontier_in"], "frontier_out": state["frontier_out"]})
        r = rows[-1]
        print(f"  {'ok ' if r['correct'] else 'BAD'} {r['ticket']:<42} expected {category}/{priority:<3} "
              f"got {r['got'][0]}/{r['got'][1]}" + (f"  invalid calls: {r['invalid_calls']}" if r["invalid_calls"] else "")
              + (f"  ERROR {error}" if error else "") + ("  (escalated)" if r["escalated"] else ""))
    n = len(rows)
    tin, tout = sum(r["tokens_in"] for r in rows), sum(r["tokens_out"] for r in rows)
    fin, fout = sum(r["frontier_in"] for r in rows), sum(r["frontier_out"] for r in rows)
    return {"model": backend.label, "correct": sum(r["correct"] for r in rows), "of": n,
            "not_filed": sum(not r["filed"] for r in rows), "invalid_calls": sum(r["invalid_calls"] for r in rows),
            "escalated": sum(r["escalated"] for r in rows),
            "seconds_per_ticket": round((time.time() - t0) / n, 1), "tokens_in": tin, "tokens_out": tout,
            "api_cost": round((fin * CLAUDE_PRICE[0] + fout * CLAUDE_PRICE[1]) / 1e6, 4)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["claude", "local", "both", "mixed", "all"], default="both")
    ap.add_argument("--base-url", default="http://localhost:11434/v1", help="OpenAI-compatible server (Ollama default)")
    ap.add_argument("--model", default="qwen3:8b", help="model name on the local server")
    args = ap.parse_args()
    claude = Claude() if args.backend != "local" else None
    local = OpenAICompatible(args.base_url, args.model) if args.backend != "claude" else None
    backends = {"claude": [claude], "local": [local], "both": [claude, local], "mixed": [Mixed(local, claude)],
                "all": [claude, local, Mixed(local, claude)]}[args.backend]
    results = []
    for b in backends:
        print(f"\n=== {b.label}")
        results.append(evaluate(b))
    print(f"\n{'model':<36}{'correct':>9}{'not filed':>11}{'invalid calls':>15}{'escalated':>11}{'s/ticket':>10}{'API $':>9}")
    for r in results:
        print(f"{r['model']:<36}{r['correct']:>5}/{r['of']:<3}{r['not_filed']:>11}{r['invalid_calls']:>15}"
              f"{r['escalated']:>11}{r['seconds_per_ticket']:>10}{r['api_cost']:>9.4f}")

"""Two agents, fully traced with OpenTelemetry using the GenAI semantic conventions.

Companion code for https://www.agenticsystems.ai/blog/watching-the-agents/
Usage:  python traced_agents.py "How much has Bluebird Dental spent, and how many open tickets do they have?"
        python show_trace.py            # print the trace as a tree

A lead agent delegates CRM questions to a specialist agent. Every agent invocation, model call and tool call becomes
a span; all spans share one trace ID, so one request can be followed across both agents. Spans are written to
traces.jsonl (swap the exporter for OTLP to send them to any tracing backend).
"""

import json
import sys
import uuid

import anthropic
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

import crm

MODEL = "claude-opus-5-5"
client = anthropic.Anthropic()


# --------------------------------------------------------------------------- tracing setup

class JsonlExporter(SpanExporter):
    """Append finished spans to a local file. In production use the OTLP exporter instead."""

    def export(self, spans):
        with open("traces.jsonl", "a", encoding="utf-8") as f:
            for s in spans:
                f.write(json.dumps({
                    "name": s.name, "trace_id": f"{s.context.trace_id:032x}", "span_id": f"{s.context.span_id:016x}",
                    "parent_id": f"{s.parent.span_id:016x}" if s.parent else None,
                    "start": s.start_time, "end": s.end_time, "status": s.status.status_code.name,
                    "attributes": dict(s.attributes or {}),
                }) + "\n")
        return SpanExportResult.SUCCESS


provider = TracerProvider(resource=Resource.create({"service.name": "larkspur-support-agents"}))
provider.add_span_processor(SimpleSpanProcessor(JsonlExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("agentic-systems.examples")


# --------------------------------------------------------------------------- identity: who is acting, for whom

AGENTS = {
    "lead":       {"id": "agent.larkspur.lead",       "version": "1.4.0", "name": "Support lead"},
    "specialist": {"id": "agent.larkspur.crm",        "version": "2.0.1", "name": "CRM specialist"},
}
ON_BEHALF_OF = "user:ops-oncall@larkspur.example"  # every action is attributable to a principal


# --------------------------------------------------------------------------- traced primitives

def traced_model_call(agent: str, conversation_id: str, **kwargs):
    with tracer.start_as_current_span(f"chat {MODEL}") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.provider.name", "anthropic")
        span.set_attribute("gen_ai.request.model", MODEL)
        span.set_attribute("gen_ai.agent.name", AGENTS[agent]["name"])
        span.set_attribute("gen_ai.conversation.id", conversation_id)
        r = client.beta.messages.create(model=MODEL, max_tokens=16000, output_config={"effort": "low"},
                                        betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        u = r.usage
        span.set_attribute("gen_ai.usage.input_tokens",
                           u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0))
        span.set_attribute("gen_ai.usage.output_tokens", u.output_tokens)
        span.set_attribute("gen_ai.response.finish_reasons", [r.stop_reason])
        return r


def traced_tool(agent: str, conversation_id: str, call, fn) -> dict:
    with tracer.start_as_current_span(f"execute_tool {call.name}") as span:
        span.set_attribute("gen_ai.operation.name", "execute_tool")
        span.set_attribute("gen_ai.tool.name", call.name)
        span.set_attribute("gen_ai.tool.call.id", call.id)
        span.set_attribute("gen_ai.agent.name", AGENTS[agent]["name"])
        span.set_attribute("gen_ai.conversation.id", conversation_id)
        try:
            return {"type": "tool_result", "tool_use_id": call.id, "content": fn(**call.input)}
        except Exception as exc:
            span.set_attribute("error.type", type(exc).__name__)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            return {"type": "tool_result", "tool_use_id": call.id, "content": f"{type(exc).__name__}: {exc}",
                    "is_error": True}


def invoke_agent(agent: str, task: str, tools: dict, schemas: list, system: str) -> str:
    """One agent run = one invoke_agent span, carrying the agent's identity and who it acts for."""
    a, conversation_id = AGENTS[agent], f"conv_{uuid.uuid4().hex[:12]}"
    with tracer.start_as_current_span(f"invoke_agent {a['name']}") as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")
        span.set_attribute("gen_ai.agent.id", a["id"])
        span.set_attribute("gen_ai.agent.name", a["name"])
        span.set_attribute("gen_ai.agent.version", a["version"])
        span.set_attribute("gen_ai.conversation.id", conversation_id)
        span.set_attribute("app.on_behalf_of", ON_BEHALF_OF)
        messages = [{"role": "user", "content": task}]
        for _ in range(10):
            r = traced_model_call(agent, conversation_id, system=system, tools=schemas, messages=messages)
            messages.append({"role": "assistant", "content": r.content})
            calls = [b for b in r.content if b.type == "tool_use"]
            if not calls:
                return "".join(b.text for b in r.content if b.type == "text")
            messages.append({"role": "user", "content": [traced_tool(agent, conversation_id, c, tools[c.name])
                                                         for c in calls]})
        span.set_status(trace.Status(trace.StatusCode.ERROR, "step limit"))
        return "[step limit]"


# --------------------------------------------------------------------------- the two agents

def ask_crm_specialist(question: str) -> str:
    tools, schemas = crm.TOOLSETS["v2"]
    return invoke_agent("specialist", question, tools, schemas,
                        "You answer precise questions about customers using the CRM tools. Be brief.")


LEAD_TOOLS = {"ask_crm_specialist": ask_crm_specialist}
LEAD_SCHEMAS = [{"name": "ask_crm_specialist",
                 "description": "Ask the CRM specialist agent a question about a customer. Returns its answer.",
                 "input_schema": {"type": "object", "properties": {"question": {"type": "string"}},
                                  "required": ["question"], "additionalProperties": False}}]

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "How much has Bluebird Dental spent, and how many open tickets do they have?"
    print(invoke_agent("lead", question, LEAD_TOOLS, LEAD_SCHEMAS,
                       "You coordinate support work. Delegate customer lookups to the CRM specialist."))
    provider.shutdown()
    print("\nspans written to traces.jsonl - run: python show_trace.py")

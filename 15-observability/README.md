# 15 · Watching the agents

Companion code for the post [Watching the agents: identity, logs and visibility](https://www.agenticsystems.ai/blog/watching-the-agents/).

A lead agent delegates customer questions to a CRM specialist agent. Everything is traced with **OpenTelemetry** using the **GenAI semantic conventions**:

| Span | Name | Key attributes |
|---|---|---|
| an agent run | `invoke_agent {agent name}` | `gen_ai.agent.id`, `gen_ai.agent.version`, `gen_ai.conversation.id`, plus `app.on_behalf_of` (the user it acts for) |
| a model call | `chat {model}` | `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens` / `output_tokens` |
| a tool call | `execute_tool {tool name}` | `gen_ai.tool.name`, `gen_ai.tool.call.id`, `error.type` on failure |

Because the specialist is invoked *inside* the lead's tool call, its spans nest under the lead's, and one trace ID follows the request across both agents.

Spans are written to `traces.jsonl` by a tiny exporter, so you don't need a tracing backend. To send them to Jaeger, Grafana, Honeycomb or another backend, swap `JsonlExporter` for the OTLP exporter.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."

python traced_agents.py "How much has Bluebird Dental spent, and how many open tickets do they have?"
python show_trace.py
```

`show_trace.py` prints the trace as a tree. Here's the shape from a test run with a scripted stand-in model, so the timings and token counts are not real:

```
invoke_agent Support lead     id=agent.larkspur.lead@1.4.0 for user:ops-oncall@larkspur.example
  chat claude-opus-5-5          in=900 out=60
  execute_tool ask_crm_specialist
    invoke_agent CRM specialist   id=agent.larkspur.crm@2.0.1 for user:ops-oncall@larkspur.example
      chat claude-opus-5-5          in=1500 out=50
      execute_tool search_customers
      chat claude-opus-5-5
      execute_tool get_customer_context   ERROR ToolError
      chat claude-opus-5-5
      execute_tool get_customer_context
      chat claude-opus-5-5
  chat claude-opus-5-5
```

The GenAI conventions are still marked *Development* status, so attribute names can change. Pin the conventions version you follow.

## Things to try

1. **Count the cost of delegation.** Sum `gen_ai.usage.input_tokens` per `gen_ai.agent.name`. How much of the total did the hand-off add?
2. **Find a slow step.** Add `time.sleep(2)` to a CRM tool and spot it in the tree.
3. **Propagate across a process boundary.** Inject the current trace context into an outgoing request (MCP carries it as `traceparent` in a request's `_meta`) and continue the trace on the other side.

# 20 · Should this be an agent?

Companion code for the post [Should this be an agent? A decision guide](https://www.agenticsystems.ai/blog/should-this-be-an-agent/).

A six-question rubric that recommends the simplest approach that will work: a **single call or workflow**, a **workflow with a small agentic step**, an **agent** (with guardrails or human approval), or **not yet** (an assistant, with a person deciding). No API calls, no dependencies beyond Python 3.10+.

| Question | Why it matters |
|---|---|
| Can you write down the steps in advance? | Known steps belong in code; agents are for paths that depend on what's found |
| Can the result be checked automatically? | Checkable results let the harness decide when it's done |
| What does a mistake cost, and can it be undone? | Sets how much human approval is needed |
| How many tasks, and how fast? | Agents take many calls per task |
| How much is one completed task worth? | The value has to pay for the extra calls |
| How many trifecta conditions apply? | Untrusted input + private data + external action needs a secure design |

## Run it

```bash
python rubric.py                 # six worked examples
python rubric.py --interactive   # answer the questions for your own use case
```

```
## Fix failing tests in our codebase
   -> Agent with guardrails
      why: The path depends on what's found along the way, which is what agents are for (post #1).
      why: The result can be checked automatically, so let the harness decide when it's done (post #11).
      ...

## Approve or deny insurance claims
   -> Not yet: keep a person doing it, with an assistant
```

The interactive version in the post uses the same rules; all 729 combinations of answers were checked to give identical output.

## Things to try

1. **Make it yours.** The rules in `recommend()` are about forty lines. Add the questions your organisation always asks (data residency, regulatory review, who's on call) and the thresholds you actually use.
2. **Score your backlog.** Put every proposed agent project into `EXAMPLES` and see how many really need to be agents.
3. **Revisit it.** Re-run after model prices or capabilities change; tasks move up the ladder over time.

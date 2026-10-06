# 14 · Agents that design agents

Companion code for the post [Agents that design agents: ADAS → DGM → AlphaEvolve](https://www.agenticsystems.ai/blog/agents-that-design-agents/).

A tiny version of the loop behind these systems, in the style of **GEPA** (reflective prompt evolution). The "agent" being improved is a single prompt that classifies support tickets. The tickets in `data.py` are labelled by house rules the starting prompt never mentions: suspicious logins are *security* even when money is involved, plan changes are *account* rather than *billing*, and so on.

Each round:

1. **Select** a parent from the *Pareto front*: every prompt that's the best on at least one training ticket. Partial solutions survive even if they aren't the best overall.
2. **Run** it on the training tickets and collect the failures.
3. **Reflect:** a model reads the failures *in natural language* and proposes an improved prompt that states general rules, not specific tickets.
4. **Evaluate** the child on the training set and add it to the pool.

At the end, the best prompt and the original are both scored on **held-out test tickets** the loop never saw. That's the only number that tells you whether it learned rules or memorised examples.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."

python evolve.py --rounds 6
python evolve.py --rounds 6 --seed 1     # a different search path
```

Example output shape:

```
round 0 (seed prompt): train …/12
round 1: parent train …/12 -> child …/12   diagnosis: …
…
=== held-out test: seed prompt …/12  vs  evolved prompt (round …) …/12
```

## Read the result skeptically

Twelve test tickets is a tiny eval (see [post #12](https://www.agenticsystems.ai/blog/evals-for-agents/)). A difference of one or two tickets is noise. Run several seeds before believing an improvement, and read the evolved prompt: did it learn the house rules, or does it quote training tickets?

## Things to try

1. **Remove the Pareto front.** Always pick the single best prompt as the parent. Does the search get stuck sooner?
2. **Let it overfit.** Delete "do not list or quote these specific tickets" from the reflection prompt and compare train vs test.
3. **Swap the task.** Replace `data.py` with your own labelled examples. The loop doesn't care what the task is, only that code can grade it.

"""Shared helpers: one function to call the model, plus a usage meter so you can compare patterns."""

import time
from dataclasses import dataclass, field

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5-5"
client = anthropic.AsyncAnthropic()


@dataclass
class Meter:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    started: float = field(default_factory=time.perf_counter)

    def report(self, pattern: str) -> None:
        elapsed = time.perf_counter() - self.started
        print(
            f"\n--- {pattern}: {self.calls} model calls, "
            f"{self.input_tokens:,} input + {self.output_tokens:,} output tokens, {elapsed:.1f}s ---"
        )


meter = Meter()


async def ask(prompt: str, *, system: str = "", schema: type[BaseModel] | None = None, effort: str = "low"):
    """One model call. Returns text, or a validated `schema` instance when one is given.

    Effort defaults to "low": every step in a workflow is small and well-specified,
    so we raise it only where a step needs real judgment.
    """
    kwargs = dict(
        model=MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": effort},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # re-run on a recommended model if this one declines
    )
    if system:
        kwargs["system"] = system

    if schema:
        response = await client.beta.messages.parse(output_format=schema, **kwargs)
    else:
        response = await client.beta.messages.create(**kwargs)

    meter.calls += 1
    meter.input_tokens += response.usage.input_tokens
    meter.output_tokens += response.usage.output_tokens

    if response.stop_reason == "refusal":
        raise RuntimeError("the model declined this step")
    if schema:
        return response.parsed_output
    return "".join(block.text for block in response.content if block.type == "text")

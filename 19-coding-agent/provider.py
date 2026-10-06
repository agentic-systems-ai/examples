"""Run the same example on the Claude API or on Amazon Bedrock, chosen by an environment variable.

    LLM_PROVIDER=anthropic   (default)  uses ANTHROPIC_API_KEY or an `ant auth login` profile
    LLM_PROVIDER=bedrock                uses your AWS credentials; set AWS_REGION (default us-east-1)

Each example folder has its own copy of this file, so every folder stays self-contained.
"""

import os

import anthropic

BEDROCK = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower() == "bedrock"


def make_client():
    if BEDROCK:
        return anthropic.AnthropicBedrockMantle(aws_region=os.environ.get("AWS_REGION", "us-east-1"))
    return anthropic.Anthropic()


def model_id(name: str) -> str:
    """Bedrock model IDs carry an `anthropic.` prefix, e.g. anthropic.claude-opus-5-5."""
    return f"anthropic.{name}" if BEDROCK else name


def request_options(*betas: str) -> dict:
    """Options that differ by provider. Server-side refusal fallbacks exist only on the Claude API."""
    if BEDROCK:
        return {"betas": list(betas)} if betas else {}
    return {"betas": ["server-side-fallback-2026-07-01", *betas], "fallbacks": "default"}

"""Models, embeddings and a structured-output helper that also counts tokens,
so every report can show what it cost. LangChain imports happen inside the
functions, so the rest of the kit can be tested without AWS."""

from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass
class Meter:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, usage: dict | None):
        self.calls += 1
        if usage:
            self.input_tokens += int(usage.get("input_tokens", 0))
            self.output_tokens += int(usage.get("output_tokens", 0))

    @property
    def usd(self) -> float:
        return (self.input_tokens * config.PRICE_IN + self.output_tokens * config.PRICE_OUT) / 1_000_000

    def line(self) -> str:
        return (
            f"{self.calls} model calls, {self.input_tokens:,} input + {self.output_tokens:,} output tokens, "
            f"about US${self.usd:.3f}"
        )


METER = Meter()


def get_llm(guardrail: bool = False, max_tokens: int = 2500):
    """Claude on Bedrock (default) or an offshore model (public data only)."""
    if config.LLM_BACKEND == "nvidia":
        from langchain_nvidia_ai_endpoints import ChatNVIDIA  # pip install langchain-nvidia-ai-endpoints

        return ChatNVIDIA(model=config.NVIDIA_MODEL, temperature=0.1, max_tokens=max_tokens)

    if config.LLM_BACKEND == "groq":
        from langchain_groq import ChatGroq  # pip install langchain-groq

        # Free tier caps output at 1000 tokens/min; cap per-call to stay under it.
        groq_max = min(max_tokens, config.GROQ_MAX_TOKENS)
        return ChatGroq(model=config.GROQ_MODEL, temperature=0.0, max_tokens=groq_max)

    from langchain_aws import ChatBedrockConverse

    kwargs = {}
    if guardrail and config.GUARDRAIL_ID:
        kwargs["guardrail_config"] = {
            "guardrailIdentifier": config.GUARDRAIL_ID,
            "guardrailVersion": config.GUARDRAIL_VERSION,
            "trace": "enabled",
        }
    return ChatBedrockConverse(
        model=config.LLM_MODEL_ID,
        provider=config.LLM_PROVIDER,
        region_name=config.REGION,
        temperature=0.0,
        max_tokens=max_tokens,
        **kwargs,
    )


def get_embeddings():
    from langchain_aws import BedrockEmbeddings

    return BedrockEmbeddings(model_id=config.EMBED_MODEL_ID, region_name=config.REGION)


def _structured_groq(llm, schema, messages, meter: Meter):
    """Groq-specific structured output: inject JSON schema into the prompt and parse the reply.

    Groq's Qwen model uses a non-standard tool-call format that the API rejects, and
    json_object mode requires the word 'json' in the prompt. Easier to just ask the model
    to output JSON directly and parse it ourselves.  Retries once on rate-limit errors.
    """
    import json
    import re
    import time

    schema_text = json.dumps(schema.model_json_schema(), indent=2)
    json_instruction = (
        "\n\nOutput your answer as a single JSON object matching this schema exactly. "
        "Be concise. No markdown, no explanation — only the JSON:\n" + schema_text
    )

    # Append the JSON instruction to the last human message.
    augmented = [
        (role, content + json_instruction if role == "human" and i == len(messages) - 1 else content)
        for i, (role, content) in enumerate(messages)
    ]

    for attempt in range(3):
        try:
            reply = llm.invoke(augmented)
            break
        except Exception as e:
            # Groq rate-limit: wait the suggested time then retry.
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait = 65 if attempt < 2 else 0
                if wait:
                    print(f"    Groq rate limit — waiting {wait}s …")
                    time.sleep(wait)
                    continue
            raise
    else:
        raise RuntimeError("Groq rate limit: still blocked after retries.")

    meter.add(getattr(reply, "usage_metadata", None))

    text = text_of(reply).strip()
    # Strip markdown code fences the model may add anyway.
    text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```$", "", text)
    # Qwen sometimes adds <think>…</think> before the JSON; drop it.
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)
    text = text.strip()

    try:
        return schema.model_validate_json(text)
    except Exception:
        # Truncated response: try to salvage complete items from a partial JSON array.
        # Find the last complete object in a "candidates" or similar list.
        truncated = re.sub(r',\s*\{[^}]*$', '', text)   # drop last incomplete object
        truncated = re.sub(r'(\[.*\])', r'\1', truncated, flags=re.DOTALL)
        # Close any open braces/brackets so the JSON parser can proceed.
        opens = truncated.count('{') - truncated.count('}')
        brackets = truncated.count('[') - truncated.count(']')
        truncated += '}' * max(opens, 0) + ']' * max(brackets, 0)
        # Close the root object if needed.
        if not truncated.rstrip().endswith('}'):
            truncated = truncated.rstrip().rstrip(',') + '}' * (truncated.count('{') - truncated.count('}'))
        try:
            return schema.model_validate_json(truncated)
        except Exception:
            print(f"    Warning: could not parse Groq response; skipping batch.")
            # Return an empty result: fill every list field with [] so the caller can iterate.
            empty = {k: [] for k, f in schema.model_fields.items()
                     if hasattr(f.annotation, '__origin__') and f.annotation.__origin__ is list}
            return schema.model_construct(**empty)


def structured(llm, schema, messages, meter: Meter = METER):
    """Ask for a Pydantic object and record token usage. Returns the object."""
    # Use the Groq-specific path only for real ChatGroq instances, not fakes.
    if type(llm).__name__ == "ChatGroq":
        return _structured_groq(llm, schema, messages, meter)

    runner = llm.with_structured_output(schema, include_raw=True)
    out = runner.invoke(messages)
    raw = out.get("raw") if isinstance(out, dict) else None
    meter.add(getattr(raw, "usage_metadata", None))
    if isinstance(out, dict):
        if out.get("parsing_error"):
            raise ValueError(f"Model output didn't match {schema.__name__}: {out['parsing_error']}")
        return out["parsed"]
    return out


def text_of(message) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)

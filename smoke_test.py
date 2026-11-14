"""Prove AWS works before building anything on it (VIBE_CODING step 3).

1. Asks Claude Haiku 4.5 (the `au.` inference profile in config.py) to "Reply with OK".
2. Embeds the word "quarry" with Titan Text Embeddings V2 and prints the vector length.
3. Prints the total tokens used and the rough cost.

Uses your default AWS profile. Never prints credentials or account details.
Run:  python smoke_test.py
"""

from __future__ import annotations

import json
import sys

import config
from llm import Meter, get_llm, text_of

HINTS = {
    "AccessDeniedException": "Check the IAM policy in README step 2, and open Claude Haiku 4.5 once in the "
    "Bedrock console playground (Sydney); submit Anthropic's use case form if it asks.",
    "ResourceNotFoundException": "The model isn't available to this account in Sydney yet. Open it in the "
    "Bedrock console playground (Sydney) once, then rerun.",
    "ThrottlingException": "Your keys and permissions work, but Bedrock's quota for this account is used up or "
    "very low (common on new accounts). Check Service Quotas > Amazon Bedrock in Sydney, or wait and rerun.",
    "ValidationException": "Check LLM_MODEL_ID and EMBED_MODEL_ID in .env against the Bedrock console.",
    "UnrecognizedClientException": "Your AWS keys look wrong. Rerun `aws configure` yourself (never paste keys into chat).",
    "NoCredentialsError": "No AWS credentials found. Run `aws configure` yourself (never paste keys into chat).",
}


def check_claude(llm=None, meter: Meter | None = None) -> str:
    """Send one tiny prompt to Claude and return its reply."""
    llm = llm or get_llm(max_tokens=10)
    reply = llm.invoke([("human", "Reply with OK")])
    if meter is not None:
        meter.add(getattr(reply, "usage_metadata", None))
    return text_of(reply).strip()


def check_embedding(client=None, text: str = "quarry") -> tuple[int, int]:
    """Embed one word with Titan V2. Returns (vector length, input tokens)."""
    if client is None:
        import boto3

        client = boto3.client("bedrock-runtime", region_name=config.REGION)
    resp = client.invoke_model(
        modelId=config.EMBED_MODEL_ID,
        body=json.dumps({"inputText": text}),
        contentType="application/json",
        accept="application/json",
    )
    body = json.loads(resp["body"].read())
    return len(body["embedding"]), int(body.get("inputTextTokenCount", 0))


def explain(err: Exception) -> str:
    """One readable line for an AWS error, with a hint. Never includes credentials."""
    code = type(err).__name__
    response = getattr(err, "response", None)
    if isinstance(response, dict):
        code = response.get("Error", {}).get("Code", code)
    hint = HINTS.get(code, "Read the error above and check README 'Troubleshooting'.")
    return f"{code}: {err}\n   Hint: {hint}"


def main() -> int:
    if config.REGION != "ap-southeast-2":
        print(f"Refusing to run: AWS_REGION is {config.REGION}, but this project uses ap-southeast-2 only.")
        return 1
    if config.LLM_BACKEND != "bedrock":
        print(f"Refusing to run: LLM_BACKEND is {config.LLM_BACKEND}. Set it to bedrock in .env for this test.")
        return 1

    meter = Meter()
    ok = True

    print(f"1. Claude: {config.LLM_MODEL_ID} in {config.REGION}")
    try:
        reply = check_claude(meter=meter)
        print(f"   Reply: {reply}")
        ok &= "OK" in reply.upper()
    except Exception as err:  # noqa: BLE001  show any failure in plain English
        print(f"   FAILED. {explain(err)}")
        ok = False

    print(f"2. Titan embeddings: {config.EMBED_MODEL_ID}")
    embed_tokens = 0
    try:
        length, embed_tokens = check_embedding()
        print(f"   Vector length: {length}")
    except Exception as err:  # noqa: BLE001
        print(f"   FAILED. {explain(err)}")
        ok = False

    total = meter.input_tokens + meter.output_tokens + embed_tokens
    print(f"3. Tokens: Claude {meter.input_tokens} in + {meter.output_tokens} out, Titan {embed_tokens}; "
          f"total {total} (about US${meter.usd:.5f} for Claude)")
    print("AWS works." if ok else "Something failed: see the hints above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

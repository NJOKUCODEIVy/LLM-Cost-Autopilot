"""
Unified model interface for the LLM Cost Autopilot.

send_request() calls any model in the registry and always returns the same
Response shape, whichever provider handled the request.
"""

import os
import re
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai
from google.genai import types
from openai import OpenAI
import streamlit as st

from registry import MODEL_REGISTRY, ModelConfig

# override=True makes .env win over any older keys already set in the terminal
load_dotenv(override=True)


def _get_secret_value(section: str, key: str, env_name: str) -> str | None:
    value = os.getenv(env_name)
    if value:
        return value
    try:
        if section in st.secrets and key in st.secrets[section]:
            value = st.secrets[section][key]
            if value:
                return str(value)
    except Exception:
        pass
    return None


def _get_groq_client() -> OpenAI:
    api_key = _get_secret_value("groq", "api_key", "GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing GROQ_API_KEY. Add it to your environment, .env, or Streamlit secrets before using Groq models."
        )
    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        timeout=30.0,   # Seconds per attempt
        max_retries=1,  # One retry, then give up
    )


def _get_gemini_client() -> genai.Client:
    api_key = _get_secret_value("gemini", "api_key", "GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing GEMINI_API_KEY. Add it to your environment, .env, or Streamlit secrets before using Gemini models."
        )
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=30_000,  # Milliseconds per attempt (30 seconds)
            retry_options=types.HttpRetryOptions(attempts=2),  # Two tries at most
        ),
    )


@dataclass
class Response:
    text: str           # The model's answer
    input_tokens: int   # Prompt tokens, including any formatting the provider adds
    output_tokens: int  # Answer tokens plus thinking tokens (both are billed as output)
    latency: float      # Seconds from sending the request to getting the full answer
    cost: float         # USD, at the paid rates in the registry
    model_id: str       # Which model produced this answer


def _call_groq(prompt: str, model: ModelConfig) -> tuple[str, int, int]:
    client = _get_groq_client()
    result = client.chat.completions.create(
        model=model.model_id,
        messages=[{"role": "user", "content": prompt}],
    )
    text = result.choices[0].message.content or ""
    # Some models put their thinking inside <think> tags; keep only the final answer
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    usage = result.usage
    if usage is None:
        raise ValueError(f"{model.model_id} returned no token usage, so cost can't be calculated")
    return text, usage.prompt_tokens, usage.completion_tokens


def _call_gemini(prompt: str, model: ModelConfig) -> tuple[str, int, int]:
    client = _get_gemini_client()
    result = client.models.generate_content(model=model.model_id, contents=prompt)
    usage = result.usage_metadata
    if usage is None:
        raise ValueError(f"{model.model_id} returned no token usage, so cost can't be calculated")
    input_tokens = usage.prompt_token_count or 0
    # Gemini reports thinking separately but bills it as output, so add it in
    output_tokens = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
    return (result.text or "").strip(), input_tokens, output_tokens


PROVIDER_CALLS = {
    "groq": _call_groq,
    "gemini": _call_gemini,
}


def send_request(prompt: str, model_config: ModelConfig) -> Response:
    """Send a prompt to any registry model and return a standardized Response."""
    call = PROVIDER_CALLS.get(model_config.provider)
    if call is None:
        raise ValueError(f"No caller for provider '{model_config.provider}'")

    start = time.perf_counter()
    text, input_tokens, output_tokens = call(prompt, model_config)
    latency = time.perf_counter() - start

    return Response(
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency=latency,
        cost=model_config.cost(input_tokens, output_tokens),
        model_id=model_config.model_id,
    )


if __name__ == "__main__":
    prompt = "Explain what an API is in one sentence."
    print(f"Prompt: {prompt}\n")
    for model in MODEL_REGISTRY.values():
        try:
            r = send_request(prompt, model)
            print(f"[{model.name}] {r.text}")
            print(f"    tokens in/out: {r.input_tokens}/{r.output_tokens} | "
                  f"latency: {r.latency:.2f}s | cost: ${r.cost:.7f}\n")
        except Exception as e:
            print(f"[{model.name}] FAILED: {e}\n")
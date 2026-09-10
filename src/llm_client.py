"""
llm_client.py — thin wrapper around an OpenAI-compatible chat endpoint.

The judgment steps of the pipeline (classify response type, enumerate
experimental units, narrow extraction, figure reading) call the model
THROUGH THIS MODULE ONLY. Nothing else in src/ talks to a model.

Configuration is read from environment variables so the same code runs
on CyVerse (AI Verde gateway, Claude-series models) or anywhere else
with an OpenAI-compatible API:

    OPENAI_API_KEY   required — the gateway / provider key
    LLM_API_BASE     default: https://llm-api.cyverse.ai/v1
    LLM_MODEL        default: see DEFAULT_MODEL below
    LLM_VISION_MODEL default: same as LLM_MODEL

Every call is logged (model, purpose, token usage) to the module-level
CALL_LOG list so a workflow script can append it to PROMPT_ACTION_LOG.md.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_API_BASE = "https://llm-api.cyverse.ai/v1"
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "anthropic/claude-sonnet-4")

CALL_LOG: list[dict] = []


@dataclass
class LLMConfig:
    api_key: Optional[str] = None
    api_base: str = DEFAULT_API_BASE
    model: str = DEFAULT_MODEL
    vision_model: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 4096
    max_retries: int = 3
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            api_key=os.environ.get("OPENAI_API_KEY"),
            api_base=os.environ.get("LLM_API_BASE", DEFAULT_API_BASE),
            model=os.environ.get("LLM_MODEL", DEFAULT_MODEL),
            vision_model=os.environ.get("LLM_VISION_MODEL"),
        )


class LLMNotConfigured(RuntimeError):
    """Raised when a judgment step is reached but no API key is set."""


def _client(cfg: LLMConfig):
    try:
        from openai import OpenAI
    except ImportError as e:  # pragma: no cover
        raise ImportError("openai package not installed — pip install openai") from e
    if not cfg.api_key:
        raise LLMNotConfigured(
            "OPENAI_API_KEY is not set. Export your AI Verde (or other OpenAI-"
            "compatible) key before running the LLM stages of the pipeline."
        )
    return OpenAI(api_key=cfg.api_key, base_url=cfg.api_base)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return m.group(1) if m else text


def parse_json_response(text: str):
    """Parse a JSON object/array from a model reply, tolerating code fences
    and leading prose. Raises ValueError if nothing parseable is found."""
    cleaned = _strip_code_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # fall back: first {...} or [...] block
    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Model reply was not valid JSON:\n{text[:500]}")


def chat(
    system: str,
    user: str,
    *,
    purpose: str,
    cfg: Optional[LLMConfig] = None,
    image_png_path: Optional[Path] = None,
    json_mode: bool = True,
) -> str:
    """
    One chat-completion call. Returns the assistant text. If
    image_png_path is given the user turn carries the image (vision call)
    and cfg.vision_model (or cfg.model) is used.
    """
    cfg = cfg or LLMConfig.from_env()
    client = _client(cfg)
    model = (cfg.vision_model or cfg.model) if image_png_path else cfg.model

    if image_png_path:
        b64 = base64.b64encode(Path(image_png_path).read_bytes()).decode("ascii")
        user_content = [
            {"type": "text", "text": user},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
    else:
        user_content = user

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    last_err: Optional[Exception] = None
    for attempt in range(1, cfg.max_retries + 1):
        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                **cfg.extra,
            )
            text = resp.choices[0].message.content or ""
            usage = getattr(resp, "usage", None)
            CALL_LOG.append({
                "purpose": purpose,
                "model": model,
                "attempt": attempt,
                "seconds": round(time.time() - t0, 2),
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "image": str(image_png_path) if image_png_path else None,
            })
            if json_mode:
                parse_json_response(text)  # validate; raise -> retry
            return text
        except Exception as e:  # noqa: BLE001 — retry any provider/parse error
            last_err = e
            CALL_LOG.append({"purpose": purpose, "model": model, "attempt": attempt, "error": repr(e)[:300]})
            time.sleep(min(2 ** attempt, 10))
    raise RuntimeError(f"LLM call '{purpose}' failed after {cfg.max_retries} attempts: {last_err!r}")


def chat_json(system: str, user: str, *, purpose: str, cfg: Optional[LLMConfig] = None,
              image_png_path: Optional[Path] = None):
    """chat() + parse_json_response()."""
    return parse_json_response(chat(system, user, purpose=purpose, cfg=cfg,
                                    image_png_path=image_png_path, json_mode=True))

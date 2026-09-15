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
    max_tokens: int = 8000
    max_tokens_cap: int = 24000
    max_retries: int = 4
    request_timeout: float = 180.0
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        extra: dict = {}
        # Some reasoning-model deployments (observed on nrp/glm-5 via AI
        # Verde) accept this Qwen/GLM-style flag to skip chain-of-thought
        # entirely — a ~50x speedup on that model — but it is NOT a
        # standard OpenAI param and other models/deployments on the same
        # gateway may reject an unrecognized extra_body key. Opt in per
        # model with LLM_DISABLE_THINKING=1 rather than defaulting it on.
        # parse_json_response() handles either style of reply either way
        # (reasoning in its own field, or chain-of-thought text ahead of
        # the real JSON in content), so this is purely a speed knob.
        if os.environ.get("LLM_DISABLE_THINKING", "").lower() in ("1", "true", "yes"):
            extra["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
        return cls(
            api_key=os.environ.get("OPENAI_API_KEY"),
            api_base=os.environ.get("LLM_API_BASE", DEFAULT_API_BASE),
            model=os.environ.get("LLM_MODEL", DEFAULT_MODEL),
            vision_model=os.environ.get("LLM_VISION_MODEL"),
            extra=extra,
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
    return OpenAI(api_key=cfg.api_key, base_url=cfg.api_base, timeout=cfg.request_timeout, max_retries=0)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return m.group(1) if m else text


def _iter_balanced_json_candidates(text: str):
    """
    Yield every top-level {...} or [...] substring of text whose braces
    are actually balanced (respecting string literals and escapes), in
    the order they appear. Needed because some reasoning-model
    deployments (e.g. GLM with thinking disabled via extra_body) put
    their chain-of-thought directly in the answer content ahead of the
    real JSON, rather than in a separate reasoning_content field —
    "first '{' to last '}'" then spans the prose in between and never
    parses. Scanning for genuinely balanced blocks and trying them
    LAST-FIRST (the real answer is usually what the model settles on at
    the end) finds the real payload regardless of which style a given
    deployment uses.
    """
    candidates = []
    depth = 0
    start = None
    in_string = False
    escape = False
    opener = closer = None
    for i, ch in enumerate(text):
        if start is None:
            if ch in "{[":
                start, opener = i, ch
                closer = "}" if ch == "{" else "]"
                depth = 1
                in_string = False
                escape = False
            continue
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                candidates.append(text[start:i + 1])
                start = None
    return candidates


def parse_json_response(text: str):
    """Parse a JSON object/array from a model reply, tolerating code
    fences, leading/trailing prose, and chain-of-thought text that
    precedes the real JSON in `text` itself (see
    _iter_balanced_json_candidates). Tries candidates last-to-first
    since the real answer is usually the one the model produces after
    any reasoning. Raises ValueError if nothing parseable is found."""
    cleaned = _strip_code_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    candidates = _iter_balanced_json_candidates(cleaned)
    for candidate in reversed(candidates):
        try:
            return json.loads(candidate)
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
    verbose: bool = True,
) -> str:
    """
    One chat-completion call. Returns the assistant text. If
    image_png_path is given the user turn carries the image (vision call)
    and cfg.vision_model (or cfg.model) is used. Prints a one-line
    progress note before/after each attempt (verbose=True, the default)
    so a long-running batch never looks hung — every call also has a
    hard cfg.request_timeout so a slow/overloaded model pool fails
    instead of blocking forever.
    """
    cfg = cfg or LLMConfig.from_env()
    client = _client(cfg)
    model = (cfg.vision_model or cfg.model) if image_png_path else cfg.model
    if verbose:
        print(f"  [llm] {purpose}: calling {model} (timeout={cfg.request_timeout:.0f}s)...", flush=True)

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
    cur_max_tokens = cfg.max_tokens
    for attempt in range(1, cfg.max_retries + 1):
        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=cfg.temperature,
                max_tokens=cur_max_tokens,
                **cfg.extra,
            )
            choice = resp.choices[0]
            text = choice.message.content or ""
            reasoning = getattr(choice.message, "reasoning_content", None)
            usage = getattr(resp, "usage", None)
            CALL_LOG.append({
                "purpose": purpose,
                "model": model,
                "attempt": attempt,
                "seconds": round(time.time() - t0, 2),
                "finish_reason": getattr(choice, "finish_reason", None),
                "max_tokens_used": cur_max_tokens,
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "reasoning_chars": len(reasoning) if reasoning else 0,
                "image": str(image_png_path) if image_png_path else None,
            })
            if verbose:
                print(f"  [llm] {purpose}: got reply in {time.time() - t0:.1f}s "
                     f"(finish={getattr(choice, 'finish_reason', None)}, "
                     f"{getattr(usage, 'completion_tokens', '?')} completion tokens, "
                     f"{len(reasoning) if reasoning else 0} reasoning chars)", flush=True)
            # Reasoning models (GLM/Qwen-thinking/...) spend completion
            # tokens on reasoning_content before writing the real answer, so
            # a truncated response ("length") with EMPTY content means the
            # budget ran out during reasoning, not that the model refused.
            # A truncated response with NON-empty content is just as
            # unusable when json_mode is on -- a JSON object cut off
            # mid-object is not valid JSON, so parse_json_response() below
            # would raise anyway and burn a retry at the SAME max_tokens,
            # guaranteeing the identical truncation again. Widen the budget
            # for either case rather than only the empty-content one; only
            # fall through to the parse attempt once we're already at the
            # cap (nothing more to gain from retrying).
            finish_reason = getattr(choice, "finish_reason", None)
            if finish_reason == "length" and cur_max_tokens < cfg.max_tokens_cap:
                cur_max_tokens = min(cur_max_tokens * 2, cfg.max_tokens_cap)
                reason = "empty content" if not text.strip() else f"{len(text)} char(s), likely truncated JSON"
                last_err = RuntimeError(
                    f"{reason}, finish_reason=length at max_tokens={cur_max_tokens // 2} "
                    f"(reasoning used {len(reasoning) if reasoning else 0} chars) — retrying with {cur_max_tokens}"
                )
                continue
            if json_mode:
                parse_json_response(text)  # validate; raise -> retry
            return text
        except Exception as e:  # noqa: BLE001 — retry any provider/parse error
            last_err = e
            CALL_LOG.append({"purpose": purpose, "model": model, "attempt": attempt, "error": repr(e)[:300]})
            if verbose:
                print(f"  [llm] {purpose}: attempt {attempt} failed after {time.time() - t0:.1f}s: {e!r}", flush=True)
            time.sleep(min(2 ** attempt, 10))
    raise RuntimeError(f"LLM call '{purpose}' failed after {cfg.max_retries} attempts "
                       f"(max_tokens up to {cur_max_tokens}): {last_err!r}")


def chat_json(system: str, user: str, *, purpose: str, cfg: Optional[LLMConfig] = None,
              image_png_path: Optional[Path] = None):
    """chat() + parse_json_response()."""
    return parse_json_response(chat(system, user, purpose=purpose, cfg=cfg,
                                    image_png_path=image_png_path, json_mode=True))

"""Tests for src/llm_client.py's retry/token-widening logic in chat() --
a fake OpenAI client stands in so no network or key is needed.

Regression coverage for a bug found on a real gold-eval run: a reasoning
model (js2/gpt-oss-120b) returned a NON-empty but truncated response
(finish_reason="length", 8000/8000 completion tokens spent, content cut
off mid-JSON). The old code only widened max_tokens and retried when the
truncated content was EMPTY; a non-empty truncation instead fell through
to parse_json_response(), which raised on the incomplete JSON, and the
retry it triggered reused the SAME max_tokens -- guaranteeing the
identical truncation on every subsequent attempt until max_retries was
exhausted and the whole call failed.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import llm_client  # noqa: E402


def _fake_response(content: str, finish_reason: str, completion_tokens: int = 100):
    message = SimpleNamespace(content=content, reasoning_content=None)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=completion_tokens)
    return SimpleNamespace(choices=[choice], usage=usage)


class _FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []  # each entry: kwargs passed to create()

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=_FakeCompletions(responses))


def test_truncated_non_empty_response_widens_max_tokens_and_retries(monkeypatch):
    # First attempt: truncated mid-JSON, NON-empty content -- must not be
    # treated as "parse failure, retry at same budget" (the old bug).
    truncated = _fake_response('{"units": [{"id": 1, "note": "cut off here', "length", completion_tokens=8000)
    complete = _fake_response('{"units": []}', "stop", completion_tokens=50)
    fake_client = _FakeClient([truncated, complete])
    monkeypatch.setattr(llm_client, "_client", lambda cfg: fake_client)

    cfg = llm_client.LLMConfig(api_key="fake", max_tokens=8000, max_tokens_cap=24000, max_retries=4)
    text = llm_client.chat("system", "user", purpose="test", cfg=cfg, verbose=False)

    assert text == '{"units": []}'
    assert len(fake_client.chat.completions.calls) == 2
    assert fake_client.chat.completions.calls[0]["max_tokens"] == 8000
    assert fake_client.chat.completions.calls[1]["max_tokens"] == 16000  # doubled, not resent at 8000


def test_truncated_empty_response_still_widens_max_tokens(monkeypatch):
    # The original (already-working) case: empty content + finish=length.
    empty_truncated = _fake_response("", "length", completion_tokens=8000)
    complete = _fake_response('{"ok": true}', "stop", completion_tokens=20)
    fake_client = _FakeClient([empty_truncated, complete])
    monkeypatch.setattr(llm_client, "_client", lambda cfg: fake_client)

    cfg = llm_client.LLMConfig(api_key="fake", max_tokens=8000, max_tokens_cap=24000, max_retries=4)
    text = llm_client.chat("system", "user", purpose="test", cfg=cfg, verbose=False)

    assert text == '{"ok": true}'
    assert fake_client.chat.completions.calls[1]["max_tokens"] == 16000


def test_widening_stops_at_cap_and_eventually_raises(monkeypatch):
    # Every attempt truncates, even after hitting the cap -- should stop
    # doubling past max_tokens_cap and eventually raise once retries run out,
    # rather than retrying forever.
    always_truncated = [_fake_response('{"unclosed":', "length", completion_tokens=8000) for _ in range(4)]
    fake_client = _FakeClient(always_truncated)
    monkeypatch.setattr(llm_client, "_client", lambda cfg: fake_client)

    cfg = llm_client.LLMConfig(api_key="fake", max_tokens=8000, max_tokens_cap=16000, max_retries=4)
    try:
        llm_client.chat("system", "user", purpose="test", cfg=cfg, verbose=False)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

    used = [c["max_tokens"] for c in fake_client.chat.completions.calls]
    assert used == [8000, 16000, 16000, 16000]  # doubles once, then caps -- never exceeds max_tokens_cap

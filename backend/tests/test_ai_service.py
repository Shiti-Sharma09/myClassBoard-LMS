import pytest
from pydantic import BaseModel

from app.ai import AIError, AIService, ChatResult
from app.ai import prompts as prompts_module
from app.ai.prompts import render_prompt
from app.ai.service import extract_json
from app.config import Settings


class Ping(BaseModel):
    status: str
    echo: str


class FakeProvider:
    """Replays queued replies (str) or raises queued AIError instances. Records the calls."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return ChatResult(text=reply)


def make_service(replies, **settings_kw):
    delays: list[float] = []
    provider = FakeProvider(replies)
    service = AIService(provider, Settings(**settings_kw), sleep=delays.append)
    return service, provider, delays


GOOD = '{"status": "ok", "echo": "hello"}'


def test_returns_validated_model():
    service, provider, _ = make_service([GOOD])
    result = service.run_json("ping", {"word": "hello"}, Ping)
    assert result == Ping(status="ok", echo="hello")
    assert provider.calls[0]["json_mode"] is True


def test_schema_and_prompt_reach_the_model():
    service, provider, _ = make_service([GOOD])
    service.run_json("ping", {"word": "banana"}, Ping)
    system, user = provider.calls[0]["messages"]
    assert "JSON Schema" in system["content"] and '"echo"' in system["content"]
    assert "banana" in user["content"]


def test_tolerates_code_fences_and_surrounding_prose():
    service, _, _ = make_service(["Sure!\n```json\n" + GOOD + "\n```"])
    assert service.run_json("ping", {"word": "x"}, Ping).status == "ok"


def test_invalid_output_is_retried_with_the_error_fed_back():
    service, provider, _ = make_service(['{"status": "ok"}', GOOD])  # first reply misses "echo"
    assert service.run_json("ping", {"word": "x"}, Ping).echo == "hello"
    retry_messages = provider.calls[1]["messages"]
    assert retry_messages[-2]["role"] == "assistant"
    assert "not valid" in retry_messages[-1]["content"]


def test_gives_up_after_max_retries_with_a_friendly_error():
    service, provider, _ = make_service(["nope"] * 3, ai_max_retries=2)
    with pytest.raises(AIError) as exc:
        service.run_json("ping", {"word": "x"}, Ping)
    assert "try again" in exc.value.message
    assert len(provider.calls) == 3


def test_transient_errors_back_off_and_recover():
    busy = AIError("busy", retryable=True)
    service, provider, delays = make_service([busy, busy, GOOD])
    assert service.run_json("ping", {"word": "x"}, Ping).status == "ok"
    assert delays == [1, 2]  # exponential backoff
    assert len(provider.calls) == 3


def test_retry_after_header_is_respected():
    service, _, delays = make_service([AIError("busy", retryable=True, retry_after=7), GOOD])
    service.run_json("ping", {"word": "x"}, Ping)
    assert delays == [7]


def test_permanent_errors_are_not_retried():
    service, provider, _ = make_service([AIError("bad key")])
    with pytest.raises(AIError):
        service.run_json("ping", {"word": "x"}, Ping)
    assert len(provider.calls) == 1


def test_gives_up_when_transient_errors_never_clear():
    service, provider, _ = make_service([AIError("busy", retryable=True)] * 4, ai_max_transport_retries=3)
    with pytest.raises(AIError):
        service.run_json("ping", {"word": "x"}, Ping)
    assert len(provider.calls) == 4


def test_images_are_sent_as_data_urls():
    service, provider, _ = make_service([GOOD])
    service.run_json("ping", {"word": "x"}, Ping, model="vision", images=[(b"\x89PNG", "image/png")])
    content = provider.calls[0]["messages"][1]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert provider.calls[0]["model"] == Settings().vision_model


def test_model_kind_maps_to_configured_model_names():
    service, provider, _ = make_service([GOOD, GOOD], llm_model_main="big", llm_model_fast="small")
    service.run_json("ping", {"word": "x"}, Ping, model="main")
    service.run_json("ping", {"word": "x"}, Ping, model="fast")
    assert [c["model"] for c in provider.calls] == ["big", "small"]


def test_extract_json_rejects_garbage():
    with pytest.raises(ValueError):
        extract_json("no json here")


# --- prompt templates ---


def test_missing_prompt_variable_fails_loudly():
    with pytest.raises(Exception):
        render_prompt("ping", {})


def test_unknown_prompt_raises():
    with pytest.raises(FileNotFoundError):
        render_prompt("does_not_exist")


def test_latest_version_is_used_by_default_and_system_split_works(tmp_path, monkeypatch):
    (tmp_path / "demo.v1.md").write_text("old {{ x }}")
    (tmp_path / "demo.v2.md").write_text("You are {{ x }}.\n=== USER ===\nHello {{ x }}")
    monkeypatch.setattr(prompts_module, "PROMPT_DIR", tmp_path)
    latest = render_prompt("demo", {"x": "Bob"})
    assert (latest.version, latest.system, latest.user) == (2, "You are Bob.", "Hello Bob")
    pinned = render_prompt("demo", {"x": "Bob"}, version=1)
    assert (pinned.system, pinned.user) == (None, "old Bob")

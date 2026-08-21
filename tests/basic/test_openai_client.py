import json
import os
from unittest.mock import MagicMock, patch

import pytest

from aider import openai_client


class FakeResponse:
    def __init__(self, status_code, data=None, text=""):
        self.status_code = status_code
        self._data = data
        self.text = text

    def json(self):
        return self._data


def test_completion_non_stream(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    data = {
        "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 1},
    }
    with patch(
        "aider.openai_client.httpx.post",
        return_value=FakeResponse(200, data),
    ) as mock_post:
        res = openai_client.completion(
            model="gpt-4o", messages=[{"role": "user", "content": "x"}], stream=False
        )

    kwargs = mock_post.call_args.kwargs
    assert mock_post.call_args.args[0] == "https://api.openai.com/v1/chat/completions"
    assert kwargs["json"]["model"] == "gpt-4o"
    assert kwargs["json"]["stream"] is False
    assert kwargs["headers"]["Authorization"] == f"Bearer {os.environ['OPENAI_API_KEY']}"

    assert res.choices[0].message.content == "hi"
    assert res.choices[0].finish_reason == "stop"
    assert res.usage.prompt_tokens == 5
    assert res.usage.completion_tokens == 1


def test_completion_honors_api_key_and_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    data = {"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]}
    with patch(
        "aider.openai_client.httpx.post",
        return_value=FakeResponse(200, data),
    ) as mock_post:
        openai_client.completion(
            model="m",
            messages=[{"role": "user", "content": "x"}],
            api_key="sk-kwarg",
            base_url="http://per-model:8000/v1",
        )

    kwargs = mock_post.call_args.kwargs
    assert mock_post.call_args.args[0] == "http://per-model:8000/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer sk-kwarg"


def test_completion_api_base_still_works():
    data = {"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]}
    with patch(
        "aider.openai_client.httpx.post",
        return_value=FakeResponse(200, data),
    ) as mock_post:
        openai_client.completion(
            model="m",
            messages=[{"role": "user", "content": "x"}],
            api_key="sk-kwarg",
            api_base="http://alt:9000/v1",
        )

    assert mock_post.call_args.args[0] == "http://alt:9000/v1/chat/completions"


def test_completion_stream(monkeypatch):
    chunks = [
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
        {"choices": [{"delta": {}}, {"finish_reason": "stop"}]},
    ]
    lines = ["data: " + json.dumps(c) for c in chunks] + ["data: [DONE]"]

    class FakeStreamResponse:
        status_code = 200

        def __init__(self, lines):
            self._lines = lines

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def iter_lines(self):
            return iter(self._lines)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url, **kwargs):
            return FakeStreamResponse(lines)

    monkeypatch.setattr(openai_client.httpx, "Client", FakeClient)
    monkeypatch.setenv("OPENAI_API_BASE", "http://local")

    gen = openai_client.completion(
        model="gpt-4o", messages=[{"role": "user", "content": "x"}], stream=True
    )
    out = [
        chunk.choices[0].delta.content
        for chunk in gen
        if chunk.choices and chunk.choices[0].delta.content
    ]
    assert out == ["Hel", "lo"]


def test_completion_reasoning_stream(monkeypatch):
    chunks = [
        {"choices": [{"delta": {"reasoning_content": "think"}}]},
        {"choices": [{"delta": {"content": "ans"}}]},
    ]
    lines = ["data: " + json.dumps(c) for c in chunks] + ["data: [DONE]"]

    class FakeStreamResponse:
        status_code = 200

        def __init__(self, lines):
            self._lines = lines

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def iter_lines(self):
            return iter(self._lines)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url, **kwargs):
            return FakeStreamResponse(lines)

    monkeypatch.setattr(openai_client.httpx, "Client", FakeClient)
    gen = openai_client.completion(
        model="gpt-4o", messages=[{"role": "user", "content": "x"}], stream=True
    )
    first = next(gen)
    assert first.choices[0].delta.reasoning_content == "think"
    assert not hasattr(first.choices[0].delta, "reasoning")


def test_completion_temperature_max_tokens():
    with patch(
        "aider.openai_client.httpx.post", return_value=FakeResponse(200, {"choices": []})
    ) as mock_post:
        openai_client.completion(
            model="gpt-4o",
            messages=[],
            stream=False,
            temperature=0.7,
            max_tokens=100,
            num_ctx=8192,
        )
    payload = mock_post.call_args.kwargs["json"]
    assert payload["temperature"] == 0.7
    assert payload["max_tokens"] == 100
    assert "num_ctx" not in payload


@pytest.mark.parametrize(
    "status,cls",
    [
        (401, openai_client.AuthenticationError),
        (403, openai_client.PermissionDeniedError),
        (404, openai_client.NotFoundError),
        (429, openai_client.RateLimitError),
        (422, openai_client.UnprocessableEntityError),
        (500, openai_client.InternalServerError),
        (503, openai_client.ServiceUnavailableError),
        (400, openai_client.BadRequestError),
    ],
)
def test_completion_error_mapping(status, cls):
    with patch(
        "aider.openai_client.httpx.post",
        return_value=FakeResponse(status, {"error": {"message": "boom"}}),
    ):
        with pytest.raises(cls):
            openai_client.completion(model="gpt-4o", messages=[], stream=False)


def test_completion_context_window_error():
    with patch(
        "aider.openai_client.httpx.post",
        return_value=FakeResponse(400, {"error": {"message": "maximum context length is 128000"}}),
    ):
        with pytest.raises(openai_client.ContextWindowExceededError):
            openai_client.completion(model="gpt-4o", messages=[], stream=False)


def test_transcription():
    with patch(
        "aider.openai_client.httpx.post",
        return_value=FakeResponse(200, {"text": "hello there"}),
    ) as mock_post:
        res = openai_client.transcription(model="whisper-1", file=MagicMock(), language="en")
    assert res.text == "hello there"
    url = mock_post.call_args.args[0]
    assert url.endswith("/audio/transcriptions")
    assert mock_post.call_args.kwargs["data"]["model"] == "whisper-1"


def test_encode_fallback(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "tiktoken", None)
    assert openai_client.encode("gpt-4o", "hello world") == [0] * 2
    assert len(openai_client.encode("unknown-model-xyz", "a" * 40)) == 10


def test_model_list(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    data = {"data": [{"id": "model-b"}, {"id": "model-a"}, {"nope": 1}]}
    with patch("aider.openai_client.httpx.get", return_value=FakeResponse(200, data)):
        assert openai_client.model_list() == ["model-a", "model-b"]


def test_model_list_error_returns_empty(monkeypatch):
    with patch(
        "aider.openai_client.httpx.get", return_value=FakeResponse(500, {"error": {}})
    ):
        assert openai_client.model_list() == []

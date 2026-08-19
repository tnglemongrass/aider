"""Minimal OpenAI-compatible client used when litellm is not installed.

Implements the subset of the litellm API surface that aider uses, speaking
plain OpenAI /v1/chat/completions (and /v1/audio/transcriptions) over httpx.
The response objects mimic the attribute access litellm responses expose.
"""

import json
import os

import httpx

VERIFY_SSL = True

DEFAULT_TIMEOUT = 600


class OpenAIError(Exception):
    pass


class APIConnectionError(OpenAIError):
    pass


class Timeout(OpenAIError):
    pass


class APIError(OpenAIError):
    pass


class AuthenticationError(APIError):
    pass


class PermissionDeniedError(APIError):
    pass


class NotFoundError(APIError):
    pass


class RateLimitError(APIError):
    pass


class BadRequestError(APIError):
    pass


class InvalidRequestError(BadRequestError):
    pass


class UnprocessableEntityError(APIError):
    pass


class InternalServerError(APIError):
    pass


class ServiceUnavailableError(APIError):
    pass


class ContextWindowExceededError(BadRequestError):
    pass


def set_verify_ssl(verify):
    global VERIFY_SSL
    VERIFY_SSL = verify


def _base_url():
    api_base = os.environ.get("OPENAI_API_BASE")
    if api_base:
        return api_base.rstrip("/")
    return "https://api.openai.com/v1"


def _headers(extra_headers=None):
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if extra_headers:
        headers.update(extra_headers)
    return headers


def _timeout(timeout):
    return timeout if timeout is not None else DEFAULT_TIMEOUT


def _error_from_response(resp):
    try:
        data = resp.json()
    except Exception:
        data = {}
    err = data.get("error") or {}
    if isinstance(err, dict):
        message = err.get("message") or resp.text
    else:
        message = str(err)
    status = resp.status_code
    msg = f"HTTP {status}: {message}"
    if status == 401:
        return AuthenticationError(msg)
    if status == 403:
        return PermissionDeniedError(msg)
    if status == 404:
        return NotFoundError(msg)
    if status == 429:
        return RateLimitError(msg)
    if status == 422:
        return UnprocessableEntityError(msg)
    if status == 500:
        return InternalServerError(msg)
    if status == 503:
        return ServiceUnavailableError(msg)
    if status == 400:
        if "maximum context" in str(message).lower() or "context_length" in str(message).lower():
            return ContextWindowExceededError(msg)
        return BadRequestError(msg)
    return APIError(msg)


class _Message:
    def __init__(self, data):
        self.content = data.get("content")
        self.tool_calls = data.get("tool_calls")
        if "reasoning_content" in data:
            self.reasoning_content = data["reasoning_content"]
        if "reasoning" in data:
            self.reasoning = data["reasoning"]


class _Choice:
    def __init__(self, data):
        self.message = _Message(data.get("message") or {})
        self.finish_reason = data.get("finish_reason")


class _Usage:
    def __init__(self, data):
        self.prompt_tokens = data.get("prompt_tokens", 0)
        self.completion_tokens = data.get("completion_tokens", 0)
        self.prompt_cache_hit_tokens = data.get("prompt_cache_hit_tokens")
        self.cache_read_input_tokens = data.get("cache_read_input_tokens")
        self.cache_creation_input_tokens = data.get("cache_creation_input_tokens")


class OpenAIResponse:
    def __init__(self, data):
        self.choices = [_Choice(c) for c in data.get("choices") or []]
        self.usage = _Usage(data.get("usage") or {})

    def __repr__(self):
        return f"OpenAIResponse(choices={self.choices!r})"


class _Delta:
    def __init__(self, data):
        self.content = data.get("content")
        self.function_call = data.get("function_call")
        if "reasoning_content" in data:
            self.reasoning_content = data["reasoning_content"]
        if "reasoning" in data:
            self.reasoning = data["reasoning"]


class _StreamChoice:
    def __init__(self, data):
        self.finish_reason = data.get("finish_reason")
        self.delta = _Delta(data.get("delta") or {})


class StreamChunk:
    def __init__(self, data):
        self.choices = [_StreamChoice(c) for c in data.get("choices") or []]


class _Transcription:
    def __init__(self, data):
        if isinstance(data, dict):
            self.text = data.get("text", "")
        else:
            self.text = str(data)


def completion(
    model,
    messages,
    stream=False,
    temperature=None,
    max_tokens=None,
    timeout=None,
    extra_headers=None,
    api_base=None,
    extra_body=None,
    **ignored,
):
    payload = dict(model=model, messages=messages, stream=bool(stream))
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if extra_body:
        payload.update(extra_body)
    url = (api_base or _base_url()).rstrip("/") + "/chat/completions"
    headers = _headers(extra_headers)
    timeout = _timeout(timeout)

    if stream:
        def gen():
            try:
                with httpx.Client(verify=VERIFY_SSL, timeout=timeout) as client:
                    with client.stream("POST", url, json=payload, headers=headers) as resp:
                        if resp.status_code != 200:
                            raise _error_from_response(resp)
                        for line in resp.iter_lines():
                            if not line:
                                continue
                            if line.startswith("data:"):
                                line = line[5:].strip()
                            if line == "[DONE]":
                                return
                            try:
                                yield StreamChunk(json.loads(line))
                            except json.JSONDecodeError:
                                continue
            except httpx.TimeoutException as err:
                raise Timeout(str(err)) from err
            except httpx.ConnectError as err:
                raise APIConnectionError(str(err)) from err

        return gen()

    try:
        resp = httpx.post(
            url, json=payload, headers=headers, timeout=timeout, verify=VERIFY_SSL
        )
    except httpx.TimeoutException as err:
        raise Timeout(str(err)) from err
    except httpx.ConnectError as err:
        raise APIConnectionError(str(err)) from err

    if resp.status_code != 200:
        raise _error_from_response(resp)
    return OpenAIResponse(resp.json())


def encode(model, text):
    try:
        import tiktoken

        return tiktoken.encoding_for_model(model).encode(text)
    except Exception:
        return [0] * (len(text) // 4)


def token_counter(model, messages):
    total = 0
    for message in messages or []:
        content = message.get("content", "")
        if isinstance(content, str):
            total += len(encode(model, content))
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += len(encode(model, part.get("text", "")))
        total += 1
    return total


def transcription(model, file, prompt=None, language=None):
    url = _base_url().rstrip("/") + "/audio/transcriptions"
    data = {"model": model}
    if prompt:
        data["prompt"] = prompt
    if language:
        data["language"] = language
    headers = {}
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        resp = httpx.post(
            url,
            data=data,
            files={"file": file},
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
            verify=VERIFY_SSL,
        )
    except httpx.TimeoutException as err:
        raise Timeout(str(err)) from err
    except httpx.ConnectError as err:
        raise APIConnectionError(str(err)) from err
    if resp.status_code != 200:
        raise _error_from_response(resp)
    return _Transcription(resp.json())

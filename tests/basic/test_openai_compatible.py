from pathlib import Path

import requests

from aider import models
from aider.models import get_openai_compatible_models
from aider.openai_compatible import OpenAICompatibleModelManager


class DummyResponse:
    """Minimal stand-in for requests.Response used in tests."""

    def __init__(self, json_data, status_code=200):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


def test_openai_compatible_get_models_from_cache(monkeypatch, tmp_path):
    """
    OpenAICompatibleModelManager should return correct model list from the
    OpenAI-compatible endpoint.
    """
    payload = {
        "data": [
            {"id": "gpt-3.5-turbo", "object": "model"},
            {"id": "gpt-4", "object": "model"},
            {"id": "custom-model", "object": "model"},
        ]
    }

    # Fake out the network call and the HOME directory used for the cache file
    monkeypatch.setattr("requests.get", lambda *a, **k: DummyResponse(payload))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    manager = OpenAICompatibleModelManager()
    models = manager.get_models("https://api.example.com/v1")

    assert len(models) == 3
    assert "gpt-3.5-turbo" in models
    assert "gpt-4" in models
    assert "custom-model" in models


def test_openai_compatible_get_models_without_v1(monkeypatch, tmp_path):
    """
    OpenAICompatibleModelManager should handle API base URLs without /v1 suffix.
    """
    payload = {
        "data": [
            {"id": "model-1", "object": "model"},
            {"id": "model-2", "object": "model"},
        ]
    }

    # Track what URL was requested
    requested_url = None

    def mock_get(url, *args, **kwargs):
        nonlocal requested_url
        requested_url = url
        return DummyResponse(payload)

    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    manager = OpenAICompatibleModelManager()
    models = manager.get_models("https://api.example.com")

    assert len(models) == 2
    assert requested_url == "https://api.example.com/v1/models"


def test_openai_compatible_get_models_with_v1(monkeypatch, tmp_path):
    """
    OpenAICompatibleModelManager should handle API base URLs with /v1 suffix.
    """
    payload = {
        "data": [
            {"id": "model-1", "object": "model"},
        ]
    }

    # Track what URL was requested
    requested_url = None

    def mock_get(url, *args, **kwargs):
        nonlocal requested_url
        requested_url = url
        return DummyResponse(payload)

    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    manager = OpenAICompatibleModelManager()
    models = manager.get_models("https://api.example.com/v1")

    assert len(models) == 1
    assert requested_url == "https://api.example.com/v1/models"


def test_openai_compatible_handles_api_failure(monkeypatch, tmp_path):
    """
    OpenAICompatibleModelManager should gracefully handle API failures.
    """

    def mock_get(*args, **kwargs):
        raise requests.RequestException("Network error")

    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    manager = OpenAICompatibleModelManager()
    models = manager.get_models("https://api.example.com/v1")

    assert models == []


def test_openai_compatible_caching(monkeypatch, tmp_path):
    """
    OpenAICompatibleModelManager should cache results and reuse them.
    """
    payload = {
        "data": [
            {"id": "cached-model", "object": "model"},
        ]
    }

    call_count = 0

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return DummyResponse(payload)

    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    manager = OpenAICompatibleModelManager()

    # First call should fetch from API
    models1 = manager.get_models("https://api.example.com/v1")
    assert call_count == 1

    # Second call should use cache
    models2 = manager.get_models("https://api.example.com/v1")
    assert call_count == 1  # Should not have made another API call

    assert models1 == models2


def test_get_openai_compatible_models_with_env(monkeypatch, tmp_path):
    """
    get_openai_compatible_models should fetch models when OPENAI_API_BASE is set.
    """
    payload = {
        "data": [
            {"id": "env-model", "object": "model"},
        ]
    }

    monkeypatch.setattr("requests.get", lambda *a, **k: DummyResponse(payload))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.example.com/v1")

    # Need to reinitialize the model_info_manager to pick up the new environment
    models.model_info_manager.openai_compatible_manager = OpenAICompatibleModelManager()

    fetched_models = get_openai_compatible_models()

    assert len(fetched_models) == 1
    assert "env-model" in fetched_models


def test_get_openai_compatible_models_without_env(monkeypatch):
    """
    get_openai_compatible_models should return empty list when OPENAI_API_BASE is not set.
    """
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)

    fetched_models = get_openai_compatible_models()

    assert fetched_models == []


def test_openai_compatible_includes_auth_header(monkeypatch, tmp_path):
    """
    OpenAICompatibleModelManager should include Authorization header when API key is set.
    """
    payload = {
        "data": [
            {"id": "secure-model", "object": "model"},
        ]
    }

    headers_used = None

    def mock_get(url, headers=None, *args, **kwargs):
        nonlocal headers_used
        headers_used = headers
        return DummyResponse(payload)

    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key-123")

    manager = OpenAICompatibleModelManager()
    models = manager.get_models("https://api.example.com/v1")

    assert headers_used is not None
    assert "Authorization" in headers_used
    assert headers_used["Authorization"] == "Bearer test-api-key-123"
    assert len(models) == 1

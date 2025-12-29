"""
OpenAI-compatible endpoint model fetcher.

This module fetches model list from custom OpenAI-compatible endpoints
when the user specifies a custom API base URL via OPENAI_API_BASE or --openai-api-base.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


class OpenAICompatibleModelManager:
    """Manager for fetching and caching models from OpenAI-compatible endpoints."""

    CACHE_TTL = 60 * 60 * 24  # 24 hours

    def __init__(self) -> None:
        self.cache_dir = Path.home() / ".aider" / "caches"
        self.cache_file_prefix = "openai_compatible_models"
        self.verify_ssl: bool = True
        self._models_cache: Dict[str, Tuple[List[str], float]] = {}

    def set_verify_ssl(self, verify_ssl: bool) -> None:
        """Enable/disable SSL verification for API requests."""
        self.verify_ssl = verify_ssl

    def get_models(self, api_base: str) -> List[str]:
        """
        Fetch model list from the given OpenAI-compatible API base URL.

        Args:
            api_base: The base URL of the OpenAI-compatible API

        Returns:
            List of model names available at the endpoint
        """
        # Check in-memory cache first
        if api_base in self._models_cache:
            models, timestamp = self._models_cache[api_base]
            if time.time() - timestamp < self.CACHE_TTL:
                return models

        # Try to load from disk cache
        cached_models = self._load_cache(api_base)
        if cached_models:
            self._models_cache[api_base] = (cached_models, time.time())
            return cached_models

        # Fetch from API
        models = self._fetch_models(api_base)
        if models:
            self._save_cache(api_base, models)
            self._models_cache[api_base] = (models, time.time())

        return models

    def _fetch_models(self, api_base: str) -> List[str]:
        """Fetch models from the /v1/models endpoint."""
        # Ensure the API base URL ends with /v1 or construct the full URL
        api_base = api_base.rstrip('/')
        if not api_base.endswith('/v1'):
            models_url = f"{api_base}/v1/models"
        else:
            models_url = f"{api_base}/models"

        try:
            # Get API key if available
            api_key = os.environ.get("OPENAI_API_KEY")
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            response = requests.get(
                models_url,
                headers=headers,
                timeout=10,
                verify=self.verify_ssl
            )

            if response.status_code == 200:
                data = response.json()
                # OpenAI-compatible endpoints return models in a "data" array
                if "data" in data and isinstance(data["data"], list):
                    models = [model.get("id") for model in data["data"] if model.get("id")]
                    return models
        except (requests.RequestException, json.JSONDecodeError, ValueError):
            # Silently fail - user might not have connectivity or endpoint might not be
            # valid
            pass

        return []

    def _get_cache_file(self, api_base: str) -> Path:
        """Get the cache file path for a given API base URL."""
        # Create a safe filename from the URL
        url_hash = hashlib.sha256(api_base.encode()).hexdigest()[:16]
        return self.cache_dir / f"{self.cache_file_prefix}_{url_hash}.json"

    def _load_cache(self, api_base: str) -> Optional[List[str]]:
        """Load cached models from disk."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self._get_cache_file(api_base)

            if cache_file.exists():
                cache_age = time.time() - cache_file.stat().st_mtime
                if cache_age < self.CACHE_TTL:
                    try:
                        data = json.loads(cache_file.read_text())
                        if "models" in data and isinstance(data["models"], list):
                            return data["models"]
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass

        return None

    def _save_cache(self, api_base: str, models: List[str]) -> None:
        """Save models to disk cache."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self._get_cache_file(api_base)
            data = {"models": models, "api_base": api_base}
            cache_file.write_text(json.dumps(data, indent=2))
        except OSError:
            # Non-fatal if we can't write the cache
            pass

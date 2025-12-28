"""
SimpleLLM - A minimal OpenAI-compatible client for aider.

This module provides a simple, lightweight alternative to litellm for basic
OpenAI-compatible API interactions. It's designed to work with any OpenAI-compatible
server and be configured entirely through environment variables.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import requests


class SimpleLLMError(Exception):
    """Base exception for SimpleLLM errors"""
    pass


class ModelInfo:
    """Cache for model metadata from the API server"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".aider" / "caches" / "simple_llm"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Dict] = {}
    
    def get_cache_file(self, base_url: str) -> Path:
        """Get cache file path for a given base URL"""
        # Create a safe filename from the URL
        safe_name = base_url.replace("://", "_").replace("/", "_").replace(":", "_")
        return self.cache_dir / f"models_{safe_name}.json"
    
    def fetch_models(self, base_url: str, api_key: Optional[str] = None, 
                     verify_ssl: bool = True) -> List[Dict]:
        """Fetch model list from the API server"""
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Try both /models and /v1/models endpoints
        for endpoint in ["/v1/models", "/models"]:
            try:
                url = base_url.rstrip("/") + endpoint
                response = requests.get(url, headers=headers, timeout=10, verify=verify_ssl)
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data:
                        return data["data"]
                    elif isinstance(data, list):
                        return data
            except Exception:
                continue
        
        return []
    
    def get_model_info(self, model_name: str, base_url: str, 
                       api_key: Optional[str] = None, 
                       verify_ssl: bool = True) -> Dict[str, Any]:
        """Get model information, using cache when available"""
        cache_key = f"{base_url}:{model_name}"
        
        # Check memory cache first
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Check disk cache
        cache_file = self.get_cache_file(base_url)
        if cache_file.exists():
            try:
                cache_age = time.time() - cache_file.stat().st_mtime
                # Cache valid for 24 hours
                if cache_age < 86400:
                    with open(cache_file, "r") as f:
                        cached_data = json.load(f)
                        if model_name in cached_data:
                            self._cache[cache_key] = cached_data[model_name]
                            return cached_data[model_name]
            except (json.JSONDecodeError, OSError):
                pass
        
        # Fetch fresh data
        models = self.fetch_models(base_url, api_key, verify_ssl)
        model_cache = {}
        
        for model in models:
            model_id = model.get("id", "")
            info = {
                "max_tokens": model.get("max_tokens") or model.get("context_length") or 4096,
                "max_input_tokens": model.get("max_input_tokens") or model.get("context_length") or 4096,
                "max_output_tokens": model.get("max_output_tokens") or 4096,
            }
            model_cache[model_id] = info
            if model_id == model_name:
                self._cache[cache_key] = info
        
        # Save to disk cache
        try:
            with open(cache_file, "w") as f:
                json.dump(model_cache, f, indent=2)
        except OSError:
            pass
        
        # Return info for requested model or empty dict if not found
        return self._cache.get(cache_key, {})


# Global model info cache
_model_info_cache = ModelInfo()


def completion(
    model: str,
    messages: List[Dict[str, str]],
    stream: bool = False,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
    **kwargs
) -> Any:
    """
    Send a chat completion request to an OpenAI-compatible API.
    
    This function mimics the litellm.completion interface but uses a simple
    requests-based implementation for OpenAI-compatible servers.
    
    Args:
        model: Model name to use
        messages: List of message dicts with 'role' and 'content' keys
        stream: Whether to stream the response
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens to generate
        timeout: Request timeout in seconds
        **kwargs: Additional parameters (tools, tool_choice, extra_params, etc.)
    
    Returns:
        Response object compatible with litellm format
    """
    # Get configuration from environment
    api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    verify_ssl = os.environ.get("AIDER_VERIFY_SSL", "true").lower() != "false"
    
    # Use max_tokens from environment if not specified
    if max_tokens is None:
        env_max_tokens = os.environ.get("MAX_TOKENS")
        if env_max_tokens:
            try:
                max_tokens = int(env_max_tokens)
            except ValueError:
                pass
    
    # Build request
    url = api_base.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    # Handle extra_headers from kwargs
    if "extra_headers" in kwargs:
        headers.update(kwargs["extra_headers"])
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    
    if temperature is not None:
        payload["temperature"] = temperature
    
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    
    # Handle tools (function calling)
    if "tools" in kwargs:
        payload["tools"] = kwargs["tools"]
    if "tool_choice" in kwargs:
        payload["tool_choice"] = kwargs["tool_choice"]
    
    # Handle extra_params
    if "extra_params" in kwargs:
        extra = kwargs["extra_params"]
        # Merge extra_body if present
        if "extra_body" in extra:
            for key, value in extra["extra_body"].items():
                payload[key] = value
            extra = {k: v for k, v in extra.items() if k != "extra_body"}
        payload.update(extra)
    
    # Handle num_ctx for Ollama
    if "num_ctx" in kwargs:
        payload["num_ctx"] = kwargs["num_ctx"]
    
    timeout_val = timeout if timeout is not None else 600
    
    try:
        response = requests.post(
            url, 
            headers=headers, 
            json=payload, 
            stream=stream, 
            timeout=timeout_val,
            verify=verify_ssl
        )
        response.raise_for_status()
        
        if stream:
            return StreamingResponse(response)
        else:
            return CompletionResponse(response.json())
    
    except requests.exceptions.RequestException as e:
        raise SimpleLLMError(f"API request failed: {str(e)}")


class CompletionResponse:
    """Wrapper for non-streaming completion responses"""
    
    def __init__(self, data: Dict):
        self._data = data
        self.choices = [Choice(choice) for choice in data.get("choices", [])]
        self.usage = data.get("usage", {})
        self.model = data.get("model", "")
        self.id = data.get("id", "")
    
    def __getitem__(self, key):
        return self._data[key]
    
    def get(self, key, default=None):
        return self._data.get(key, default)


class Choice:
    """Wrapper for a completion choice"""
    
    def __init__(self, data: Dict):
        self._data = data
        self.message = Message(data.get("message", {}))
        self.finish_reason = data.get("finish_reason")
        self.index = data.get("index", 0)


class Message:
    """Wrapper for a message"""
    
    def __init__(self, data: Dict):
        self._data = data
        self.content = data.get("content", "")
        self.role = data.get("role", "assistant")
        self.tool_calls = data.get("tool_calls")
    
    def get(self, key, default=None):
        return self._data.get(key, default)


class StreamingResponse:
    """Wrapper for streaming completion responses"""
    
    def __init__(self, response: requests.Response):
        self._response = response
    
    def __iter__(self) -> Iterator[Dict]:
        """Iterate over streaming chunks"""
        for line in self._response.iter_lines():
            if not line:
                continue
            
            line = line.decode("utf-8")
            if line.startswith("data: "):
                line = line[6:]  # Remove "data: " prefix
            
            if line.strip() == "[DONE]":
                break
            
            try:
                chunk = json.loads(line)
                yield StreamChunk(chunk)
            except json.JSONDecodeError:
                continue


class StreamChunk:
    """Wrapper for a streaming chunk"""
    
    def __init__(self, data: Dict):
        self._data = data
        self.choices = [StreamChoice(choice) for choice in data.get("choices", [])]
        self.model = data.get("model", "")
        self.id = data.get("id", "")


class StreamChoice:
    """Wrapper for a streaming choice"""
    
    def __init__(self, data: Dict):
        self._data = data
        self.delta = Delta(data.get("delta", {}))
        self.finish_reason = data.get("finish_reason")
        self.index = data.get("index", 0)


class Delta:
    """Wrapper for a delta (streaming message fragment)"""
    
    def __init__(self, data: Dict):
        self._data = data
        self.content = data.get("content", "")
        self.role = data.get("role")
        self.tool_calls = data.get("tool_calls")
    
    def get(self, key, default=None):
        return self._data.get(key, default)


def get_model_info(model: str) -> Dict[str, Any]:
    """
    Get model information from the API server.
    
    Args:
        model: Model name
    
    Returns:
        Dict with model metadata (max_tokens, max_input_tokens, etc.)
    """
    api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    api_key = os.environ.get("OPENAI_API_KEY")
    verify_ssl = os.environ.get("AIDER_VERIFY_SSL", "true").lower() != "false"
    
    return _model_info_cache.get_model_info(model, api_base, api_key, verify_ssl)


def validate_environment(model: str) -> Dict[str, Any]:
    """
    Check if the required environment variables are set.
    
    Args:
        model: Model name (unused, for compatibility)
    
    Returns:
        Dict with keys_in_environment and missing_keys
    """
    missing = []
    
    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    
    if missing:
        return {
            "keys_in_environment": False,
            "missing_keys": missing
        }
    
    return {
        "keys_in_environment": True,
        "missing_keys": []
    }


def encode(model: str, text: str) -> List[int]:
    """
    Tokenize text (simple approximation).
    
    For SimpleLLM, we use a rough approximation: ~4 chars per token.
    This is good enough for most purposes.
    """
    # Rough approximation: 4 characters per token
    return [0] * (len(text) // 4 + 1)


def token_counter(model: str, messages: List[Dict]) -> int:
    """
    Count tokens in messages (simple approximation).
    
    Args:
        model: Model name (unused)
        messages: List of message dicts
    
    Returns:
        Approximate token count
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        # Rough approximation: 4 characters per token + overhead
        total += len(content) // 4 + 4
    return total


def completion_cost(completion_response: Any) -> float:
    """
    Calculate cost of a completion (returns 0 for SimpleLLM).
    
    SimpleLLM doesn't track costs by default.
    """
    return 0.0


# Expose a module-level "model_cost" dict for compatibility
model_cost = {}


# Flag to indicate this is SimpleLLM, not litellm
suppress_debug_info = True
set_verbose = False
drop_params = True

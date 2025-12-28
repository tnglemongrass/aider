"""Tests for SimpleLLM provider"""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from aider import simple_llm


class TestSimpleLLM(unittest.TestCase):
    """Test SimpleLLM functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Set up test environment variables
        os.environ["OPENAI_API_BASE"] = "https://api.test.com/v1"
        os.environ["OPENAI_API_KEY"] = "test-key-123"
    
    def tearDown(self):
        """Clean up test environment"""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_validate_environment_with_key(self):
        """Test environment validation when API key is present"""
        result = simple_llm.validate_environment("test-model")
        self.assertTrue(result["keys_in_environment"])
        self.assertEqual(result["missing_keys"], [])
    
    def test_validate_environment_without_key(self):
        """Test environment validation when API key is missing"""
        del os.environ["OPENAI_API_KEY"]
        result = simple_llm.validate_environment("test-model")
        self.assertFalse(result["keys_in_environment"])
        self.assertIn("OPENAI_API_KEY", result["missing_keys"])
    
    def test_encode_approximation(self):
        """Test token encoding approximation"""
        text = "Hello, world! This is a test."
        tokens = simple_llm.encode("test-model", text)
        # Should be roughly len(text) / 4
        expected = len(text) // 4 + 1
        self.assertEqual(len(tokens), expected)
    
    def test_token_counter(self):
        """Test token counting for messages"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        count = simple_llm.token_counter("test-model", messages)
        # Should return a reasonable approximation
        self.assertGreater(count, 0)
        self.assertLess(count, 100)  # These are short messages
    
    def test_completion_cost(self):
        """Test that completion_cost returns 0"""
        mock_response = MagicMock()
        cost = simple_llm.completion_cost(mock_response)
        self.assertEqual(cost, 0.0)
    
    @patch("aider.simple_llm.requests.post")
    def test_completion_non_streaming(self, mock_post):
        """Test non-streaming completion"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-id",
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Test response"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }
        mock_post.return_value = mock_response
        
        messages = [{"role": "user", "content": "Test message"}]
        response = simple_llm.completion(
            model="test-model",
            messages=messages,
            stream=False
        )
        
        # Verify the response structure
        self.assertEqual(response.model, "test-model")
        self.assertEqual(len(response.choices), 1)
        self.assertEqual(response.choices[0].message.content, "Test response")
        
        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://api.test.com/v1/chat/completions")
        self.assertIn("Authorization", call_args[1]["headers"])
        self.assertEqual(call_args[1]["headers"]["Authorization"], "Bearer test-key-123")
    
    @patch("aider.simple_llm.requests.post")
    def test_completion_with_temperature(self, mock_post):
        """Test completion with temperature parameter"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-id",
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Test"},
                    "finish_reason": "stop"
                }
            ]
        }
        mock_post.return_value = mock_response
        
        simple_llm.completion(
            model="test-model",
            messages=[{"role": "user", "content": "Test"}],
            stream=False,
            temperature=0.7
        )
        
        # Check that temperature was included in the payload
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["temperature"], 0.7)
    
    @patch("aider.simple_llm.requests.post")
    def test_completion_with_max_tokens(self, mock_post):
        """Test completion with max_tokens parameter"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-id",
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Test"},
                    "finish_reason": "stop"
                }
            ]
        }
        mock_post.return_value = mock_response
        
        simple_llm.completion(
            model="test-model",
            messages=[{"role": "user", "content": "Test"}],
            stream=False,
            max_tokens=100
        )
        
        # Check that max_tokens was included in the payload
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["max_tokens"], 100)
    
    @patch("aider.simple_llm.requests.post")
    def test_completion_with_env_max_tokens(self, mock_post):
        """Test completion with MAX_TOKENS from environment"""
        os.environ["MAX_TOKENS"] = "200"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-id",
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Test"},
                    "finish_reason": "stop"
                }
            ]
        }
        mock_post.return_value = mock_response
        
        simple_llm.completion(
            model="test-model",
            messages=[{"role": "user", "content": "Test"}],
            stream=False
        )
        
        # Check that max_tokens from env was used
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["max_tokens"], 200)
    
    @patch("aider.simple_llm.requests.get")
    def test_model_info_fetch(self, mock_get):
        """Test fetching model info from API"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "test-model",
                    "max_tokens": 8192,
                    "context_length": 8192
                }
            ]
        }
        mock_get.return_value = mock_response
        
        cache = simple_llm.ModelInfo()
        info = cache.fetch_models("https://api.test.com/v1", "test-key")
        
        self.assertEqual(len(info), 1)
        self.assertEqual(info[0]["id"], "test-model")
    
    def test_completion_response_wrapper(self):
        """Test CompletionResponse wrapper"""
        data = {
            "id": "test-id",
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Test content"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {"total_tokens": 10}
        }
        
        response = simple_llm.CompletionResponse(data)
        
        self.assertEqual(response.model, "test-model")
        self.assertEqual(response.id, "test-id")
        self.assertEqual(len(response.choices), 1)
        self.assertEqual(response.choices[0].message.content, "Test content")
        self.assertEqual(response.usage["total_tokens"], 10)


if __name__ == "__main__":
    unittest.main()

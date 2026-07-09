"""Comprehensive tests for skills/watch/scripts/opencode_client.py.

Tests OpenCodeClient initialization, validation, message builders, and edge cases.
All network calls are mocked — no real HTTP requests are made.
"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scripts.errors import APIError, ConfigError
from scripts.opencode_client import (
    OpenCodeClient,
    OpenCodeError,
    RateLimitError,
    _DEFAULT_BASE_URL,
    _DEFAULT_MODEL,
    _DEFAULT_TIMEOUT,
    _MAX_TIMEOUT,
    _MIN_KEY_LENGTH,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> OpenCodeClient:
    """Create a client with a test API key."""
    return OpenCodeClient(api_key="test-key-12345678")


@pytest.fixture
def mock_response() -> dict[str, Any]:
    """Standard mock API response."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


# ---------------------------------------------------------------------------
# __init__ validation
# ---------------------------------------------------------------------------

class TestOpenCodeClientInit:
    """Test client initialization and input validation."""

    def test_valid_init(self) -> None:
        client = OpenCodeClient(api_key="test-key-12345678")
        assert client._model == _DEFAULT_MODEL
        assert client._base_url == _DEFAULT_BASE_URL
        assert client._timeout == _DEFAULT_TIMEOUT

    def test_custom_model(self) -> None:
        client = OpenCodeClient(api_key="test-key-12345678", model="my-model")
        assert client._model == "my-model"

    def test_custom_base_url(self) -> None:
        client = OpenCodeClient(api_key="test-key-12345678", base_url="https://custom.api.com/v1")
        assert client._base_url == "https://custom.api.com/v1"

    def test_custom_timeout(self) -> None:
        client = OpenCodeClient(api_key="test-key-12345678", timeout=30)
        assert client._timeout == 30

    def test_trailing_slash_stripped(self) -> None:
        client = OpenCodeClient(api_key="test-key-12345678", base_url="https://api.example.com/v1/")
        assert client._base_url == "https://api.example.com/v1"

    def test_empty_api_key_raises(self) -> None:
        with pytest.raises(ConfigError, match="must not be empty"):
            OpenCodeClient(api_key="")

    def test_short_api_key_raises(self) -> None:
        with pytest.raises(ConfigError, match="too short"):
            OpenCodeClient(api_key="short")

    def test_whitespace_in_api_key_raises(self) -> None:
        with pytest.raises(ConfigError, match="whitespace"):
            OpenCodeClient(api_key="key with spaces here")

    def test_http_base_url_raises(self) -> None:
        with pytest.raises(ConfigError, match="HTTPS"):
            OpenCodeClient(api_key="test-key-12345678", base_url="http://api.example.com")

    def test_no_scheme_base_url_raises(self) -> None:
        with pytest.raises(ConfigError, match="HTTPS"):
            OpenCodeClient(api_key="test-key-12345678", base_url="api.example.com")

    def test_timeout_zero_raises(self) -> None:
        with pytest.raises(ConfigError, match="Timeout must be between"):
            OpenCodeClient(api_key="test-key-12345678", timeout=0)

    def test_negative_timeout_raises(self) -> None:
        with pytest.raises(ConfigError, match="Timeout must be between"):
            OpenCodeClient(api_key="test-key-12345678", timeout=-5)

    def test_timeout_over_max_raises(self) -> None:
        with pytest.raises(ConfigError, match="Timeout must be between"):
            OpenCodeClient(api_key="test-key-12345678", timeout=_MAX_TIMEOUT + 1)

    def test_timeout_at_max_ok(self) -> None:
        client = OpenCodeClient(api_key="test-key-12345678", timeout=_MAX_TIMEOUT)
        assert client._timeout == _MAX_TIMEOUT

    def test_timeout_at_one_ok(self) -> None:
        client = OpenCodeClient(api_key="test-key-12345678", timeout=1)
        assert client._timeout == 1

    def test_exactly_min_key_length(self) -> None:
        key = "a" * _MIN_KEY_LENGTH
        client = OpenCodeClient(api_key=key)
        assert client._api_key == key

    def test_one_below_min_key_length(self) -> None:
        key = "a" * (_MIN_KEY_LENGTH - 1)
        with pytest.raises(ConfigError, match="too short"):
            OpenCodeClient(api_key=key)

    def test_ssl_context_created(self) -> None:
        client = OpenCodeClient(api_key="test-key-12345678")
        assert isinstance(client._ssl_ctx, ssl.SSLContext)

    def test_stores_api_key(self) -> None:
        client = OpenCodeClient(api_key="test-key-12345678")
        assert client._api_key == "test-key-12345678"


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------

class TestOpenCodeClientRepr:
    """Test that repr does NOT expose the API key."""

    def test_repr_no_api_key(self) -> None:
        client = OpenCodeClient(api_key="secret-key-12345678")
        r = repr(client)
        assert "secret-key-12345678" not in r

    def test_repr_contains_model(self) -> None:
        client = OpenCodeClient(api_key="test-key-12345678", model="my-model")
        r = repr(client)
        assert "my-model" in r

    def test_repr_contains_base_url(self) -> None:
        client = OpenCodeClient(api_key="test-key-12345678", base_url="https://api.example.com/v1")
        r = repr(client)
        assert "api.example.com" in r


# ---------------------------------------------------------------------------
# from_env classmethod
# ---------------------------------------------------------------------------

class TestOpenCodeClientFromEnv:
    """Test the from_env factory method."""

    def test_from_env_with_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENCODE_API_KEY", "env-key-12345678")
        client = OpenCodeClient.from_env()
        assert client._api_key == "env-key-12345678"
        assert client._model == _DEFAULT_MODEL

    def test_from_env_custom_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENCODE_API_KEY", "env-key-12345678")
        client = OpenCodeClient.from_env(model="custom-model")
        assert client._model == "custom-model"

    def test_from_env_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
        with pytest.raises(ConfigError):
            OpenCodeClient.from_env()


# ---------------------------------------------------------------------------
# create_image_message
# ---------------------------------------------------------------------------

class TestCreateImageMessage:
    """Test image message builder."""

    def test_basic_image_message(self, client: OpenCodeClient) -> None:
        msg = client.create_image_message("base64data", "Describe this image")
        assert msg["role"] == "user"
        assert isinstance(msg["content"], list)
        assert len(msg["content"]) == 2

    def test_image_url_format(self, client: OpenCodeClient) -> None:
        msg = client.create_image_message("base64data", "Describe")
        img_part = msg["content"][0]
        assert img_part["type"] == "image_url"
        assert img_part["image_url"]["url"] == "data:image/jpeg;base64,base64data"

    def test_text_part(self, client: OpenCodeClient) -> None:
        msg = client.create_image_message("b64", "What is this?")
        text_part = msg["content"][1]
        assert text_part["type"] == "text"
        assert text_part["text"] == "What is this?"

    def test_custom_mime_type(self, client: OpenCodeClient) -> None:
        msg = client.create_image_message("b64", "test", mime_type="image/png")
        img_url = msg["content"][0]["image_url"]["url"]
        assert img_url.startswith("data:image/png;base64,")

    def test_role_is_user(self, client: OpenCodeClient) -> None:
        msg = client.create_image_message("b64", "test")
        assert msg["role"] == "user"


# ---------------------------------------------------------------------------
# create_multiframe_message
# ---------------------------------------------------------------------------

class TestCreateMultiframeMessage:
    """Test multi-frame message builder."""

    def test_single_frame(self, client: OpenCodeClient) -> None:
        msg = client.create_multiframe_message(["frame1b64"], "transcript text")
        assert msg["role"] == "user"
        assert isinstance(msg["content"], list)
        assert len(msg["content"]) == 2  # 1 image + 1 text

    def test_multiple_frames(self, client: OpenCodeClient) -> None:
        frames = ["f1b64", "f2b64", "f3b64"]
        msg = client.create_multiframe_message(frames, "transcript")
        assert len(msg["content"]) == 4  # 3 images + 1 text

    def test_text_is_last(self, client: OpenCodeClient) -> None:
        msg = client.create_multiframe_message(["f1", "f2"], "transcript")
        last = msg["content"][-1]
        assert last["type"] == "text"
        assert last["text"] == "transcript"

    def test_images_are_correct_type(self, client: OpenCodeClient) -> None:
        msg = client.create_multiframe_message(["f1", "f2"], "t")
        for part in msg["content"][:-1]:
            assert part["type"] == "image_url"

    def test_custom_mime_type(self, client: OpenCodeClient) -> None:
        msg = client.create_multiframe_message(["f1"], "t", mime_type="image/webp")
        url = msg["content"][0]["image_url"]["url"]
        assert "data:image/webp;base64,f1" in url

    def test_empty_frames_list(self, client: OpenCodeClient) -> None:
        msg = client.create_multiframe_message([], "transcript only")
        assert len(msg["content"]) == 1
        assert msg["content"][0]["type"] == "text"


# ---------------------------------------------------------------------------
# create_video_message
# ---------------------------------------------------------------------------

class TestCreateVideoMessage:
    """Test video message builder."""

    def test_basic_video_message(self, client: OpenCodeClient) -> None:
        msg = client.create_video_message("videob64", "Describe the video")
        assert msg["role"] == "user"
        assert isinstance(msg["content"], list)
        assert len(msg["content"]) == 2

    def test_video_url_format(self, client: OpenCodeClient) -> None:
        msg = client.create_video_message("videob64", "test")
        video_part = msg["content"][0]
        assert video_part["type"] == "video_url"
        assert video_part["video_url"]["url"] == "data:video/mp4;base64,videob64"

    def test_fps_parameter(self, client: OpenCodeClient) -> None:
        msg = client.create_video_message("vb64", "test", fps=0.5)
        assert msg["content"][0]["video_url"]["fps"] == 0.5

    def test_default_fps(self, client: OpenCodeClient) -> None:
        msg = client.create_video_message("vb64", "test")
        assert msg["content"][0]["video_url"]["fps"] == 0.25

    def test_custom_mime_type(self, client: OpenCodeClient) -> None:
        msg = client.create_video_message("vb64", "test", mime_type="video/webm")
        url = msg["content"][0]["video_url"]["url"]
        assert "data:video/webm;base64," in url

    def test_text_part(self, client: OpenCodeClient) -> None:
        msg = client.create_video_message("vb64", "Analyze this")
        text_part = msg["content"][1]
        assert text_part["type"] == "text"
        assert text_part["text"] == "Analyze this"

    def test_media_resolution_default(self, client: OpenCodeClient) -> None:
        msg = client.create_video_message("vb64", "test")
        assert msg["content"][0]["video_url"]["media_resolution"] == "default"


# ---------------------------------------------------------------------------
# chat_completion (mocked network)
# ---------------------------------------------------------------------------

class TestChatCompletion:
    """Test chat_completion with mocked HTTP responses."""

    def test_basic_call(self, client: OpenCodeClient, mock_response: dict) -> None:
        with patch.object(urllib.request, "urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            result = client.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
            )
            assert result == mock_response

    def test_payload_contains_model(self, client: OpenCodeClient, mock_response: dict) -> None:
        with patch.object(urllib.request, "urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            client.chat_completion(messages=[{"role": "user", "content": "Hi"}])

            req = mock_open.call_args[0][0]
            body = json.loads(req.data.decode("utf-8"))
            assert body["model"] == _DEFAULT_MODEL

    def test_payload_temperature(self, client: OpenCodeClient, mock_response: dict) -> None:
        with patch.object(urllib.request, "urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            client.chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.3,
            )
            req = mock_open.call_args[0][0]
            body = json.loads(req.data.decode("utf-8"))
            assert body["temperature"] == 0.3

    def test_payload_max_tokens(self, client: OpenCodeClient, mock_response: dict) -> None:
        with patch.object(urllib.request, "urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            client.chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=2048,
            )
            req = mock_open.call_args[0][0]
            body = json.loads(req.data.decode("utf-8"))
            assert body["max_tokens"] == 2048

    def test_authorization_header(self, client: OpenCodeClient, mock_response: dict) -> None:
        with patch.object(urllib.request, "urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            client.chat_completion(messages=[{"role": "user", "content": "Hi"}])
            req = mock_open.call_args[0][0]
            assert req.get_header("Authorization") == "Bearer test-key-12345678"

    def test_per_request_timeout(self, client: OpenCodeClient, mock_response: dict) -> None:
        with patch.object(urllib.request, "urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            client.chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                timeout=30,
            )
            assert mock_open.call_args[1].get("timeout") == 30

    def test_http_429_raises_rate_limit(self, client: OpenCodeClient) -> None:
        with patch.object(urllib.request, "urlopen") as mock_open:
            mock_open.side_effect = urllib.error.HTTPError(
                url="https://api.example.com",
                code=429,
                msg="Too Many Requests",
                hdrs=None,
                fp=MagicMock(read=MagicMock(return_value=b"rate limited")),
            )
            with pytest.raises(RateLimitError):
                client.chat_completion(
                    messages=[{"role": "user", "content": "Hi"}],
                )

    def test_http_500_raises_open_code_error(self, client: OpenCodeClient) -> None:
        with patch.object(urllib.request, "urlopen") as mock_open:
            mock_open.side_effect = urllib.error.HTTPError(
                url="https://api.example.com",
                code=500,
                msg="Internal Server Error",
                hdrs=None,
                fp=MagicMock(read=MagicMock(return_value=b"server error")),
            )
            with pytest.raises(OpenCodeError):
                client.chat_completion(
                    messages=[{"role": "user", "content": "Hi"}],
                )

    def test_invalid_json_response_raises(self, client: OpenCodeClient) -> None:
        with patch.object(urllib.request, "urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"not valid json {{{"
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            with pytest.raises(OpenCodeError, match="Invalid JSON"):
                client.chat_completion(
                    messages=[{"role": "user", "content": "Hi"}],
                )

    def test_url_error_raises(self, client: OpenCodeClient) -> None:
        with patch.object(urllib.request, "urlopen") as mock_open:
            mock_open.side_effect = urllib.error.URLError("Connection refused")
            with pytest.raises(OpenCodeError, match="Network error"):
                client.chat_completion(
                    messages=[{"role": "user", "content": "Hi"}],
                )


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------

class TestErrorHierarchy:
    """Verify OpenCode error classes follow the expected hierarchy."""

    def test_open_code_error_is_api_error(self) -> None:
        assert issubclass(OpenCodeError, APIError)

    def test_rate_limit_error_is_open_code_error(self) -> None:
        assert issubclass(RateLimitError, OpenCodeError)

    def test_rate_limit_error_is_api_error(self) -> None:
        assert issubclass(RateLimitError, APIError)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge-case tests for the client."""

    def test_empty_messages_list(self, client: OpenCodeClient, mock_response: dict) -> None:
        with patch.object(urllib.request, "urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            result = client.chat_completion(messages=[])
            assert result == mock_response

    def test_multimodal_messages(self, client: OpenCodeClient, mock_response: dict) -> None:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe"},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc"}},
                ],
            }
        ]
        with patch.object(urllib.request, "urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            result = client.chat_completion(messages=messages)
            assert result == mock_response

    def test_temperature_boundaries(self, client: OpenCodeClient, mock_response: dict) -> None:
        for temp in (0.0, 2.0):
            with patch.object(urllib.request, "urlopen") as mock_open:
                mock_resp = MagicMock()
                mock_resp.read.return_value = json.dumps(mock_response).encode("utf-8")
                mock_resp.__enter__ = lambda s: s
                mock_resp.__exit__ = MagicMock(return_value=False)
                mock_open.return_value = mock_resp

                client.chat_completion(
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=temp,
                )
                req = mock_open.call_args[0][0]
                body = json.loads(req.data.decode("utf-8"))
                assert body["temperature"] == temp

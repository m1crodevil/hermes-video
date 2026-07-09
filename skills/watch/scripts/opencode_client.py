#!/usr/bin/env python3
"""OpenCode Zen API client for MiMo V2.5 integration.

Secure HTTP client using only stdlib (urllib.request + ssl) for calling
the OpenCode Zen API.  Supports:

- Chat completions (text and multimodal)
- Single image + text messages
- Multiple frame + transcript messages

Security best practices:
- API key loaded from environment only (never hardcoded)
- HTTPS enforced — all requests use SSL certificate verification
- Timeout on every request to prevent hangs
- API key never logged or included in error messages
- Input validation on API key format
"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any

from .errors import APIError, ConfigError


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://opencode.ai/zen/v1"
_DEFAULT_MODEL = "mimo-v2.5-free"
_DEFAULT_TIMEOUT = 120  # seconds
_MIN_KEY_LENGTH = 10
_MAX_TIMEOUT = 600


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OpenCodeError(APIError):
    """Raised when an OpenCode API call fails."""


class RateLimitError(OpenCodeError):
    """Raised on HTTP 429 responses."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class OpenCodeClient:
    """Lightweight OpenCode Zen API client (stdlib only).

    Example::

        client = OpenCodeClient.from_env()
        resp = client.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
        )
        print(resp["choices"][0]["message"]["content"])
    """

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise the client with explicit credentials.

        Args:
            api_key: OpenCode Zen API key (validated for minimum length).
            model: Model identifier (default ``mimo-v2.5-free``).
            base_url: API base URL (must be HTTPS).
            timeout: Request timeout in seconds (max 600).

        Raises:
            ConfigError: If *api_key* is invalid or *base_url* is not HTTPS.
        """
        # --- API key validation ---
        if not api_key:
            raise ConfigError("API key must not be empty", missing_key="api_key")
        if len(api_key) < _MIN_KEY_LENGTH:
            raise ConfigError(
                f"API key too short (minimum {_MIN_KEY_LENGTH} chars)",
                missing_key="api_key",
            )
        if " " in api_key:
            raise ConfigError(
                "API key must not contain whitespace",
                missing_key="api_key",
            )

        # --- Base URL validation ---
        if not base_url.startswith("https://"):
            raise ConfigError(
                "Base URL must use HTTPS",
                missing_key="base_url",
            )

        # --- Timeout validation ---
        if timeout < 1 or timeout > _MAX_TIMEOUT:
            raise ConfigError(
                f"Timeout must be between 1 and {_MAX_TIMEOUT} seconds",
                missing_key="timeout",
            )

        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        # Reusable SSL context — verify certificates
        self._ssl_ctx = ssl.create_default_context()

    # ------------------------------------------------------------------
    # Factory — load key from environment
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls, model: str = _DEFAULT_MODEL) -> OpenCodeClient:
        """Create a client using the ``OPENCODE_API_KEY`` env variable.

        Loads the key via :func:`env.get_api_key` which checks:
        1. ``OPENCODE_API_KEY`` environment variable
        2. ``~/.config/watch/.env`` file

        Raises:
            ConfigError: If the API key is missing or invalid.
        """
        from .env import get_api_key

        api_key = get_api_key("OPENCODE_API_KEY", required=True)
        # get_api_key returns str | None, but required=True guarantees str
        assert api_key is not None  # for type checker
        return cls(api_key=api_key, model=model)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request.

        Args:
            messages: OpenAI-style message list (``role`` + ``content``).
            temperature: Sampling temperature (0.0 – 2.0).
            max_tokens: Maximum tokens in the response.
            timeout: Optional per-request timeout override (seconds).

        Returns:
            The full JSON response dict from the API.

        Raises:
            OpenCodeError: On non-2xx HTTP status or malformed response.
            RateLimitError: On HTTP 429 (rate limited).
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return self._post("/chat/completions", payload, timeout=timeout)

    def create_image_message(
        self,
        image_b64: str,
        text: str,
        *,
        mime_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        """Build a user message containing a base64-encoded image + text.

        Args:
            image_b64: Raw base64 string (no ``data:`` prefix).
            text: Text prompt to accompany the image.
            mime_type: Image MIME type (default ``image/jpeg``).

        Returns:
            A dict suitable for inclusion in a ``messages`` list.
        """
        return {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_b64}",
                    },
                },
                {"type": "text", "text": text},
            ],
        }

    def create_multiframe_message(
        self,
        frames: list[str],
        transcript: str,
        *,
        mime_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        """Build a user message with multiple base64 frames + transcript.

        Args:
            frames: List of raw base64 strings (no ``data:`` prefix).
            transcript: Transcript text to include alongside frames.
            mime_type: Image MIME type (default ``image/jpeg``).

        Returns:
            A dict suitable for inclusion in a ``messages`` list.
        """
        content: list[dict[str, Any]] = []
        for b64 in frames:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{b64}",
                },
            })
        content.append({"type": "text", "text": transcript})
        return {"role": "user", "content": content}

    def create_video_message(
        self,
        video_b64: str,
        text: str,
        *,
        mime_type: str = "video/mp4",
        fps: float = 0.25,
    ) -> dict[str, Any]:
        """Build a user message containing a base64-encoded video + text.

        Args:
            video_b64: Raw base64 string (no ``data:`` prefix).
            text: Text prompt to accompany the video.
            mime_type: Video MIME type (default ``video/mp4``).
            fps: Frames-per-second for the vision encoder.

        Returns:
            A dict suitable for inclusion in a ``messages`` list.
        """
        return {
            "role": "user",
            "content": [
                {
                    "type": "video_url",
                    "video_url": {
                        "url": f"data:{mime_type};base64,{video_b64}",
                        "fps": fps,
                        "media_resolution": "default",
                    },
                },
                {"type": "text", "text": text},
            ],
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Low-level POST to the API.

        Args:
            path: URL path appended to the base URL (e.g. ``/chat/completions``).
            payload: JSON-serialisable request body.
            timeout: Optional timeout override.

        Returns:
            Parsed JSON response.

        Raises:
            OpenCodeError: On HTTP errors or invalid responses.
            RateLimitError: On HTTP 429.
        """
        url = f"{self._base_url}{path}"
        req_timeout = timeout or self._timeout

        # Serialise body
        try:
            body = json.dumps(payload).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise OpenCodeError(
                f"Failed to serialise request payload: {exc}",
                endpoint=url,
            ) from exc

        # Build request
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )

        # Execute with SSL verification
        try:
            with urllib.request.urlopen(
                req,
                timeout=req_timeout,
                context=self._ssl_ctx,
            ) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            status = exc.code
            body_text = ""
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            if status == 429:
                raise RateLimitError(
                    "Rate limited by API",
                    endpoint=url,
                    status_code=status,
                    response_body=body_text[:200],
                ) from exc

            raise OpenCodeError(
                f"HTTP {status} from API",
                endpoint=url,
                status_code=status,
                response_body=body_text[:200],
            ) from exc

        except urllib.error.URLError as exc:
            raise OpenCodeError(
                f"Network error: {exc.reason}",
                endpoint=url,
            ) from exc

        except TimeoutError:
            raise OpenCodeError(
                f"Request timed out after {req_timeout}s",
                endpoint=url,
            )

        # Parse JSON
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OpenCodeError(
                f"Invalid JSON response: {exc}",
                endpoint=url,
            ) from exc

        return result

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        # Never expose the API key in repr
        return (
            f"OpenCodeClient(model={self._model!r}, "
            f"base_url={self._base_url!r})"
        )

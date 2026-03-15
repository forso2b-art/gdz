from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from gdz_bot.config import Config

logger = logging.getLogger(__name__)


class OpenRouterError(RuntimeError):
    pass


class OpenRouterRetryableError(OpenRouterError):
    pass


class OpenRouterClient:
    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, config: Config) -> None:
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._rotation_lock = asyncio.Lock()
        self._next_key_index = 0

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=120)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def create_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        attempts = await self._get_attempt_order()
        errors: list[str] = []

        for key_index in attempts:
            try:
                return await self._request_with_key(payload, key_index)
            except OpenRouterRetryableError as exc:
                logger.warning("OpenRouter key %s failed, switching to next key: %s", key_index + 1, exc)
                errors.append(f"key_{key_index + 1}: {exc}")
                continue
            except OpenRouterError as exc:
                raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc

        raise OpenRouterError("All OpenRouter API keys failed: " + " | ".join(errors))

    async def _get_attempt_order(self) -> list[int]:
        async with self._rotation_lock:
            start_index = self._next_key_index
            self._next_key_index = (self._next_key_index + 1) % len(self.config.openrouter_api_keys)

        return [
            (start_index + offset) % len(self.config.openrouter_api_keys)
            for offset in range(len(self.config.openrouter_api_keys))
        ]

    def _headers_for_key(self, key_index: int) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.openrouter_api_keys[key_index]}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.config.openrouter_http_referer,
            "X-Title": self.config.openrouter_app_title,
        }

    async def _request_with_key(self, payload: dict[str, Any], key_index: int) -> dict[str, Any]:
        try:
            async with self.session.post(
                self.API_URL,
                data=json.dumps(payload),
                headers=self._headers_for_key(key_index),
            ) as response:
                body = await response.text()
        except asyncio.TimeoutError as exc:
            raise OpenRouterRetryableError("request timed out") from exc
        except aiohttp.ClientError as exc:
            raise OpenRouterRetryableError(str(exc)) from exc

        if response.status < 400:
            try:
                return json.loads(body)
            except json.JSONDecodeError as exc:
                raise OpenRouterRetryableError("invalid JSON response") from exc

        if response.status in {401, 402, 403, 408, 409, 429, 500, 502, 503, 504}:
            raise OpenRouterRetryableError(f"status {response.status}: {body[:300]}")

        raise OpenRouterError(f"status {response.status}: {body[:500]}")

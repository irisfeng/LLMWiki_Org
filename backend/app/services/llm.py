import json
import logging
from dataclasses import dataclass
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


# Errors that justify falling back to the secondary provider.
# 4xx other than 429 stay on primary (business errors, bad prompt, bad auth).
_FALLBACK_HTTP_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class ProviderConfig:
    api_key: str
    base_url: str
    model: str
    provider: str  # "dashscope" | "doubao" | "openai"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


def _translate_thinking(provider: str, enable_thinking: bool | None, thinking_budget: int | None) -> dict:
    """Map generic thinking flags to provider-specific payload fields."""
    if enable_thinking is None:
        return {}
    if provider == "dashscope":
        out: dict = {"enable_thinking": enable_thinking}
        if thinking_budget is not None:
            out["thinking_budget"] = thinking_budget
        return out
    if provider == "doubao":
        # Volcengine Ark uses {"thinking": {"type": "enabled"|"disabled"|"auto"}}.
        # thinking_budget is not honored — Doubao self-regulates; ignored.
        return {"thinking": {"type": "enabled" if enable_thinking else "disabled"}}
    # Generic OpenAI-compatible: no standardized thinking flag. Omit.
    return {}


class LLMClient:
    def __init__(
        self,
        primary: ProviderConfig | None = None,
        fallback: ProviderConfig | None = None,
    ):
        self.primary = primary or ProviderConfig(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            provider=settings.llm_provider,
        )
        self.fallback = fallback or ProviderConfig(
            api_key=settings.fallback_api_key,
            base_url=settings.fallback_base_url,
            model=settings.fallback_model,
            provider=settings.fallback_provider,
        )

    def _should_fallback(self, exc: Exception) -> bool:
        if not self.fallback.is_configured:
            return False
        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in _FALLBACK_HTTP_CODES
        return False

    async def _post_once(self, p: ProviderConfig, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{p.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {p.api_key}", "Content-Type": "application/json"},
                json={**payload, "model": p.model},
            )
            response.raise_for_status()
            return response.json()

    async def chat(self, user_message: str, system_message: str = "", temperature: float = 0.3) -> str:
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})
        payload = {"messages": messages, "temperature": temperature}

        try:
            data = await self._post_once(self.primary, payload)
        except Exception as e:
            if not self._should_fallback(e):
                raise
            logger.warning("Primary LLM failed (%s); falling back to %s", type(e).__name__, self.fallback.model)
            data = await self._post_once(self.fallback, payload)
        return data["choices"][0]["message"]["content"]

    async def chat_json(self, user_message: str, system_message: str = "", temperature: float = 0.1) -> dict:
        raw = await self.chat(user_message, system_message, temperature)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(raw)

    async def _stream_once(self, p: ProviderConfig, payload: dict):
        """Open a single streaming call against one provider. May yield or raise."""
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{p.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {p.api_key}", "Content-Type": "application/json"},
                json={**payload, "model": p.model},
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    logger.error("LLM stream error %d (%s): %s", response.status_code, p.provider, body.decode(errors="replace"))
                    raise httpx.HTTPStatusError(
                        f"LLM API returned {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {})
                            rc = delta.get("reasoning_content")
                            if rc:
                                yield {"reasoning": rc}
                            if delta.get("content"):
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError, IndexError) as e:
                            logger.warning("Skipping malformed stream chunk: %s — %s", line, e)

    async def chat_stream(
        self,
        messages: list[dict],
        system_message: str = "",
        temperature: float = 0.5,
        enable_thinking: bool | None = None,
        thinking_budget: int | None = None,
    ):
        """Stream chat completion with automatic fallback to Volcengine on primary failure.

        Thinking flags are translated to each provider's dialect. Fallback only
        engages before any token is emitted — once streaming begins we do not
        rewind (server already committed partial content to the user).

        Yields:
          - str  : regular answer tokens
          - dict : {"reasoning": "..."} for thinking-chain tokens
        """
        all_messages = []
        if system_message:
            all_messages.append({"role": "system", "content": system_message})
        all_messages.extend(messages)

        def build_payload(p: ProviderConfig) -> dict:
            payload: dict = {
                "messages": all_messages,
                "temperature": temperature,
                "stream": True,
            }
            payload.update(_translate_thinking(p.provider, enable_thinking, thinking_budget))
            return payload

        # Attempt primary. Buffer zero tokens — only retry fallback if the
        # primary errors before any content is yielded.
        started = False
        try:
            async for item in self._stream_once(self.primary, build_payload(self.primary)):
                started = True
                yield item
            return
        except Exception as e:
            if started or not self._should_fallback(e):
                raise
            logger.warning(
                "Primary LLM stream failed (%s); falling back to %s",
                type(e).__name__, self.fallback.model,
            )

        async for item in self._stream_once(self.fallback, build_payload(self.fallback)):
            yield item


llm_client = LLMClient()

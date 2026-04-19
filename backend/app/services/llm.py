import json
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, api_key: str = "", base_url: str = "", model: str = ""):
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model

    async def chat(self, user_message: str, system_message: str = "", temperature: float = 0.3) -> str:
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": messages, "temperature": temperature},
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def chat_json(self, user_message: str, system_message: str = "", temperature: float = 0.1) -> dict:
        raw = await self.chat(user_message, system_message, temperature)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(raw)

    async def chat_stream(
        self,
        messages: list[dict],
        system_message: str = "",
        temperature: float = 0.5,
        enable_thinking: bool | None = None,
        thinking_budget: int | None = None,
    ):
        """Stream chat completion.

        Yields:
          - str  : regular answer tokens (delta.content)
          - dict : {"reasoning": "..."} for thinking-chain tokens (delta.reasoning_content),
                   available on qwen3.x thinking models.
        """
        all_messages = []
        if system_message:
            all_messages.append({"role": "system", "content": system_message})
        all_messages.extend(messages)

        payload: dict = {
            "model": self.model,
            "messages": all_messages,
            "temperature": temperature,
            "stream": True,
        }
        # DashScope-specific thinking controls. Harmless on non-qwen providers if
        # they ignore unknown fields; if a provider rejects them, callers should
        # pass enable_thinking=None to omit.
        if enable_thinking is not None:
            payload["enable_thinking"] = enable_thinking
        if thinking_budget is not None:
            payload["thinking_budget"] = thinking_budget

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    logger.error("LLM stream error %d: %s", response.status_code, body.decode(errors="replace"))
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


llm_client = LLMClient()

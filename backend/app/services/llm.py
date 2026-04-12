import json
import httpx
from app.config import settings


class LLMClient:
    def __init__(self, api_key: str = "", base_url: str = "", model: str = ""):
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self._client = httpx.AsyncClient(timeout=120.0)

    async def chat(self, user_message: str, system_message: str = "", temperature: float = 0.3) -> str:
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})

        response = await self._client.post(
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

    async def chat_stream(self, messages: list[dict], system_message: str = "", temperature: float = 0.5):
        all_messages = []
        if system_message:
            all_messages.append({"role": "system", "content": system_message})
        all_messages.extend(messages)

        async with self._client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": all_messages, "temperature": temperature, "stream": True},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]

    async def close(self):
        await self._client.aclose()


llm_client = LLMClient()

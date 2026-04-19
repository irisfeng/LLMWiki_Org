import pytest
from unittest.mock import AsyncMock, patch
from app.services.llm import LLMClient, ProviderConfig


@pytest.mark.asyncio
async def test_llm_client_chat():
    client = LLMClient(
        primary=ProviderConfig(
            api_key="test-key",
            base_url="http://fake",
            model="test-model",
            provider="openai",
        )
    )
    mock_response = {
        "choices": [{"message": {"content": "Hello world"}}]
    }
    with patch.object(client, "_post_once", new_callable=AsyncMock, return_value=mock_response):
        result = await client.chat("Say hello")
        assert result == "Hello world"

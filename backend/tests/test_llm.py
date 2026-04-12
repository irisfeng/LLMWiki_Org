import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm import LLMClient


@pytest.mark.asyncio
async def test_llm_client_chat():
    client = LLMClient(api_key="test-key", base_url="http://fake", model="test-model")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello world"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.chat("Say hello")
        assert result == "Hello world"

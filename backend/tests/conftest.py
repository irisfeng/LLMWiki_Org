import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_llm_response():
    return {
        "choices": [{
            "message": {
                "content": '{"source_page": {"title": "Test", "slug": "test", "frontmatter": {}, "content": "# Test"}}'
            }
        }]
    }

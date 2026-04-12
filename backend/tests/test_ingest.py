import pytest
from app.services.ingest import IngestService

MOCK_LLM_OUTPUT = {
    "source_page": {
        "title": "测试文章",
        "slug": "test-article",
        "frontmatter": {"source_type": "article", "author": "张三", "tags": ["testing"]},
        "content": "## Summary\n\n这是一篇测试文章的摘要。\n\n## Connections\n\n- [[zhang-san]]"
    },
    "entity_pages": [
        {
            "slug": "zhang-san",
            "action": "create",
            "title": "张三",
            "frontmatter": {"entity_type": "person", "tags": ["author"]},
            "content": "张三是一位作者。\n\n## Sources\n\n- [[test-article]]"
        }
    ],
    "concept_pages": [],
    "cross_references": []
}


def test_ingest_parses_llm_output():
    service = IngestService()
    pages = service.parse_llm_output(MOCK_LLM_OUTPUT)
    assert len(pages) == 2
    assert pages[0]["slug"] == "test-article"
    assert pages[0]["type"] == "source"
    assert pages[1]["slug"] == "zhang-san"
    assert pages[1]["type"] == "entity"


def test_extract_wikilinks():
    service = IngestService()
    links = service.extract_wikilinks("See [[foo-bar]] and [[baz-qux]] for details.")
    assert links == ["foo-bar", "baz-qux"]

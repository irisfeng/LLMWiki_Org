import re
from datetime import datetime, timezone
from app.services.llm import llm_client

INGEST_SYSTEM_PROMPT = """你是一个知识库编译器。你的任务是将原始资料编译为结构化的 Wiki 页面。

## 输出格式

你必须输出一个合法 JSON 对象（不要用 markdown code fence 包裹），包含以下字段：

{
  "source_page": {
    "title": "源标题",
    "slug": "url-friendly-slug（英文小写+连字符）",
    "frontmatter": { "source_type": "article|paper|book|report|tweet|other", "author": "作者", "date": "YYYY-MM-DD", "tags": [] },
    "content": "Markdown 正文，包含 ## Summary, ## Key Claims, ## Connections, ## Quotes 章节"
  },
  "entity_pages": [
    {
      "slug": "entity-slug",
      "action": "create",
      "title": "实体名称",
      "frontmatter": { "entity_type": "person|organization|place|product|event", "aliases": [], "tags": [] },
      "content": "实体描述，包含 ## Sources 章节链接到 source 页"
    }
  ],
  "concept_pages": [
    {
      "slug": "concept-slug",
      "action": "create",
      "title": "概念名称",
      "frontmatter": { "aliases": [], "tags": [] },
      "content": "概念解释，包含 ## Sources 章节"
    }
  ],
  "cross_references": [
    { "page_slug": "已有页面slug", "add_links": ["新页面slug"], "add_content": "追加的关联说明" }
  ]
}

## 写作规则
- 每个断言必须可溯源到原始资料
- 使用 [[slug]] 格式做交叉引用
- 简洁精确，无废话
- 中文源用中文写，英文源用英文写
- tags 使用小写连字符格式
- slug 用英文小写+连字符，从标题翻译/转写得到
- 只提取真正重要的实体和概念，不要过度拆分"""


class IngestService:
    def parse_llm_output(self, data: dict) -> list[dict]:
        pages = []
        sp = data["source_page"]
        pages.append({
            "type": "source",
            "slug": sp["slug"],
            "title": sp["title"],
            "frontmatter": sp.get("frontmatter", {}),
            "content": sp["content"],
        })
        for ep in data.get("entity_pages", []):
            pages.append({
                "type": "entity",
                "slug": ep["slug"],
                "title": ep["title"],
                "frontmatter": ep.get("frontmatter", {}),
                "content": ep.get("content", ""),
                "action": ep.get("action", "create"),
            })
        for cp in data.get("concept_pages", []):
            pages.append({
                "type": "concept",
                "slug": cp["slug"],
                "title": cp["title"],
                "frontmatter": cp.get("frontmatter", {}),
                "content": cp.get("content", ""),
                "action": cp.get("action", "create"),
            })
        return pages

    def extract_wikilinks(self, content: str) -> list[str]:
        return re.findall(r'\[\[([^\]]+)\]\]', content)

    async def build_context(self, db_session) -> str:
        from sqlalchemy import select
        from app.models import WikiPage
        result = await db_session.execute(select(WikiPage.type, WikiPage.slug, WikiPage.title))
        rows = result.all()
        if not rows:
            return "当前知识库为空，这是第一个源。"
        lines = ["当前知识库已有页面："]
        for row in rows:
            lines.append(f"- [{row.type}] {row.slug}: {row.title}")
        return "\n".join(lines)

    async def process_source(self, source_id: str, content_text: str, db_session):
        from sqlalchemy import select
        from app.models import WikiPage, RawSource, WikiLink

        context = await self.build_context(db_session)
        user_message = f"{context}\n\n---\n\n## 待处理的新源材料：\n\n{content_text[:30000]}"
        data = await llm_client.chat_json(user_message, system_message=INGEST_SYSTEM_PROMPT)
        pages = self.parse_llm_output(data)

        created_pages = []
        for page_data in pages:
            action = page_data.pop("action", "create")
            if action == "update":
                existing = await db_session.execute(select(WikiPage).where(WikiPage.slug == page_data["slug"]))
                existing_page = existing.scalar_one_or_none()
                if existing_page:
                    existing_page.content += "\n\n" + page_data["content"]
                    existing_page.updated_at = datetime.now(timezone.utc)
                    created_pages.append(existing_page)
                    continue
            if page_data["type"] == "source":
                page_data["source_id"] = source_id
            new_page = WikiPage(**page_data)
            db_session.add(new_page)
            created_pages.append(new_page)

        await db_session.flush()

        for page in created_pages:
            links = self.extract_wikilinks(page.content)
            for link_slug in links:
                target = await db_session.execute(select(WikiPage.id).where(WikiPage.slug == link_slug))
                target_id = target.scalar_one_or_none()
                wl = WikiLink(from_page_id=page.id, to_page_id=target_id, to_slug=link_slug)
                db_session.add(wl)

        for xref in data.get("cross_references", []):
            existing = await db_session.execute(select(WikiPage).where(WikiPage.slug == xref["page_slug"]))
            existing_page = existing.scalar_one_or_none()
            if existing_page and xref.get("add_content"):
                existing_page.content += "\n\n" + xref["add_content"]
                existing_page.updated_at = datetime.now(timezone.utc)

        source = await db_session.get(RawSource, source_id)
        source.status = "done"
        source.processed_at = datetime.now(timezone.utc)
        await db_session.commit()
        return created_pages


ingest_service = IngestService()

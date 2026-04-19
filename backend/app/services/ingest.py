import asyncio
import logging
import re
from datetime import datetime, timezone
from app.services.llm import llm_client
from app.services.embedding import embedding_service
from app.services.chunker import chunk_markdown

logger = logging.getLogger(__name__)

INGEST_SYSTEM_PROMPT = """你是一个知识库编译器。你的任务是将原始资料编译为结构化的 Wiki 页面。

上下文中会列出知识库已有的页面（type, slug, title）。**已存在的 entity/concept 页面要用 action="update"**（之后系统会把旧内容和你给的新摘要一起喂给修订器，产出整合版）；真正新的页面才用 action="create"。

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
      "action": "create | update",
      "title": "实体名称",
      "frontmatter": { "entity_type": "person|organization|place|product|event", "aliases": [], "tags": [] },
      "content": "如果是 create：完整实体描述，含 ## Sources。如果是 update：仅本次新源对该实体补充/修正/冲突的要点，作为修订提示（不要重复旧页已有信息）"
    }
  ],
  "concept_pages": [
    {
      "slug": "concept-slug",
      "action": "create | update",
      "title": "概念名称",
      "frontmatter": { "aliases": [], "tags": [] },
      "content": "语义同上"
    }
  ],
  "cross_references": [
    { "page_slug": "已有页面slug", "add_links": ["新页面slug"], "add_content": "追加的关联说明（限非实体/非概念的 source 页）" }
  ],
  "contradictions": [
    {
      "page_slug": "受影响的已有页面 slug",
      "old_claim": "旧页已有的论断（简短摘录）",
      "new_claim": "新源提出的冲突论断",
      "resolution_hint": "可选：如何调和或哪个更可信"
    }
  ]
}

## 写作规则
- 每个断言必须可溯源到原始资料
- 使用 [[slug]] 格式做交叉引用
- 简洁精确，无废话
- 中文源用中文写，英文源用英文写
- tags 使用小写连字符格式
- slug 用英文小写+连字符，从标题翻译/转写得到
- 只提取真正重要的实体和概念，不要过度拆分
- **矛盾检测**：如果新源的事实、数据、结论与已有页面不一致，务必填入 contradictions 数组；没有矛盾就返回空数组 []"""


REVISE_PAGE_SYSTEM_PROMPT = """你是 Wiki 页面修订器。给定一个页面的当前内容和一份针对该页面的"新源材料摘要"，输出整合后的完整页面内容。

规则：
1. 输出必须是**完整的 markdown 页面内容**（不是 diff 或增量），作为新正文
2. 整合新信息：修正/扩充/删除相应段落；未受影响的段落保持原样
3. 保留所有 [[slug]] 引用；合理补充新引用
4. 在 ## Sources 章节追加一行：`- [[{new_source_slug}]]`（如果该章节不存在，就创建它）
5. 如果新源与旧页论断冲突：
   - 页面中对应段落改为两方并陈，注明时间/出处
   - 同时把冲突记录到输出的 contradictions 数组
6. 不要堆砌重复内容；不要把新摘要原封不动粘贴，而要把信息**编织进**既有结构

输出 JSON：
{
  "revised_content": "完整的 markdown 页面正文",
  "contradictions": [
    {"old_claim": "...", "new_claim": "...", "resolution": "..."}
  ]
}"""


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

    def build_contradiction_block(
        self,
        conflicts: list[dict],
        new_source_slug: str,
        date_str: str,
    ) -> str:
        """Render a markdown blockquote summarizing detected contradictions.
        Prepended to the affected page so readers see unresolved conflicts up front."""
        if not conflicts:
            return ""
        lines = [f"> **⚠️ 矛盾记录 · {date_str}** · 新源 [[{new_source_slug}]]", ">"]
        for c in conflicts:
            old = (c.get("old_claim") or "").strip()
            new = (c.get("new_claim") or "").strip()
            res = (c.get("resolution") or c.get("resolution_hint") or "").strip()
            if not old and not new:
                continue
            if old:
                lines.append(f"> - **原论断**: {old}")
            if new:
                lines.append(f"> - **新论断**: {new}")
            if res:
                lines.append(f"> - **处置建议**: {res}")
            lines.append(">")
        if lines[-1] == ">":
            lines.pop()
        return "\n".join(lines)

    async def _revise_page(
        self,
        old_content: str,
        update_hint: str,
        new_source_slug: str,
    ) -> dict:
        """Second-pass LLM call: rewrite the existing page content integrating the new source.
        Returns {"revised_content": str, "contradictions": [...]}."""
        user_msg = (
            f"## 当前页面内容\n\n{old_content or '(空页面)'}\n\n"
            f"---\n\n## 新源摘要（来自 [[{new_source_slug}]]，针对本页面的补充/修正）\n\n{update_hint}"
        )
        try:
            data = await llm_client.chat_json(user_msg, system_message=REVISE_PAGE_SYSTEM_PROMPT)
            if not isinstance(data, dict) or "revised_content" not in data:
                raise ValueError("Revise output missing revised_content")
            return {
                "revised_content": data["revised_content"],
                "contradictions": data.get("contradictions") or [],
            }
        except Exception as e:
            logger.warning("Page revise failed, falling back to append: %s", e)
            # Fallback: degrade to the old append behavior so an LLM hiccup
            # doesn't kill the whole ingest.
            return {
                "revised_content": (old_content or "") + "\n\n" + update_hint,
                "contradictions": [],
            }

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

    async def _rebuild_chunks_for_pages(self, pages, db_session) -> None:
        """Delete stale chunks for the given pages, re-chunk, embed, and persist."""
        from sqlalchemy import delete
        from app.models import WikiChunk

        if not pages:
            return

        page_ids = [p.id for p in pages]
        await db_session.execute(delete(WikiChunk).where(WikiChunk.page_id.in_(page_ids)))
        await db_session.flush()

        all_chunks: list[tuple] = []  # (WikiChunk, embed_text)
        for page in pages:
            chunks = chunk_markdown(page.content or "", title=page.title)
            for ch in chunks:
                wc = WikiChunk(
                    page_id=page.id,
                    position=ch.position,
                    heading_path=ch.heading_path,
                    content=ch.content,
                    char_count=ch.char_count,
                )
                db_session.add(wc)
                embed_text = f"{page.title}\n{ch.content}"
                all_chunks.append((wc, embed_text))

        if not all_chunks:
            return
        await db_session.flush()

        # Embed in batches of 20
        batch_size = 20
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i : i + batch_size]
            texts = [t for _, t in batch]
            vectors = await embedding_service.embed_batch(texts)
            for (wc, _), vec in zip(batch, vectors):
                if vec:
                    wc.embedding = vec

    async def process_source(self, source_id: str, content_text: str, db_session):
        from sqlalchemy import select, delete
        from app.models import WikiPage, RawSource, WikiLink

        context = await self.build_context(db_session)
        user_message = f"{context}\n\n---\n\n## 待处理的新源材料：\n\n{content_text[:30000]}"
        data = await llm_client.chat_json(user_message, system_message=INGEST_SYSTEM_PROMPT)
        pages = self.parse_llm_output(data)

        # First identify the new source page's slug — needed as the "new source" ref
        # when revising existing entity/concept pages.
        new_source_slug = ""
        for p in pages:
            if p["type"] == "source":
                new_source_slug = p["slug"]
                break

        created_pages = []
        touched_pages_by_slug: dict[str, WikiPage] = {}

        def mark_touched(page: WikiPage) -> None:
            touched_pages_by_slug[page.slug] = page

        # Collect pages that need a second-pass revise so we can run them in parallel.
        pages_to_revise: list[tuple[WikiPage, str]] = []  # (existing_page, update_hint)

        for page_data in pages:
            page_data.pop("action", None)  # action is advisory; we decide by slug existence
            existing = await db_session.execute(select(WikiPage).where(WikiPage.slug == page_data["slug"]))
            existing_page = existing.scalar_one_or_none()
            if existing_page:
                if page_data["type"] == "source":
                    # Full replace for source pages (reingest semantics)
                    existing_page.content = page_data["content"]
                    existing_page.title = page_data["title"]
                    existing_page.frontmatter = page_data.get("frontmatter", existing_page.frontmatter)
                    existing_page.source_id = source_id
                    existing_page.updated_at = datetime.now(timezone.utc)
                    created_pages.append(existing_page)
                    mark_touched(existing_page)
                else:
                    # Queue for a 2nd-pass revise (rewrite, not append)
                    update_hint = page_data.get("content", "") or ""
                    pages_to_revise.append((existing_page, update_hint))
                continue
            # New pages generated from this ingest are always attributed to this source.
            page_data["source_id"] = source_id
            new_page = WikiPage(**page_data)
            db_session.add(new_page)
            created_pages.append(new_page)
            mark_touched(new_page)

        # Second-pass revise calls run in parallel (each is one extra LLM roundtrip)
        if pages_to_revise and new_source_slug:
            revise_results = await asyncio.gather(
                *(self._revise_page(p.content or "", hint, new_source_slug) for p, hint in pages_to_revise),
                return_exceptions=False,
            )
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for (existing_page, _), result in zip(pages_to_revise, revise_results):
                existing_page.content = result["revised_content"]
                conflicts = result.get("contradictions") or []
                if conflicts:
                    block = self.build_contradiction_block(conflicts, new_source_slug, today)
                    if block:
                        existing_page.content = block + "\n\n" + (existing_page.content or "")
                existing_page.updated_at = datetime.now(timezone.utc)
                created_pages.append(existing_page)
                mark_touched(existing_page)

        # Apply top-level contradictions from pass-1 (may target pages not in pages_to_revise —
        # e.g. the LLM noticed a conflict but didn't request a full rewrite of that page).
        top_level_conflicts = data.get("contradictions") or []
        if top_level_conflicts and new_source_slug:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            by_slug: dict[str, list[dict]] = {}
            for c in top_level_conflicts:
                slug = (c.get("page_slug") or "").strip()
                if slug:
                    by_slug.setdefault(slug, []).append(c)
            for slug, conflicts in by_slug.items():
                # Skip if this page was already handled via revise (its ⚠️ block is already prepended)
                if any(p.slug == slug for p, _ in pages_to_revise):
                    continue
                target = await db_session.execute(select(WikiPage).where(WikiPage.slug == slug))
                target_page = target.scalar_one_or_none()
                if not target_page:
                    continue
                block = self.build_contradiction_block(conflicts, new_source_slug, today)
                if block:
                    target_page.content = block + "\n\n" + (target_page.content or "")
                    target_page.updated_at = datetime.now(timezone.utc)
                    if target_page not in created_pages:
                        created_pages.append(target_page)
                    mark_touched(target_page)

        # Apply cross-reference content updates before re-embedding/re-chunking so
        # retrieval and link graph stay consistent with final committed content.
        for xref in data.get("cross_references", []):
            existing = await db_session.execute(select(WikiPage).where(WikiPage.slug == xref["page_slug"]))
            existing_page = existing.scalar_one_or_none()
            if existing_page and xref.get("add_content"):
                existing_page.content += "\n\n" + xref["add_content"]
                existing_page.updated_at = datetime.now(timezone.utc)
                mark_touched(existing_page)

        await db_session.flush()

        touched_pages = list(touched_pages_by_slug.values())

        # Generate embeddings for all created pages (page-level, kept for backward-compat search)
        texts_to_embed = []
        for page in touched_pages:
            embed_text = f"{page.title}\n{(page.content or '')[:4000]}"
            texts_to_embed.append(embed_text)
        if texts_to_embed:
            vectors = await embedding_service.embed_batch(texts_to_embed)
            for page, vec in zip(touched_pages, vectors):
                if vec:
                    page.embedding = vec

        # Chunk each page and persist + embed chunks (fine-grained retrieval)
        await self._rebuild_chunks_for_pages(touched_pages, db_session)

        # Rebuild outgoing wikilinks for every changed page to avoid stale or duplicate edges.
        if touched_pages:
            page_ids = [p.id for p in touched_pages]
            await db_session.execute(delete(WikiLink).where(WikiLink.from_page_id.in_(page_ids)))

        for page in touched_pages:
            links = sorted(set(self.extract_wikilinks(page.content)))
            for link_slug in links:
                target = await db_session.execute(select(WikiPage.id).where(WikiPage.slug == link_slug))
                target_id = target.scalar_one_or_none()
                wl = WikiLink(from_page_id=page.id, to_page_id=target_id, to_slug=link_slug)
                db_session.add(wl)

        source = await db_session.get(RawSource, source_id)
        source.status = "done"
        source.processed_at = datetime.now(timezone.utc)
        await db_session.commit()
        return created_pages


ingest_service = IngestService()

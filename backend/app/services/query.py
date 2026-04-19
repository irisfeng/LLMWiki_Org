import logging
import time
from collections import defaultdict
import jieba
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models import WikiPage, WikiChunk
from app.services.llm import llm_client
from app.services.embedding import embedding_service

logger = logging.getLogger(__name__)

QUERY_SYSTEM_PROMPT = """你是一个知识库问答助手。你根据提供的 Wiki 页面片段回答问题。

规则：
1. 只根据提供的 Wiki 片段回答，不使用外部知识
2. 片段以 [1]、[2]、[3]… 编号。在引用来源时，用 [1][2] 这样的数字角标，紧跟在被引用的关键短语之后
3. 同一句话可以引用多个来源，写作 [1][3]；不要使用 [[slug]] 或其他形式
4. 如果提供的片段不足以回答，明确说明"知识库中暂无相关信息"
5. 回答简洁直接，避免废话
6. 如果不同片段存在矛盾，指出矛盾并呈现各方说法，各自带上角标
7. 用中文回答（除非用户用英文提问）"""

TYPE_HINTS = {
    "entity": ["谁", "人物", "团队", "公司", "组织", "作者", "创始人", "开发者", "who"],
    "concept": ["什么是", "定义", "概念", "原理", "机制", "how does", "what is", "explain"],
    "source": ["论文", "文章", "报告", "书", "paper", "article", "report"],
}

STOP_WORDS = {"的", "了", "是", "在", "有", "和", "与", "对", "这", "那", "也",
              "就", "都", "而", "及", "着", "或", "中", "为", "被", "把", "从",
              "到", "说", "要", "会", "能", "上", "下", "不", "吗", "呢", "吧",
              "哪些", "什么", "怎么", "如何", "哪个", "哪里", "多少", "为什么"}

MAX_CONTEXT_CHARS = 8000
CHUNK_TOP_K = 24
CHUNK_KW_TOP_K = 20
PAGE_TOP_K = 8
CHUNKS_PER_PAGE = 3

# Answer-mode presets mapped to qwen3.6-plus thinking controls.
# concise : fast reply, no thinking — good for fact lookups
# cited   : default — short thinking budget for robust citations
# deep    : exploratory / analytical — larger budget, warmer sampling
MODE_PRESETS: dict[str, dict] = {
    "concise": {"enable_thinking": False, "thinking_budget": None, "temperature": 0.3},
    "cited":   {"enable_thinking": True,  "thinking_budget": 1500, "temperature": 0.3},
    "deep":    {"enable_thinking": True,  "thinking_budget": 8000, "temperature": 0.5},
}
DEFAULT_MODE = "cited"


def tokenize_chinese(text: str) -> list[str]:
    words = jieba.cut(text)
    return [w.strip() for w in words if w.strip() and len(w.strip()) > 1 and w.strip() not in STOP_WORDS]


def detect_type_hint(question: str) -> str | None:
    for page_type, keywords in TYPE_HINTS.items():
        for kw in keywords:
            if kw in question.lower():
                return page_type
    return None


class QueryService:
    """Chunk-first hybrid retrieval.

    1. Vector-search chunks (semantic).
    2. Keyword-scan chunks (jieba tokens).
    3. Aggregate chunk scores per page -> rank pages.
    4. Build context from top chunks per page.
    """

    async def retrieve(
        self, question: str, db: AsyncSession
    ) -> tuple[list[WikiPage], dict[str, list[WikiChunk]], dict[str, float]]:
        chunk_scores: dict[str, float] = defaultdict(float)
        chunk_by_id: dict[str, WikiChunk] = {}

        query_vec = await embedding_service.embed(question)
        if query_vec:
            vec_sql = (
                select(WikiChunk, WikiChunk.embedding.cosine_distance(query_vec).label("distance"))
                .where(WikiChunk.embedding.isnot(None))
                .order_by("distance")
                .limit(CHUNK_TOP_K)
            )
            vec_result = await db.execute(vec_sql)
            for row in vec_result:
                chunk: WikiChunk = row[0]
                similarity = 1.0 - float(row[1])
                key = str(chunk.id)
                chunk_by_id[key] = chunk
                chunk_scores[key] += similarity * 0.7

        keywords = tokenize_chinese(question)
        if keywords:
            conditions = [WikiChunk.content.ilike(f"%{kw}%") for kw in keywords[:8]]
            kw_sql = select(WikiChunk).where(or_(*conditions)).limit(CHUNK_KW_TOP_K)
            kw_result = await db.execute(kw_sql)
            for chunk in kw_result.scalars().all():
                key = str(chunk.id)
                chunk_by_id[key] = chunk
                hits = sum(1 for kw in keywords if kw.lower() in (chunk.content or "").lower())
                chunk_scores[key] += hits * 0.08

        # Fallback to page-level search if no chunks exist yet
        if not chunk_by_id:
            pages = await self._legacy_page_search(question, db)
            return pages, {}, {}

        # Aggregate per page
        page_scores: dict[str, float] = defaultdict(float)
        page_chunks: dict[str, list[tuple[float, WikiChunk]]] = defaultdict(list)
        for key, score in chunk_scores.items():
            chunk = chunk_by_id[key]
            pid = str(chunk.page_id)
            page_scores[pid] += score
            page_chunks[pid].append((score, chunk))

        page_ids_ranked = sorted(page_scores.keys(), key=lambda p: page_scores[p], reverse=True)[:PAGE_TOP_K]
        if not page_ids_ranked:
            return [], {}, {}

        pages_result = await db.execute(select(WikiPage).where(WikiPage.id.in_(page_ids_ranked)))
        pages_by_id = {str(p.id): p for p in pages_result.scalars().all()}
        pages = [pages_by_id[pid] for pid in page_ids_ranked if pid in pages_by_id]

        type_hint = detect_type_hint(question)
        if type_hint:
            pages.sort(key=lambda p: (0 if p.type == type_hint else 1, -page_scores[str(p.id)]))

        best_chunks: dict[str, list[WikiChunk]] = {}
        for pid in page_ids_ranked:
            if pid not in pages_by_id:
                continue
            ranked = sorted(page_chunks[pid], key=lambda t: t[0], reverse=True)
            best_chunks[pages_by_id[pid].slug] = [c for _, c in ranked[:CHUNKS_PER_PAGE]]

        return pages, best_chunks, dict(page_scores)

    async def _legacy_page_search(self, question: str, db: AsyncSession) -> list[WikiPage]:
        """Used only when no chunks exist yet (pre-backfill)."""
        keywords = tokenize_chinese(question)
        scored: dict[str, tuple[float, WikiPage]] = {}
        if keywords:
            conditions = []
            for kw in keywords[:8]:
                conditions.append(WikiPage.title.ilike(f"%{kw}%"))
                conditions.append(WikiPage.content.ilike(f"%{kw}%"))
            result = await db.execute(select(WikiPage).where(or_(*conditions)).limit(PAGE_TOP_K))
            for p in result.scalars().all():
                scored[p.slug] = (1.0, p)
        if len(scored) < 3:
            fallback = await db.execute(select(WikiPage).order_by(WikiPage.updated_at.desc()).limit(PAGE_TOP_K))
            for p in fallback.scalars().all():
                scored.setdefault(p.slug, (0.1, p))
        return [p for _, p in sorted(scored.values(), key=lambda x: x[0], reverse=True)][:PAGE_TOP_K]

    async def find_relevant_pages(self, question: str, db: AsyncSession, top_k: int = 8) -> list[WikiPage]:
        pages, _, _ = await self.retrieve(question, db)
        return pages[:top_k]

    def build_context(self, pages: list[WikiPage], chunks_by_slug: dict[str, list[WikiChunk]]) -> str:
        """Build numbered context. Each page is tagged [N] so the LLM can cite it as [N]."""
        parts: list[str] = []
        budget = MAX_CONTEXT_CHARS
        for idx, page in enumerate(pages, start=1):
            chunks = chunks_by_slug.get(page.slug) or []
            header = f"---\n[{idx}] [{page.type}] {page.title} (slug: {page.slug})\n\n"
            parts.append(header)
            budget -= len(header)
            if chunks:
                for ch in chunks:
                    piece = (ch.content or "").strip() + "\n\n"
                    if budget - len(piece) < 0:
                        piece = piece[: max(0, budget)]
                    parts.append(piece)
                    budget -= len(piece)
                    if budget <= 0:
                        break
            else:
                content = (page.content or "")[: max(300, budget)]
                parts.append(content + "\n")
                budget -= len(content)
            if budget <= 0:
                break
        return "".join(parts)

    def build_sources_payload(
        self,
        pages: list[WikiPage],
        chunks_by_slug: dict[str, list[WikiChunk]],
        page_scores: dict[str, float] | None = None,
    ) -> list[dict]:
        """Build the sources array surfaced to the frontend as numbered citations."""
        payload: list[dict] = []
        for idx, page in enumerate(pages, start=1):
            chunks = chunks_by_slug.get(page.slug) or []
            excerpt = ""
            heading = ""
            if chunks:
                excerpt = (chunks[0].content or "").strip()
                hp = chunks[0].heading_path or []
                if isinstance(hp, list) and hp:
                    heading = " › ".join(str(h) for h in hp if h)
            else:
                excerpt = (page.content or "").strip()
            if len(excerpt) > 220:
                excerpt = excerpt[:220].rstrip() + "…"
            score = 0.0
            if page_scores:
                score = float(page_scores.get(str(page.id), 0.0))
            payload.append({
                "index": idx,
                "slug": page.slug,
                "title": page.title,
                "type": page.type,
                "score": round(score, 3),
                "excerpt": excerpt,
                "heading": heading,
            })
        return payload

    def build_context_from_pages(self, pages: list[WikiPage]) -> str:
        return self.build_context(pages, {})

    async def _summarize_history(self, history: list[dict]) -> str:
        """Summarize older conversation history into a brief context string."""
        conversation_text = "\n".join(
            f"{m['role']}: {m['content'][:200]}" for m in history
        )
        summary_prompt = (
            "将以下对话历史浓缩为一句话摘要，保留关键主题和结论，不超过100字：\n\n"
            f"{conversation_text}"
        )
        result = await llm_client.chat(
            user_message=summary_prompt,
            system_message="你是一个对话摘要助手。只输出摘要，不要解释。",
        )
        return result.strip()

    async def answer(
        self,
        question: str,
        db: AsyncSession,
        history: list[dict] = None,
        mode: str = DEFAULT_MODE,
    ):
        """Stream a chat answer. Yields:
          - {"stage": {name, status, ms, ...}} pipeline events (retrieve / think / generate)
          - {"reasoning": "..."}                thinking-chain tokens
          - "token"                             regular content tokens
          - {"__meta__": {"sources": [...]}}    final metadata
        """
        preset = MODE_PRESETS.get(mode, MODE_PRESETS[DEFAULT_MODE])

        t0 = time.perf_counter()
        yield {"stage": {"name": "retrieve", "status": "start"}}
        pages, chunks_by_slug, page_scores = await self.retrieve(question, db)
        context = self.build_context(pages, chunks_by_slug)
        sources = self.build_sources_payload(pages, chunks_by_slug, page_scores)
        retrieve_ms = int((time.perf_counter() - t0) * 1000)
        yield {"stage": {
            "name": "retrieve",
            "status": "done",
            "ms": retrieve_ms,
            "count": len(pages),
        }}

        messages = []
        if history and len(history) > 0:
            if len(history) > 8:
                older = history[:-6]
                recent = history[-6:]
                try:
                    summary = await self._summarize_history(older)
                    messages.append({
                        "role": "system",
                        "content": f"之前的对话摘要：{summary}",
                    })
                except Exception:
                    logger.warning("History summarization failed, using recent history only")
                messages.extend(recent)
            else:
                messages.extend(history)
        messages.append({
            "role": "user",
            "content": f"以下是知识库中的相关片段：\n\n{context}\n\n---\n\n用户问题：{question}"
        })

        # If thinking is enabled, announce the think stage so the UI can show it.
        # We can't time thinking precisely in advance, but we emit start markers
        # and flip to "generate" once the first content token arrives.
        thinking_enabled = preset["enable_thinking"]
        if thinking_enabled:
            yield {"stage": {"name": "think", "status": "start"}}
        else:
            yield {"stage": {"name": "generate", "status": "start"}}

        generate_started = not thinking_enabled
        think_t0 = time.perf_counter()

        async for chunk in llm_client.chat_stream(
            messages=messages,
            system_message=QUERY_SYSTEM_PROMPT,
            temperature=preset["temperature"],
            enable_thinking=preset["enable_thinking"],
            thinking_budget=preset["thinking_budget"],
        ):
            if isinstance(chunk, dict) and "reasoning" in chunk:
                yield {"reasoning": chunk["reasoning"]}
            elif isinstance(chunk, str):
                if not generate_started:
                    generate_started = True
                    think_ms = int((time.perf_counter() - think_t0) * 1000)
                    yield {"stage": {"name": "think", "status": "done", "ms": think_ms}}
                    yield {"stage": {"name": "generate", "status": "start"}}
                yield chunk

        yield {"__meta__": {"sources": sources, "mode": mode}}


query_service = QueryService()

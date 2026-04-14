import logging
import jieba
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models import WikiPage
from app.services.llm import llm_client
from app.services.embedding import embedding_service

logger = logging.getLogger(__name__)

QUERY_SYSTEM_PROMPT = """你是一个知识库问答助手。你根据提供的 Wiki 页面内容回答问题。

规则：
1. 只根据提供的 Wiki 页面内容回答，不使用外部知识
2. 用 [[页面slug]] 格式引用来源页面
3. 如果提供的页面不足以回答，明确说明"知识库中暂无相关信息"
4. 回答简洁直接，避免废话
5. 如果不同页面存在矛盾，指出矛盾并呈现各方说法
6. 用中文回答（除非用户用英文提问）"""

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
    async def find_relevant_pages(self, question: str, db: AsyncSession, top_k: int = 8) -> list[WikiPage]:
        scored: dict[str, tuple[float, WikiPage]] = {}

        # Branch 1: Vector similarity search
        query_vec = await embedding_service.embed(question)
        if query_vec:
            vec_sql = (
                select(WikiPage, WikiPage.embedding.cosine_distance(query_vec).label("distance"))
                .where(WikiPage.embedding.isnot(None))
                .order_by("distance")
                .limit(top_k)
            )
            vec_result = await db.execute(vec_sql)
            for row in vec_result:
                page = row[0]
                distance = row[1]
                similarity = 1.0 - distance
                scored[page.slug] = (similarity * 0.7, page)

        # Branch 2: Keyword search with jieba
        keywords = tokenize_chinese(question)
        if keywords:
            conditions = []
            for kw in keywords[:8]:
                conditions.append(WikiPage.title.ilike(f"%{kw}%"))
                conditions.append(WikiPage.content.ilike(f"%{kw}%"))
            kw_result = await db.execute(
                select(WikiPage).where(or_(*conditions)).limit(top_k)
            )
            for page in kw_result.scalars().all():
                title_hits = sum(1 for kw in keywords if kw.lower() in (page.title or "").lower())
                content_hits = sum(1 for kw in keywords if kw.lower() in (page.content or "")[:2000].lower())
                kw_score = (title_hits * 0.15 + content_hits * 0.05)
                if page.slug in scored:
                    old_score, _ = scored[page.slug]
                    scored[page.slug] = (old_score + kw_score, page)
                else:
                    scored[page.slug] = (kw_score, page)

        # Type boost
        type_hint = detect_type_hint(question)
        if type_hint:
            for slug, (score, page) in scored.items():
                if page.type == type_hint:
                    scored[slug] = (score + 0.1, page)

        # Sort by score
        ranked = sorted(scored.values(), key=lambda x: x[0], reverse=True)
        pages = [page for _, page in ranked[:top_k]]

        # Fallback
        if len(pages) < 3:
            fallback_query = select(WikiPage).order_by(WikiPage.updated_at.desc()).limit(5)
            if type_hint:
                fallback_query = select(WikiPage).where(
                    WikiPage.type == type_hint
                ).order_by(WikiPage.updated_at.desc()).limit(5)
            fallback_result = await db.execute(fallback_query)
            for p in fallback_result.scalars().all():
                if p.slug not in {page.slug for page in pages}:
                    pages.append(p)
                    if len(pages) >= top_k:
                        break

        return pages

    def build_context_from_pages(self, pages: list[WikiPage]) -> str:
        parts = []
        budget = MAX_CONTEXT_CHARS
        for page in pages:
            header = f"---\n## [{page.type}] {page.title} (slug: {page.slug})\n\n"
            max_content = max(300, budget - len(header))
            content = page.content[:max_content] if page.content else ""
            entry = header + content + "\n"
            parts.append(entry)
            budget -= len(entry)
            if budget <= 0:
                break
        return "\n".join(parts)

    async def answer(self, question: str, db: AsyncSession, history: list[dict] = None):
        pages = await self.find_relevant_pages(question, db)
        context = self.build_context_from_pages(pages)

        messages = []
        if history:
            messages.extend(history[-6:])
        messages.append({
            "role": "user",
            "content": f"以下是知识库中的相关页面：\n\n{context}\n\n---\n\n用户问题：{question}"
        })

        referenced_slugs = [p.slug for p in pages]

        async for chunk in llm_client.chat_stream(messages=messages, system_message=QUERY_SYSTEM_PROMPT):
            yield chunk

        yield {"__meta__": {"referenced_pages": referenced_slugs}}


query_service = QueryService()

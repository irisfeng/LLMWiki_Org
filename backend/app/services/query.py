from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models import WikiPage
from app.services.llm import llm_client

QUERY_SYSTEM_PROMPT = """你是一个知识库问答助手。你根据提供的 Wiki 页面内容回答问题。

规则：
1. 只根据提供的 Wiki 页面内容回答，不使用外部知识
2. 用 [[页面slug]] 格式引用来源页面
3. 如果提供的页面不足以回答，明确说明"知识库中暂无相关信息"
4. 回答简洁直接，避免废话
5. 如果不同页面存在矛盾，指出矛盾并呈现各方说法
6. 用中文回答（除非用户用英文提问）"""


class QueryService:
    async def find_relevant_pages(self, question: str, db: AsyncSession, top_k: int = 10) -> list[WikiPage]:
        keywords = [w for w in question.replace("？", " ").replace("?", " ").split() if len(w) > 1]
        if not keywords:
            result = await db.execute(select(WikiPage).order_by(WikiPage.updated_at.desc()).limit(top_k))
            return list(result.scalars().all())

        conditions = []
        for kw in keywords[:5]:
            conditions.append(WikiPage.title.ilike(f"%{kw}%"))
            conditions.append(WikiPage.content.ilike(f"%{kw}%"))

        result = await db.execute(select(WikiPage).where(or_(*conditions)).limit(top_k))
        pages = list(result.scalars().all())

        if len(pages) < 3:
            result2 = await db.execute(select(WikiPage).order_by(WikiPage.updated_at.desc()).limit(5))
            for p in result2.scalars().all():
                if p not in pages:
                    pages.append(p)
                    if len(pages) >= top_k:
                        break
        return pages

    def build_context_from_pages(self, pages: list[WikiPage]) -> str:
        parts = []
        for page in pages:
            parts.append(f"---\n## [{page.type}] {page.title} (slug: {page.slug})\n\n{page.content}\n")
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

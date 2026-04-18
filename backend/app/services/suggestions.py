"""Generate and cache content-aware chat bubble suggestions.

Flow:
1. Worker finishes ingest → calls refresh_suggestions(db).
2. LLM is given titles + short excerpts of the latest pages and asked for
   10 natural-sounding questions an operator would want to ask.
3. Cache table is replaced atomically so readers never see a partial state.
4. API GET /wiki/suggestions?limit=3 random-samples from the cache.

When the cache is empty (fresh install or LLM failure), the endpoint
returns a hardcoded fallback so the UI is never blank.
"""
from __future__ import annotations

import json
import logging
from typing import Iterable

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatSuggestion, WikiPage
from app.services.llm import llm_client

logger = logging.getLogger(__name__)


FALLBACK_SUGGESTIONS = [
    "最近新增了哪些知识？",
    "帮我总结团队的关键讨论",
    "有哪些待跟进的事项？",
]


_SYSTEM_PROMPT = """你是一个团队知识库的提问建议助手。根据下方最近的知识页面，
生成 10 个团队成员可能会问的、具体且自然的中文问题。

要求：
1. 每个问题 6~20 个汉字，简洁自然
2. 紧扣实际内容（涉及页面标题或其中的关键概念）
3. 多样化：有的问事实、有的问关系、有的问行动
4. 不要包含"请问"、"你好"等客套话
5. 严格按 JSON 返回：{"questions": ["问题1", "问题2", ...]}
"""


async def _collect_page_snippets(db: AsyncSession, limit: int = 12) -> list[dict]:
    q = select(WikiPage).order_by(WikiPage.updated_at.desc()).limit(limit)
    pages = (await db.execute(q)).scalars().all()
    return [
        {
            "title": p.title,
            "type": p.type,
            "excerpt": (p.content or "")[:280],
        }
        for p in pages
    ]


async def refresh_suggestions(db: AsyncSession, target_count: int = 10) -> int:
    """Regenerate the cache. Returns how many suggestions were written.
    Safe to call repeatedly; failures leave the existing cache in place."""
    snippets = await _collect_page_snippets(db)
    if not snippets:
        return 0

    user_message = "最近知识页面（JSON）:\n" + json.dumps(snippets, ensure_ascii=False)
    try:
        data = await llm_client.chat_json(user_message, system_message=_SYSTEM_PROMPT, temperature=0.7)
    except Exception as e:
        logger.error("suggestion LLM call failed: %s", e)
        return 0

    questions: Iterable = data.get("questions") if isinstance(data, dict) else None
    if not questions:
        return 0

    cleaned: list[str] = []
    for q in questions:
        if not isinstance(q, str):
            continue
        q = q.strip().strip('"').strip("'")
        if 4 <= len(q) <= 60:
            cleaned.append(q)
    cleaned = cleaned[:target_count]
    if not cleaned:
        return 0

    # Replace cache atomically.
    await db.execute(delete(ChatSuggestion))
    for q in cleaned:
        db.add(ChatSuggestion(question=q))
    await db.commit()
    logger.info("suggestion cache refreshed with %d entries", len(cleaned))
    return len(cleaned)


async def pick_suggestions(db: AsyncSession, limit: int = 3) -> list[str]:
    """Return up to `limit` random cached suggestions, or fallbacks."""
    from sqlalchemy.sql import func as sa_func

    q = select(ChatSuggestion.question).order_by(sa_func.random()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    if rows:
        return list(rows)
    return FALLBACK_SUGGESTIONS[:limit]

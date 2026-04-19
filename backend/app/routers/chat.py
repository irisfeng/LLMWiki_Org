import json
import re
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models import ChatSession, ChatMessage, WikiPage
from app.schemas import ChatMessageCreate, ChatMessageResponse
from app.services.query import query_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/sessions")
async def create_session(user_name: str = "", db: AsyncSession = Depends(get_db)):
    session = ChatSession(user_name=user_name)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"session_id": str(session.id)}


@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List recent chat sessions with first user question as title and message count.
    Used by the chat 历史 drawer. Skips sessions with no messages yet.
    """
    sessions_result = await db.execute(
        select(ChatSession).order_by(ChatSession.created_at.desc()).limit(100)
    )
    sessions = list(sessions_result.scalars().all())
    if not sessions:
        return []

    ids = [s.id for s in sessions]

    msgs_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id.in_(ids))
        .where(ChatMessage.role == "user")
        .order_by(ChatMessage.session_id, ChatMessage.created_at)
    )
    first_user: dict[str, str] = {}
    for m in msgs_result.scalars().all():
        sid = str(m.session_id)
        if sid not in first_user:
            first_user[sid] = m.content

    count_result = await db.execute(
        select(ChatMessage.session_id, func.count())
        .where(ChatMessage.session_id.in_(ids))
        .group_by(ChatMessage.session_id)
    )
    counts = {str(sid): c for sid, c in count_result.all()}

    out = []
    for s in sessions:
        sid = str(s.id)
        if sid not in first_user:
            continue
        title = first_user[sid].strip().replace("\n", " ")
        if len(title) > 60:
            title = title[:60] + "…"
        out.append({
            "id": sid,
            "user_name": s.user_name or "",
            "created_at": s.created_at.isoformat(),
            "title": title,
            "message_count": counts.get(sid, 0),
        })
    return out


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a chat session and all its messages."""
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    # Delete all messages first
    await db.execute(
        delete(ChatMessage).where(ChatMessage.session_id == session_id)
    )
    await db.delete(session)
    await db.commit()
    return {"message": "已删除"}


@router.post("/messages")
async def send_message(body: ChatMessageCreate, db: AsyncSession = Depends(get_db)):
    if body.session_id:
        session_id = body.session_id
    else:
        session = ChatSession(user_name=body.user_name)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        session_id = session.id

    user_msg = ChatMessage(session_id=session_id, role="user", content=body.content)
    db.add(user_msg)
    await db.commit()

    history_result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    history_msgs = history_result.scalars().all()
    history = [{"role": m.role, "content": m.content} for m in history_msgs[:-1]]

    async def event_generator():
        full_response = ""
        sources: list[dict] = []

        try:
            async for chunk in query_service.answer(body.content, db, history):
                if isinstance(chunk, dict) and "__meta__" in chunk:
                    sources = chunk["__meta__"].get("sources", []) or []
                else:
                    full_response += chunk
                    yield {"event": "message", "data": chunk}

            assistant_msg = ChatMessage(
                session_id=session_id, role="assistant",
                content=full_response, referenced_pages=sources,
            )
            db.add(assistant_msg)
            await db.commit()
            yield {
                "event": "done",
                "data": json.dumps({
                    "session_id": str(session_id),
                    "message_id": str(assistant_msg.id),
                    "sources": sources,
                }),
            }
        except Exception as e:
            logger.exception("Chat stream error: %s", e)
            # Don't leak internal error details to the client
            yield {
                "event": "error",
                "data": json.dumps({"error": "服务暂时不可用，请稍后重试"}),
            }

    return EventSourceResponse(event_generator())


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_session_messages(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    return result.scalars().all()


def _slugify_question(q: str) -> str:
    """Build a URL-friendly slug base from a question.
    Keeps latin+digits, strips CJK/punctuation; falls back to empty if nothing remains."""
    ascii_only = re.sub(r"[^A-Za-z0-9\s-]", " ", q)
    tokens = [t.lower() for t in re.split(r"\s+", ascii_only) if t]
    if not tokens:
        return ""
    return "-".join(tokens[:6])[:60].strip("-")


async def _unique_slug(base: str, db: AsyncSession) -> str:
    """Ensure slug uniqueness by suffixing -2, -3... as needed."""
    candidate = base
    n = 1
    while True:
        existing = await db.execute(select(WikiPage.id).where(WikiPage.slug == candidate))
        if existing.scalar_one_or_none() is None:
            return candidate
        n += 1
        candidate = f"{base}-{n}"


@router.post("/messages/{message_id}/save-as-analysis")
async def save_message_as_analysis(
    message_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Persist an assistant message (and its preceding user question) as a WikiPage
    of type=analysis. Returns the new page's slug so the frontend can link to it."""
    msg = await db.get(ChatMessage, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="消息不存在")
    if msg.role != "assistant":
        raise HTTPException(status_code=400, detail="只能保存 AI 回答")

    # Find the user question immediately preceding this assistant reply.
    prev_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == msg.session_id)
        .where(ChatMessage.role == "user")
        .where(ChatMessage.created_at < msg.created_at)
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    )
    user_msg = prev_result.scalar_one_or_none()
    question_text = (user_msg.content if user_msg else "").strip() or "未命名分析"

    title = question_text.replace("\n", " ").strip()
    if len(title) > 80:
        title = title[:80] + "…"

    base = _slugify_question(question_text)
    if not base:
        base = "analysis-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    else:
        base = f"analysis-{base}"
    slug = await _unique_slug(base, db)

    # Build sources section from structured referenced_pages.
    sources_md = ""
    refs = msg.referenced_pages or []
    if refs and isinstance(refs[0], dict):
        lines = ["\n\n## 引用来源\n"]
        for s in refs:
            idx = s.get("index", "?")
            stitle = s.get("title", s.get("slug", "未命名"))
            sslug = s.get("slug", "")
            stype = s.get("type", "")
            heading = s.get("heading", "")
            suffix = f" · {heading}" if heading else ""
            lines.append(f"- [{idx}] [[{sslug}]] **{stitle}** `{stype}`{suffix}")
        sources_md = "\n".join(lines)

    content_md = (
        f"# {title}\n\n"
        f"> 来自 AI 问答（会话 {msg.session_id}）· {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"## 问题\n\n{question_text}\n\n"
        f"## 回答\n\n{msg.content}"
        f"{sources_md}"
    )

    page = WikiPage(
        type="analysis",
        slug=slug,
        title=title,
        frontmatter={
            "source": "chat",
            "session_id": str(msg.session_id),
            "message_id": str(msg.id),
        },
        content=content_md,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)

    # Trigger async re-chunk + re-embed so the new page joins retrieval.
    try:
        from app.worker import backfill_chunks_for_page
        backfill_chunks_for_page.delay(str(page.id))
    except Exception as e:
        logger.warning("Failed to enqueue backfill for new analysis page: %s", e)

    return {"slug": slug, "title": title}

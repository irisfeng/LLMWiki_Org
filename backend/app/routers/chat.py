import json
import uuid
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models import ChatSession, ChatMessage
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
        referenced_pages = []

        try:
            async for chunk in query_service.answer(body.content, db, history):
                if isinstance(chunk, dict) and "__meta__" in chunk:
                    referenced_pages = chunk["__meta__"]["referenced_pages"]
                else:
                    full_response += chunk
                    yield {"event": "message", "data": chunk}

            assistant_msg = ChatMessage(
                session_id=session_id, role="assistant",
                content=full_response, referenced_pages=referenced_pages,
            )
            db.add(assistant_msg)
            await db.commit()
            yield {
                "event": "done",
                "data": json.dumps({
                    "session_id": str(session_id),
                    "referenced_pages": referenced_pages or [],
                }),
            }
        except Exception as e:
            logger.exception("Chat stream error: %s", e)
            yield {
                "event": "error",
                "data": json.dumps({"error": f"{type(e).__name__}: {e}"}),
            }

    return EventSourceResponse(event_generator())


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_session_messages(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    return result.scalars().all()

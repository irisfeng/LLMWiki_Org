import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models import ChatSession, ChatMessage
from app.schemas import ChatMessageCreate, ChatMessageResponse
from app.services.query import query_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/sessions")
async def create_session(user_name: str = "", db: AsyncSession = Depends(get_db)):
    session = ChatSession(user_name=user_name)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"session_id": str(session.id)}


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
        yield {"event": "done", "data": f'{{"session_id": "{session_id}", "referenced_pages": {referenced_pages}}}'}

    return EventSourceResponse(event_generator())


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_session_messages(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    return result.scalars().all()

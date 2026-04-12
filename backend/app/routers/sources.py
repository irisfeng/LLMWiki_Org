import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import RawSource
from app.schemas import SourceTextSubmit, SourceURLSubmit, SourceResponse
from app.config import settings
from app.worker import process_ingest

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.post("/upload", response_model=SourceResponse)
async def upload_file(
    file: UploadFile = File(...),
    submitted_by: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    os.makedirs(settings.raw_storage_path, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ".txt"
    file_path = os.path.join(settings.raw_storage_path, f"{file_id}{ext}")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        content_text = content.decode("utf-8")
    except UnicodeDecodeError:
        from markitdown import MarkItDown
        mid = MarkItDown()
        result = mid.convert(file_path)
        content_text = result.text_content

    source = RawSource(
        id=file_id, filename=file.filename or "upload", file_path=file_path,
        content_text=content_text, submitted_by=submitted_by, status="pending",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    process_ingest.delay(str(source.id))
    return source


@router.post("/text", response_model=SourceResponse)
async def submit_text(body: SourceTextSubmit, db: AsyncSession = Depends(get_db)):
    os.makedirs(settings.raw_storage_path, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = os.path.join(settings.raw_storage_path, f"{file_id}.md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(body.text)

    source = RawSource(
        id=file_id, filename=body.title or "text-input", file_path=file_path,
        content_text=body.text, submitted_by=body.submitted_by, status="pending",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    process_ingest.delay(str(source.id))
    return source


@router.post("/url", response_model=SourceResponse)
async def submit_url(body: SourceURLSubmit, db: AsyncSession = Depends(get_db)):
    import httpx
    from markitdown import MarkItDown

    os.makedirs(settings.raw_storage_path, exist_ok=True)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(body.url, follow_redirects=True)
        resp.raise_for_status()

    file_id = str(uuid.uuid4())
    file_path = os.path.join(settings.raw_storage_path, f"{file_id}.html")
    with open(file_path, "wb") as f:
        f.write(resp.content)

    mid = MarkItDown()
    result = mid.convert(file_path)
    content_text = result.text_content

    source = RawSource(
        id=file_id, filename=body.url, file_path=file_path,
        content_text=content_text, submitted_by=body.submitted_by, status="pending",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    process_ingest.delay(str(source.id))
    return source


@router.get("/", response_model=list[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RawSource).order_by(RawSource.created_at.desc()).limit(100))
    return result.scalars().all()

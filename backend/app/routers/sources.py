import os
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import RawSource
from app.schemas import SourceTextSubmit, SourceURLSubmit, SourceResponse
from app.config import settings
from app.worker import process_ingest

logger = logging.getLogger(__name__)

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

    # Extract text content — failures here should not block the upload
    content_text = ""
    try:
        if ext.lower() == ".pdf":
            from app.services.mineru_service import parse_pdf
            content_text = await parse_pdf(file_path)
        if not content_text:
            try:
                content_text = content.decode("utf-8")
            except UnicodeDecodeError:
                from markitdown import MarkItDown
                mid = MarkItDown()
                result = mid.convert(file_path)
                content_text = result.text_content
    except Exception as e:
        logger.error("Text extraction failed for %s: %s", file.filename, e)

    source = RawSource(
        id=file_id, filename=file.filename or "upload", file_path=file_path,
        content_text=content_text, submitted_by=submitted_by,
        status="pending" if content_text else "failed",
        error_message=None if content_text else "文本提取失败，请检查文件格式",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    if content_text:
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

    os.makedirs(settings.raw_storage_path, exist_ok=True)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(body.url, follow_redirects=True)
        resp.raise_for_status()

    file_id = str(uuid.uuid4())
    file_path = os.path.join(settings.raw_storage_path, f"{file_id}.html")
    with open(file_path, "wb") as f:
        f.write(resp.content)

    content_text = ""
    try:
        from markitdown import MarkItDown
        mid = MarkItDown()
        result = mid.convert(file_path)
        content_text = result.text_content
    except Exception as e:
        logger.error("URL content extraction failed for %s: %s", body.url, e)

    source = RawSource(
        id=file_id, filename=body.url, file_path=file_path,
        content_text=content_text, submitted_by=body.submitted_by,
        status="pending" if content_text else "failed",
        error_message=None if content_text else "网页内容提取失败",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    if content_text:
        process_ingest.delay(str(source.id))
    return source


@router.get("/", response_model=list[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RawSource).order_by(RawSource.created_at.desc()).limit(100))
    return result.scalars().all()


@router.get("/{source_id}/file")
async def download_file(source_id: str, db: AsyncSession = Depends(get_db)):
    source = await db.get(RawSource, source_id)
    if not source or not source.file_path:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not os.path.exists(source.file_path):
        raise HTTPException(status_code=404, detail="文件已被删除")
    return FileResponse(
        source.file_path,
        filename=source.filename,
        media_type="application/octet-stream",
    )


@router.post("/{source_id}/reingest")
async def reingest_source(source_id: str, db: AsyncSession = Depends(get_db)):
    source = await db.get(RawSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="源不存在")

    # Re-extract text from raw file if content_text is empty
    if not source.content_text and source.file_path and os.path.exists(source.file_path):
        ext = os.path.splitext(source.file_path)[1].lower()
        try:
            if ext == ".pdf":
                from app.services.mineru_service import parse_pdf
                source.content_text = await parse_pdf(source.file_path)
            if not source.content_text:
                with open(source.file_path, "rb") as f:
                    raw = f.read()
                try:
                    source.content_text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    from markitdown import MarkItDown
                    mid = MarkItDown()
                    result = mid.convert(source.file_path)
                    source.content_text = result.text_content
        except Exception as e:
            logger.error("Re-extraction failed for %s: %s", source.filename, e)

    if not source.content_text:
        raise HTTPException(status_code=400, detail="文本提取失败，无法重新处理")

    source.status = "pending"
    source.processed_at = None
    source.error_message = None
    await db.commit()
    process_ingest.delay(str(source.id))
    return {"message": "已重新加入处理队列"}

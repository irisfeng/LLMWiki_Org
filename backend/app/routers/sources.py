import os
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.database import get_db
from app.models import RawSource, WikiPage
from app.schemas import SourceTextSubmit, SourceURLSubmit, SourceResponse, WikiPageSummary
from app.config import settings
from app.worker import process_ingest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sources", tags=["sources"])


def _extract_pptx_text(file_path: str) -> str:
    """Extract text from .pptx/.ppt by walking shapes directly.
    Bypasses markitdown's PptxConverter which crashes on shapes with null position (Emu vs NoneType).
    """
    from pptx import Presentation
    prs = Presentation(file_path)
    parts: list[str] = []
    for i, slide in enumerate(prs.slides, 1):
        slide_parts: list[str] = []
        for shape in slide.shapes:
            try:
                if hasattr(shape, "text") and shape.text and shape.text.strip():
                    slide_parts.append(shape.text.strip())
            except Exception:
                continue
        if slide_parts:
            parts.append(f"## Slide {i}\n\n" + "\n\n".join(slide_parts))
    return "\n\n".join(parts)


def _extract_text(file_path: str, raw_bytes: bytes | None = None) -> str:
    """Unified text extraction for upload + reingest.
    PDF -> MinerU (async caller should use parse_pdf directly)
    PPTX/PPT -> python-pptx (skip markitdown, which crashes)
    Other -> UTF-8 decode, then MarkItDown fallback.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".pptx", ".ppt"):
        try:
            text = _extract_pptx_text(file_path)
            if text:
                return text
        except Exception as e:
            logger.error("pptx direct extraction failed for %s: %s", file_path, e)
    if raw_bytes is None:
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        from markitdown import MarkItDown
        return MarkItDown().convert(file_path).text_content or ""
    except Exception as e:
        logger.error("markitdown conversion failed for %s: %s", file_path, e)
        return ""


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
            content_text = _extract_text(file_path, raw_bytes=content)
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
    """List all raw sources with per-source generated page counts."""
    sources_result = await db.execute(
        select(RawSource).order_by(RawSource.created_at.desc()).limit(200)
    )
    sources = list(sources_result.scalars().all())
    if not sources:
        return []

    counts_result = await db.execute(
        select(WikiPage.source_id, func.count(WikiPage.id))
        .where(WikiPage.source_id.in_([s.id for s in sources]))
        .group_by(WikiPage.source_id)
    )
    counts = {str(sid): c for sid, c in counts_result.all()}

    out = []
    for s in sources:
        resp = SourceResponse.model_validate(s, from_attributes=True)
        resp.generated_pages_count = counts.get(str(s.id), 0)
        out.append(resp)
    return out


@router.get("/{source_id}/pages", response_model=list[WikiPageSummary])
async def list_source_pages(source_id: str, db: AsyncSession = Depends(get_db)):
    """List wiki pages generated from a specific raw source."""
    source = await db.get(RawSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="源不存在")
    result = await db.execute(
        select(WikiPage).where(WikiPage.source_id == source.id).order_by(WikiPage.created_at)
    )
    return result.scalars().all()


@router.delete("/{source_id}")
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a raw source and its file. Generated pages are kept but unlinked."""
    source = await db.get(RawSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="源不存在")
    # Unlink generated pages (keep the knowledge, orphan the source_id)
    await db.execute(
        update(WikiPage).where(WikiPage.source_id == source.id).values(source_id=None)
    )
    # Remove physical file
    if source.file_path and os.path.exists(source.file_path):
        try:
            os.remove(source.file_path)
        except OSError as e:
            logger.warning("Failed to remove file %s: %s", source.file_path, e)
    await db.delete(source)
    await db.commit()
    return {"message": "已删除", "unlinked_pages": True}


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
                source.content_text = _extract_text(source.file_path)
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

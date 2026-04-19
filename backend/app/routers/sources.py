import os
import uuid
import logging
import ipaddress
import socket
import httpx
from urllib.parse import urlparse
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete

from app.database import get_db
from app.models import RawSource, WikiPage, WikiChunk, WikiLink
from app.schemas import SourceTextSubmit, SourceURLSubmit, SourceResponse, WikiPageSummary
from app.config import settings
from app.worker import process_ingest
from app.services.preview_pdf import (
    preview_pdf_path,
    remove_preview_pdf,
    should_convert,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sources", tags=["sources"])


def _validate_url_safe(url: str, allow_redirects: bool = False) -> str:
    """Validate that a URL is safe to fetch (anti-SSRF).

    Only allows http/https to public IP addresses.
    Resolves DNS first to prevent DNS rebinding attacks.
    When allow_redirects=False (default): validates and returns the URL as-is.
    When allow_redirects=True: validates the initial URL only (caller handles redirects).
    Raises HTTPException if the URL is unsafe.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="仅支持 http/https 链接")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="无效的 URL")

    if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"):
        raise HTTPException(status_code=400, detail="不允许访问本地地址")

    try:
        resolved_ips = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="无法解析域名")

    for family, _, _, _, sockaddr in resolved_ips:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if not ip.is_global:
            raise HTTPException(
                status_code=400,
                detail="不允许访问内网地址",
            )

    return url


async def _fetch_url_with_redirect_handling(url: str, client: httpx.AsyncClient, max_redirects: int = 10) -> httpx.Response:
    """Fetch a URL manually following redirects with SSRF validation on each hop.

    Unlike client.get(follow_redirects=True), this re-validates every redirect
    target so a malicious server cannot redirect to an internal resource.
    """
    current_url = url
    followed = 0
    last_response: httpx.Response | None = None

    while followed < max_redirects:
        # Validate current URL before fetching
        _validate_url_safe(current_url)

        response = await client.get(current_url)

        if response.status_code < 300 or response.status_code > 399:
            return response

        # No more redirects — return the final response
        location = response.headers.get("location")
        if not location:
            return response

        followed += 1
        # Resolve the next URL (handles relative and absolute Location headers)
        next_url = str(httpx.URL(current_url).join_with_redirect(location))
        current_url = next_url

    # Exceeded max redirects
    raise HTTPException(status_code=400, detail="重定向次数过多")


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

    # Queue ingest. Text extraction runs in the Celery worker so the API
    # request returns sub-second even on large/slow-to-parse files.
    source = RawSource(
        id=file_id, filename=file.filename or "upload", file_path=file_path,
        content_text="", submitted_by=submitted_by, status="pending",
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
    # SSRF protection: validate URL and handle redirects manually
    _validate_url_safe(body.url)

    os.makedirs(settings.raw_storage_path, exist_ok=True)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await _fetch_url_with_redirect_handling(body.url, client)
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


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RawSource).where(RawSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="源不存在")
    count_result = await db.execute(
        select(func.count(WikiPage.id)).where(WikiPage.source_id == source.id)
    )
    resp = SourceResponse.model_validate(source, from_attributes=True)
    resp.generated_pages_count = count_result.scalar() or 0
    return resp


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


@router.get("/{source_id}/download")
async def download_source_file(source_id: str, db: AsyncSession = Depends(get_db)):
    """Stream the original raw source file back to the user (PDF/DOCX/MD/HTML/...)."""
    source = await db.get(RawSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="源不存在")
    if not source.file_path or not os.path.exists(source.file_path):
        raise HTTPException(status_code=404, detail="原文文件不存在")
    # Use original filename so the browser saves it sensibly
    safe_name = source.filename or os.path.basename(source.file_path)
    return FileResponse(
        path=source.file_path,
        filename=safe_name,
        media_type="application/octet-stream",
    )


@router.delete("/{source_id}")
async def delete_source(source_id: str, cascade: bool = False, db: AsyncSession = Depends(get_db)):
    """Delete a raw source and its file.
    If cascade=True, also delete generated wiki pages and their chunks.
    If cascade=False (default), generated pages are kept but unlinked.
    """
    source = await db.get(RawSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="源不存在")

    deleted_pages_count = 0
    if cascade:
        # Find all pages generated from this source
        pages_result = await db.execute(
            select(WikiPage).where(WikiPage.source_id == source.id)
        )
        pages = pages_result.scalars().all()
        deleted_pages_count = len(pages)

        for page in pages:
            # Delete chunks for this page
            await db.execute(
                delete(WikiChunk).where(WikiChunk.page_id == page.id)
            )
            # Delete outgoing links from this page
            await db.execute(
                delete(WikiLink).where(WikiLink.from_page_id == page.id)
            )
            # Null out incoming links pointing to this page (preserve other pages' link records)
            await db.execute(
                update(WikiLink).where(WikiLink.to_page_id == page.id).values(to_page_id=None)
            )
            await db.delete(page)
    else:
        # Unlink generated pages (keep the knowledge, orphan the source_id)
        await db.execute(
            update(WikiPage).where(WikiPage.source_id == source.id).values(source_id=None)
        )

    # Remove physical file (and its cached preview PDF, if any)
    if source.file_path:
        remove_preview_pdf(source.file_path)
        if os.path.exists(source.file_path):
            try:
                os.remove(source.file_path)
            except OSError as e:
                logger.warning("Failed to remove file %s: %s", source.file_path, e)

    await db.delete(source)
    await db.commit()
    return {
        "message": "已删除",
        "cascade": cascade,
        "deleted_pages": deleted_pages_count,
    }


@router.get("/{source_id}/preview")
async def preview_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """Return truncated content_text for preview."""
    source = await db.get(RawSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="源不存在")
    if not source.content_text:
        raise HTTPException(status_code=404, detail="该文档没有可预览的文本内容")
    # Truncate to 3000 chars for preview
    preview_text = source.content_text[:3000]
    has_more = len(source.content_text) > 3000
    return {
        "id": str(source.id),
        "filename": source.filename,
        "preview": preview_text,
        "total_length": len(source.content_text),
        "truncated": has_more,
    }


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


_INLINE_MIME = {
    ".pdf": "application/pdf",
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
}


@router.get("/{source_id}/raw")
async def source_raw_inline(source_id: str, db: AsyncSession = Depends(get_db)):
    """Serve a file suitable for inline preview.

    - For PDF/HTML/TXT/CSV/MD/DOCX/XLSX: stream the original upload with the
      correct MIME type (frontend iframes PDF/HTML; mammoth/SheetJS render
      DOCX/XLSX client-side).
    - For PPT/PPTX/DOC: serve a pre-rendered preview PDF cached during
      ingest. The original file is still available via /download.
    """
    source = await db.get(RawSource, source_id)
    if not source or not source.file_path:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not os.path.exists(source.file_path):
        raise HTTPException(status_code=404, detail="文件已被删除")

    if should_convert(source.file_path):
        preview = preview_pdf_path(source.file_path)
        if not os.path.exists(preview):
            raise HTTPException(
                status_code=404,
                detail="预览 PDF 尚未生成，请点击「重新解析」",
            )
        return FileResponse(
            preview,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"},
        )

    ext = os.path.splitext(source.file_path)[1].lower()
    mime = _INLINE_MIME.get(ext, "application/octet-stream")
    return FileResponse(
        source.file_path,
        media_type=mime,
        headers={"Content-Disposition": "inline"},
    )


@router.post("/{source_id}/reingest")
async def reingest_source(source_id: str, db: AsyncSession = Depends(get_db)):
    source = await db.get(RawSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="源不存在")

    if not source.file_path or not os.path.exists(source.file_path):
        raise HTTPException(status_code=400, detail="原始文件已丢失，无法重新处理")

    # Force re-extraction in worker, and drop any stale preview PDF so it
    # gets regenerated (this is the UX for "preview didn't come out right").
    remove_preview_pdf(source.file_path)
    source.content_text = ""
    source.status = "pending"
    source.processed_at = None
    source.error_message = None
    await db.commit()
    process_ingest.delay(str(source.id))
    return {"message": "已重新加入处理队列"}

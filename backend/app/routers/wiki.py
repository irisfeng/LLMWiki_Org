from urllib.parse import quote
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.database import get_db
from app.models import WikiPage, WikiLink, RawSource
from datetime import datetime, timezone
from app.schemas import WikiPageSummary, WikiPageDetail, WikiSearchResult, WikiPageUpdate, SourceResponse


def _render_markdown(page: WikiPage) -> str:
    fm = page.frontmatter or {}
    lines = ["---"]
    lines.append(f"title: {page.title}")
    lines.append(f"slug: {page.slug}")
    lines.append(f"type: {page.type}")
    for k, v in fm.items():
        if isinstance(v, (list, dict)):
            import json as _json
            lines.append(f"{k}: {_json.dumps(v, ensure_ascii=False)}")
        else:
            lines.append(f"{k}: {v}")
    lines.append(f"updated_at: {page.updated_at.isoformat()}")
    lines.append("---\n")
    lines.append(f"# {page.title}\n")
    lines.append(page.content or "")
    return "\n".join(lines)

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


@router.get("/tags")
async def list_tags(db: AsyncSession = Depends(get_db)):
    """Return all unique tags from wiki page frontmatter with counts."""
    from sqlalchemy import text
    result = await db.execute(text(
        "SELECT tag, COUNT(*) as count FROM wiki_pages, "
        "jsonb_array_elements_text(COALESCE(frontmatter->'tags', '[]'::jsonb)) AS tag "
        "GROUP BY tag ORDER BY count DESC LIMIT 100"
    ))
    return [{"tag": row[0], "count": row[1]} for row in result.all()]


@router.get("/pages", response_model=list[WikiPageSummary])
async def list_pages(type: str | None = None, tag: str | None = None, db: AsyncSession = Depends(get_db)):
    query = (
        select(WikiPage, RawSource.filename)
        .outerjoin(RawSource, RawSource.id == WikiPage.source_id)
        .order_by(WikiPage.updated_at.desc())
    )
    if type:
        query = query.where(WikiPage.type == type)
    if tag:
        from sqlalchemy import text as _text
        query = query.where(
            _text("frontmatter->'tags' @> :tag_json").bindparams(tag_json=f'["{tag}"]')
        )
    result = await db.execute(query.limit(200))
    out = []
    for page, filename in result.all():
        out.append({
            "id": page.id,
            "type": page.type,
            "slug": page.slug,
            "title": page.title,
            "frontmatter": page.frontmatter,
            "updated_at": page.updated_at,
            "source_filename": filename,
        })
    return out


@router.get("/pages/{slug:path}", response_model=WikiPageDetail)
async def get_page(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WikiPage).where(WikiPage.slug == slug))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    backlinks_q = await db.execute(
        select(WikiPage).join(WikiLink, WikiLink.from_page_id == WikiPage.id).where(WikiLink.to_slug == slug)
    )
    backlinks = backlinks_q.scalars().all()

    # Optional: load the raw source so the frontend can render a download/preview hero
    source = None
    if page.source_id:
        src_q = await db.execute(select(RawSource).where(RawSource.id == page.source_id))
        src = src_q.scalar_one_or_none()
        if src:
            source = SourceResponse.model_validate(src)

    return WikiPageDetail(
        id=page.id, type=page.type, slug=page.slug, title=page.title,
        frontmatter=page.frontmatter, content=page.content,
        created_at=page.created_at, updated_at=page.updated_at,
        backlinks=[WikiPageSummary(
            id=b.id, type=b.type, slug=b.slug, title=b.title,
            frontmatter=b.frontmatter, updated_at=b.updated_at
        ) for b in backlinks],
        source=source,
    )


@router.get("/pages/{slug:path}/download")
async def download_page_markdown(slug: str, db: AsyncSession = Depends(get_db)):
    """Download a wiki page as a .md file (UTF-8, with frontmatter)."""
    result = await db.execute(select(WikiPage).where(WikiPage.slug == slug))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    body = _render_markdown(page)
    safe_name = quote(f"{page.slug}.md")
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=\"{page.slug}.md\"; filename*=UTF-8''{safe_name}",
        },
    )


@router.get("/pages/{slug:path}/related", response_model=list[WikiPageSummary])
async def get_related_pages(slug: str, db: AsyncSession = Depends(get_db)):
    """Get pages related via wikilinks (1-degree connections)."""
    page = (await db.execute(
        select(WikiPage).where(WikiPage.slug == slug)
    )).scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="页面不存在")

    # Outgoing links (pages this page links to)
    outgoing = await db.execute(
        select(WikiPage)
        .join(WikiLink, WikiLink.to_page_id == WikiPage.id)
        .where(WikiLink.from_page_id == page.id)
    )
    # Incoming links (pages that link to this page)
    incoming = await db.execute(
        select(WikiPage)
        .join(WikiLink, WikiLink.from_page_id == WikiPage.id)
        .where(WikiLink.to_page_id == page.id)
    )

    seen = set()
    related = []
    for p in list(outgoing.scalars().all()) + list(incoming.scalars().all()):
        if p.id not in seen and p.id != page.id:
            seen.add(p.id)
            related.append(p)

    return related[:20]


@router.put("/pages/{slug:path}")
async def update_page(slug: str, body: WikiPageUpdate, db: AsyncSession = Depends(get_db)):
    """Update a wiki page's content. Triggers async re-chunk + re-embed."""
    page = (await db.execute(
        select(WikiPage).where(WikiPage.slug == slug)
    )).scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="页面不存在")

    page.content = body.content
    page.updated_at = datetime.now(timezone.utc)

    # Record edit metadata in frontmatter
    fm = dict(page.frontmatter) if page.frontmatter else {}
    fm['last_edited_by'] = body.edited_by or 'anonymous'
    fm['last_edited_at'] = page.updated_at.isoformat()
    page.frontmatter = fm

    await db.commit()

    # Async re-chunk + re-embed
    from app.worker import backfill_chunks_for_page
    backfill_chunks_for_page.delay(str(page.id))

    return {"message": "已保存", "slug": slug}


@router.delete("/pages/{slug:path}")
async def delete_page(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WikiPage).where(WikiPage.slug == slug))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    await db.execute(
        WikiLink.__table__.delete().where(
            or_(WikiLink.from_page_id == page.id, WikiLink.to_page_id == page.id)
        )
    )
    await db.delete(page)
    await db.commit()
    return {"message": f"Page '{slug}' deleted"}


@router.get("/search", response_model=list[WikiSearchResult])
async def search_pages(q: str = Query(..., min_length=1), db: AsyncSession = Depends(get_db)):
    search_query = select(WikiPage.slug, WikiPage.title, WikiPage.type, WikiPage.content).where(
        or_(WikiPage.title.ilike(f"%{q}%"), WikiPage.content.ilike(f"%{q}%"))
    ).limit(20)
    result = await db.execute(search_query)
    rows = result.all()

    results = []
    for row in rows:
        content = row.content or ""
        idx = content.lower().find(q.lower())
        if idx >= 0:
            start, end = max(0, idx - 50), min(len(content), idx + len(q) + 50)
            snippet = "..." + content[start:end] + "..."
        else:
            snippet = content[:100] + "..."
        results.append(WikiSearchResult(slug=row.slug, title=row.title, type=row.type, snippet=snippet))
    return results


@router.get("/stats")
async def wiki_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WikiPage.type, func.count(WikiPage.id)).group_by(WikiPage.type))
    stats = {row[0]: row[1] for row in result.all()}
    return {
        "sources": stats.get("source", 0), "entities": stats.get("entity", 0),
        "concepts": stats.get("concept", 0), "analyses": stats.get("analysis", 0),
        "total": sum(stats.values()),
    }


@router.get("/suggestions")
async def wiki_suggestions(
    limit: int = Query(3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
):
    """Random-sample cached chat-bubble suggestions. Falls back to
    hardcoded defaults when the cache is empty."""
    from app.services.suggestions import pick_suggestions
    return {"suggestions": await pick_suggestions(db, limit=limit)}


@router.post("/suggestions/refresh")
async def refresh_wiki_suggestions():
    """Force-regenerate the cache (admin/debug). Runs in worker so the
    HTTP call returns immediately."""
    from app.worker import regenerate_suggestions
    regenerate_suggestions.delay()
    return {"message": "Suggestion refresh queued"}


@router.post("/backfill-embeddings")
async def trigger_backfill():
    from app.worker import backfill_embeddings
    backfill_embeddings.delay()
    return {"message": "Embedding backfill started"}


@router.post("/backfill-chunks")
async def trigger_backfill_chunks():
    """Re-chunk all existing pages and (re)generate chunk embeddings."""
    from app.worker import backfill_chunks
    backfill_chunks.delay()
    return {"message": "Chunk backfill started"}

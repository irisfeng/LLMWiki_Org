from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.database import get_db
from app.models import WikiPage, WikiLink
from app.schemas import WikiPageSummary, WikiPageDetail, WikiSearchResult

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


@router.get("/pages", response_model=list[WikiPageSummary])
async def list_pages(type: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(WikiPage).order_by(WikiPage.updated_at.desc())
    if type:
        query = query.where(WikiPage.type == type)
    result = await db.execute(query.limit(200))
    return result.scalars().all()


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

    return WikiPageDetail(
        id=page.id, type=page.type, slug=page.slug, title=page.title,
        frontmatter=page.frontmatter, content=page.content,
        created_at=page.created_at, updated_at=page.updated_at,
        backlinks=[WikiPageSummary(
            id=b.id, type=b.type, slug=b.slug, title=b.title,
            frontmatter=b.frontmatter, updated_at=b.updated_at
        ) for b in backlinks],
    )


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


@router.post("/backfill-embeddings")
async def trigger_backfill():
    from app.worker import backfill_embeddings
    backfill_embeddings.delay()
    return {"message": "Embedding backfill started"}

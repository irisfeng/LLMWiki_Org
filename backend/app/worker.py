from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery("team_wiki", broker=settings.redis_url)

celery_app.conf.update(
    result_backend=settings.redis_url,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    beat_schedule={
        "weekly-lint": {
            "task": "app.worker.run_lint",
            "schedule": crontab(hour=9, minute=0, day_of_week=1),
        },
    },
)


@celery_app.task(name="app.worker.process_ingest")
def process_ingest(source_id: str):
    import asyncio
    import os
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.models import RawSource
    from app.services.ingest import ingest_service
    from app.services.extract import extract_text
    from app.services.preview_pdf import convert_to_preview_pdf, should_convert

    async def _run():
        engine = create_async_engine(settings.database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            source = await session.get(RawSource, source_id)
            if not source:
                return
            source.status = "processing"
            await session.commit()
            try:
                # Extract text here (not in the upload handler) so the API
                # request stays sub-second regardless of file size/format.
                if not source.content_text:
                    if not source.file_path or not os.path.exists(source.file_path):
                        raise ValueError("原始文件缺失")
                    text = await extract_text(source.file_path)
                    if not text:
                        raise ValueError("文本提取失败，请检查文件格式")
                    source.content_text = text
                    await session.commit()
                await ingest_service.process_source(source_id, source.content_text, session)
            except Exception as e:
                source.status = "failed"
                source.error_message = str(e)[:1000]
                await session.commit()
                raise

            # Best-effort: render a preview PDF for office formats so the
            # frontend can iframe it. Runs after ingest so a slow conversion
            # doesn't delay the "已完成" state visible to users.
            if source.file_path and should_convert(source.file_path):
                await asyncio.to_thread(convert_to_preview_pdf, source.file_path)
        await engine.dispose()

    asyncio.run(_run())
    # New content landed — refresh the chat-bubble cache so suggestions
    # track what's actually in the wiki. Best-effort; failures shouldn't
    # mark the ingest itself as failed.
    try:
        regenerate_suggestions.delay()
    except Exception:
        pass


@celery_app.task(name="app.worker.regenerate_suggestions")
def regenerate_suggestions():
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.services.suggestions import refresh_suggestions

    async def _run():
        engine = create_async_engine(settings.database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            try:
                await refresh_suggestions(session)
            except Exception:
                # Leave the existing cache alone on failure.
                pass
        await engine.dispose()

    asyncio.run(_run())


@celery_app.task(name="app.worker.run_lint")
def run_lint():
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.services.lint import lint_service

    async def _run():
        engine = create_async_engine(settings.database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            await lint_service.run_lint(session)
        await engine.dispose()

    asyncio.run(_run())


@celery_app.task(name="app.worker.backfill_chunks")
def backfill_chunks():
    """Re-chunk every existing page, persist chunks, generate embeddings.

    Idempotent: existing chunks for each page are replaced.
    """
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from app.models import WikiPage
    from app.services.ingest import ingest_service

    async def _run():
        engine = create_async_engine(settings.database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            result = await session.execute(select(WikiPage))
            pages = list(result.scalars().all())
            if not pages:
                return
            group_size = 5
            for i in range(0, len(pages), group_size):
                batch = pages[i : i + group_size]
                await ingest_service._rebuild_chunks_for_pages(batch, session)
                await session.commit()
        await engine.dispose()

    asyncio.run(_run())


@celery_app.task(name="app.worker.backfill_chunks_for_page")
def backfill_chunks_for_page(page_id: str):
    """Re-chunk + re-embed a single page after content edit.

    Deletes old chunks, re-chunks the updated content, generates embeddings,
    and also updates the page-level embedding for backward-compat search.
    """
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.models import WikiPage
    from app.services.ingest import ingest_service
    from app.services.embedding import embedding_service

    async def _run():
        engine = create_async_engine(settings.database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            page = await session.get(WikiPage, page_id)
            if not page:
                return
            # Re-chunk + re-embed chunks
            await ingest_service._rebuild_chunks_for_pages([page], session)
            # Update page-level embedding too
            embed_text = f"{page.title}\n{(page.content or '')[:4000]}"
            vectors = await embedding_service.embed_batch([embed_text])
            if vectors and vectors[0]:
                page.embedding = vectors[0]
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


@celery_app.task(name="app.worker.backfill_embeddings")
def backfill_embeddings():
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from app.models import WikiPage
    from app.services.embedding import embedding_service

    async def _run():
        engine = create_async_engine(settings.database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            result = await session.execute(
                select(WikiPage).where(WikiPage.embedding.is_(None))
            )
            pages = list(result.scalars().all())
            if not pages:
                return

            for i in range(0, len(pages), 20):
                batch = pages[i:i+20]
                texts = [f"{p.title}\n{(p.content or '')[:4000]}" for p in batch]
                vectors = await embedding_service.embed_batch(texts)
                for page, vec in zip(batch, vectors):
                    if vec:
                        page.embedding = vec
                await session.commit()
        await engine.dispose()

    asyncio.run(_run())

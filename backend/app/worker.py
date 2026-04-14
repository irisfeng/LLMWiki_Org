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
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.models import RawSource
    from app.services.ingest import ingest_service

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
                await ingest_service.process_source(source_id, source.content_text, session)
            except Exception as e:
                source.status = "failed"
                source.error_message = str(e)[:1000]
                await session.commit()
                raise
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

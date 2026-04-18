# Hybrid Retrieval Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ilike keyword search with pgvector embedding + jieba Chinese tokenization + hybrid retrieval, fix remaining bugs, bring Q&A quality to industry standard.

**Architecture:** Add a `embedding` vector column to WikiPage. On page create/update, call DashScope text-embedding-v3 to generate 1024-dim vectors. Query service combines vector similarity search with jieba-powered keyword search, merges results by score, and applies context budget management. Also clean up remaining bugs (reingest re-extraction, garbage page deletion, error_message cleanup).

**Tech Stack:** pgvector extension, DashScope text-embedding-v3 (OpenAI-compatible), jieba, SQLAlchemy with pgvector support (pgvector-python), existing PostgreSQL 16 + FastAPI + Celery stack.

**Constraints:** VPS has 2.8GB RAM. pgvector with 1024-dim vectors at 54 pages is ~200KB — negligible. jieba adds ~60MB. Total overhead is manageable.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/requirements.txt` | Modify | Add pgvector, jieba |
| `backend/app/config.py` | Modify | Add embedding_model, embedding_dim settings |
| `backend/app/models.py` | Modify | Add embedding Vector column to WikiPage |
| `backend/app/services/embedding.py` | Create | Embedding service: call DashScope, generate vectors |
| `backend/app/services/query.py` | Rewrite | Hybrid retrieval: vector + keyword + type-aware |
| `backend/app/services/ingest.py` | Modify | Generate embeddings on page create/update |
| `backend/app/worker.py` | Modify | Add backfill_embeddings task |
| `backend/app/routers/sources.py` | Modify | Fix reingest re-extraction (already written, needs deploy) |
| `backend/app/routers/wiki.py` | Modify | Add delete page endpoint, improve search with jieba |
| `backend/app/schemas.py` | Already modified | error_message field (already done) |
| `.env.example` | Modify | Add EMBEDDING_MODEL, update LLM config to DashScope |
| `docker-compose.yml` | Modify | Add pgvector init SQL |

---

## Task 1: Bug Fixes Batch (reingest + garbage page + .env.example)

**Files:**
- Modify: `backend/app/routers/sources.py` (reingest fix already written locally)
- Modify: `backend/app/routers/wiki.py` (add delete endpoint)
- Modify: `.env.example`

- [ ] **Step 1: Add delete page endpoint to wiki router**

Add to `backend/app/routers/wiki.py` after the `get_page` endpoint:

```python
@router.delete("/pages/{slug:path}")
async def delete_page(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WikiPage).where(WikiPage.slug == slug))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    # Delete associated wiki links
    await db.execute(
        WikiLink.__table__.delete().where(
            or_(WikiLink.from_page_id == page.id, WikiLink.to_page_id == page.id)
        )
    )
    await db.delete(page)
    await db.commit()
    return {"message": f"Page '{slug}' deleted"}
```

- [ ] **Step 2: Update .env.example to DashScope config**

Replace `.env.example` LLM section:

```
# LLM (DashScope OpenAI-compatible)
LLM_API_KEY=your-dashscope-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.6-plus

# Embedding (same DashScope API key)
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIM=1024
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/wiki.py backend/app/routers/sources.py backend/app/schemas.py .env.example
git commit -m "fix: add page delete endpoint, reingest re-extraction, update .env.example to DashScope"
```

---

## Task 2: pgvector Infrastructure

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Modify: `backend/app/models.py`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add dependencies to requirements.txt**

Add these lines to `backend/requirements.txt`:

```
pgvector==0.3.6
jieba==0.42.1
```

- [ ] **Step 2: Add embedding config to settings**

Add to `backend/app/config.py` Settings class, after `raw_storage_path`:

```python
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024
```

- [ ] **Step 3: Add pgvector init to docker-compose.yml**

Add an init script volume to the postgres service in `docker-compose.yml`:

```yaml
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 3s
      retries: 5
```

Note: Replace `postgres:16-alpine` with `pgvector/pgvector:pg16` which includes the vector extension pre-installed.

- [ ] **Step 4: Add Vector column to WikiPage model**

Modify `backend/app/models.py`. Add import at top:

```python
from pgvector.sqlalchemy import Vector
```

Add column to WikiPage class, after `source_id`:

```python
    embedding: Mapped[list | None] = mapped_column(Vector(1024), nullable=True)
```

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/app/config.py backend/app/models.py docker-compose.yml
git commit -m "feat: add pgvector infrastructure, embedding column to WikiPage"
```

---

## Task 3: Embedding Service

**Files:**
- Create: `backend/app/services/embedding.py`

- [ ] **Step 1: Create embedding service**

Create `backend/app/services/embedding.py`:

```python
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate text embeddings via DashScope OpenAI-compatible API."""

    def __init__(self):
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.model = settings.embedding_model
        self.dim = settings.embedding_dim

    async def embed(self, text: str) -> list[float] | None:
        """Generate embedding for a single text. Returns None on failure."""
        if not text or not self.api_key:
            return None
        # Truncate to ~8000 chars to stay within token limits
        text = text[:8000]
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": text,
                        "dimensions": self.dim,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]
        except Exception as e:
            logger.error("Embedding failed: %s", e)
            return None

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Generate embeddings for multiple texts. DashScope supports batch input."""
        if not texts or not self.api_key:
            return [None] * len(texts)
        truncated = [t[:8000] for t in texts]
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": truncated,
                        "dimensions": self.dim,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return [item["embedding"] for item in data["data"]]
        except Exception as e:
            logger.error("Batch embedding failed: %s", e)
            return [None] * len(texts)


embedding_service = EmbeddingService()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/embedding.py
git commit -m "feat: add embedding service for DashScope text-embedding-v3"
```

---

## Task 4: Integrate Embeddings into Ingest Pipeline

**Files:**
- Modify: `backend/app/services/ingest.py:106-121` (page creation loop)

- [ ] **Step 1: Add embedding generation to ingest**

In `backend/app/services/ingest.py`, add import at top:

```python
from app.services.embedding import embedding_service
```

After the page creation loop (after `await db_session.flush()` on line 123), add embedding generation:

```python
        # Generate embeddings for all created pages
        texts_to_embed = []
        for page in created_pages:
            embed_text = f"{page.title}\n{page.content[:4000]}"
            texts_to_embed.append(embed_text)
        if texts_to_embed:
            vectors = await embedding_service.embed_batch(texts_to_embed)
            for page, vec in zip(created_pages, vectors):
                if vec:
                    page.embedding = vec
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/ingest.py
git commit -m "feat: generate embeddings for wiki pages during ingest"
```

---

## Task 5: Hybrid Retrieval Query Service

**Files:**
- Rewrite: `backend/app/services/query.py`

- [ ] **Step 1: Rewrite query service with hybrid retrieval**

Replace entire `backend/app/services/query.py`:

```python
import logging
import jieba
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, text, func
from app.models import WikiPage
from app.services.llm import llm_client
from app.services.embedding import embedding_service

logger = logging.getLogger(__name__)

QUERY_SYSTEM_PROMPT = """你是一个知识库问答助手。你根据提供的 Wiki 页面内容回答问题。

规则：
1. 只根据提供的 Wiki 页面内容回答，不使用外部知识
2. 用 [[页面slug]] 格式引用来源页面
3. 如果提供的页面不足以回答，明确说明"知识库中暂无相关信息"
4. 回答简洁直接，避免废话
5. 如果不同页面存在矛盾，指出矛盾并呈现各方说法
6. 用中文回答（除非用户用英文提问）"""

# Map question intent to page type
TYPE_HINTS = {
    "entity": ["谁", "人物", "团队", "公司", "组织", "作者", "创始人", "开发者", "who"],
    "concept": ["什么是", "定义", "概念", "原理", "机制", "how does", "what is", "explain"],
    "source": ["论文", "文章", "报告", "书", "paper", "article", "report"],
}

STOP_WORDS = {"的", "了", "是", "在", "有", "和", "与", "对", "这", "那", "也",
              "就", "都", "而", "及", "着", "或", "中", "为", "被", "把", "从",
              "到", "说", "要", "会", "能", "上", "下", "不", "吗", "呢", "吧",
              "哪些", "什么", "怎么", "如何", "哪个", "哪里", "多少", "为什么"}

MAX_CONTEXT_CHARS = 8000


def tokenize_chinese(text: str) -> list[str]:
    """Segment Chinese text using jieba, filter stop words and short tokens."""
    words = jieba.cut(text)
    return [w.strip() for w in words if w.strip() and len(w.strip()) > 1 and w.strip() not in STOP_WORDS]


def detect_type_hint(question: str) -> str | None:
    """Detect intended page type from question keywords."""
    for page_type, keywords in TYPE_HINTS.items():
        for kw in keywords:
            if kw in question.lower():
                return page_type
    return None


class QueryService:
    async def find_relevant_pages(self, question: str, db: AsyncSession, top_k: int = 8) -> list[WikiPage]:
        """Hybrid retrieval: vector similarity + keyword matching + type awareness."""
        scored: dict[str, tuple[float, WikiPage]] = {}  # slug -> (score, page)

        # --- Branch 1: Vector similarity search ---
        query_vec = await embedding_service.embed(question)
        if query_vec:
            vec_sql = (
                select(WikiPage, WikiPage.embedding.cosine_distance(query_vec).label("distance"))
                .where(WikiPage.embedding.isnot(None))
                .order_by("distance")
                .limit(top_k)
            )
            vec_result = await db.execute(vec_sql)
            for row in vec_result:
                page = row[0]
                distance = row[1]
                similarity = 1.0 - distance  # cosine similarity
                scored[page.slug] = (similarity * 0.7, page)  # weight: 0.7

        # --- Branch 2: Keyword search with jieba ---
        keywords = tokenize_chinese(question)
        if keywords:
            conditions = []
            for kw in keywords[:8]:
                conditions.append(WikiPage.title.ilike(f"%{kw}%"))
                conditions.append(WikiPage.content.ilike(f"%{kw}%"))
            kw_result = await db.execute(
                select(WikiPage).where(or_(*conditions)).limit(top_k)
            )
            for page in kw_result.scalars().all():
                # Count how many keywords match title (high weight) and content (low weight)
                title_hits = sum(1 for kw in keywords if kw.lower() in (page.title or "").lower())
                content_hits = sum(1 for kw in keywords if kw.lower() in (page.content or "")[:2000].lower())
                kw_score = (title_hits * 0.15 + content_hits * 0.05)
                if page.slug in scored:
                    old_score, _ = scored[page.slug]
                    scored[page.slug] = (old_score + kw_score, page)
                else:
                    scored[page.slug] = (kw_score, page)

        # --- Type boost ---
        type_hint = detect_type_hint(question)
        if type_hint:
            for slug, (score, page) in scored.items():
                if page.type == type_hint:
                    scored[slug] = (score + 0.1, page)

        # --- Sort by score, return top_k ---
        ranked = sorted(scored.values(), key=lambda x: x[0], reverse=True)
        pages = [page for _, page in ranked[:top_k]]

        # --- Fallback: if too few results, add recent pages ---
        if len(pages) < 3:
            fallback_query = select(WikiPage).order_by(WikiPage.updated_at.desc()).limit(5)
            if type_hint:
                fallback_query = select(WikiPage).where(
                    WikiPage.type == type_hint
                ).order_by(WikiPage.updated_at.desc()).limit(5)
            fallback_result = await db.execute(fallback_query)
            for p in fallback_result.scalars().all():
                if p.slug not in {page.slug for page in pages}:
                    pages.append(p)
                    if len(pages) >= top_k:
                        break

        return pages

    def build_context_from_pages(self, pages: list[WikiPage]) -> str:
        """Build context string with budget management."""
        parts = []
        budget = MAX_CONTEXT_CHARS
        for page in pages:
            header = f"---\n## [{page.type}] {page.title} (slug: {page.slug})\n\n"
            max_content = max(300, budget - len(header))
            content = page.content[:max_content] if page.content else ""
            entry = header + content + "\n"
            parts.append(entry)
            budget -= len(entry)
            if budget <= 0:
                break
        return "\n".join(parts)

    async def answer(self, question: str, db: AsyncSession, history: list[dict] = None):
        pages = await self.find_relevant_pages(question, db)
        context = self.build_context_from_pages(pages)

        messages = []
        if history:
            messages.extend(history[-6:])
        messages.append({
            "role": "user",
            "content": f"以下是知识库中的相关页面：\n\n{context}\n\n---\n\n用户问题：{question}"
        })

        referenced_slugs = [p.slug for p in pages]

        async for chunk in llm_client.chat_stream(messages=messages, system_message=QUERY_SYSTEM_PROMPT):
            yield chunk

        yield {"__meta__": {"referenced_pages": referenced_slugs}}


query_service = QueryService()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/query.py
git commit -m "feat: hybrid retrieval with vector search, jieba tokenization, type awareness"
```

---

## Task 6: Backfill Embeddings for Existing Pages

**Files:**
- Modify: `backend/app/worker.py`

- [ ] **Step 1: Add backfill task to worker**

Add a new task to `backend/app/worker.py`, after the `run_lint` task:

```python
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

            # Process in batches of 20
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
```

- [ ] **Step 2: Add admin endpoint to trigger backfill**

Add to `backend/app/routers/wiki.py`:

```python
@router.post("/backfill-embeddings")
async def trigger_backfill():
    from app.worker import backfill_embeddings
    backfill_embeddings.delay()
    return {"message": "Embedding backfill started"}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/worker.py backend/app/routers/wiki.py
git commit -m "feat: add backfill task to generate embeddings for existing pages"
```

---

## Task 7: Database Migration & Deploy

- [ ] **Step 1: Create SQL migration for pgvector**

On VPS, after deploying new code and rebuilding with `pgvector/pgvector:pg16` image:

```bash
docker compose exec postgres psql -U wiki -d teamwiki -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker compose exec postgres psql -U wiki -d teamwiki -c "ALTER TABLE wiki_pages ADD COLUMN IF NOT EXISTS embedding vector(1024);"
docker compose exec postgres psql -U wiki -d teamwiki -c "CREATE INDEX IF NOT EXISTS idx_wiki_pages_embedding ON wiki_pages USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);"
```

Note: `lists = 10` is appropriate for < 1000 rows. Increase when page count grows past 1000.

- [ ] **Step 2: Add EMBEDDING_MODEL and EMBEDDING_DIM to VPS .env**

```bash
echo 'EMBEDDING_MODEL=text-embedding-v3' >> /opt/team-wiki/.env
echo 'EMBEDDING_DIM=1024' >> /opt/team-wiki/.env
```

- [ ] **Step 3: Build and deploy**

```bash
cd /opt/team-wiki
docker compose down
docker compose up -d --build
```

- [ ] **Step 4: Run backfill**

```bash
curl -s -X POST http://localhost:8000/api/wiki/backfill-embeddings -H "Authorization: Bearer $TOKEN"
```

- [ ] **Step 5: Delete garbage page**

```bash
curl -s -X DELETE http://localhost:8000/api/wiki/pages/pending-source-material -H "Authorization: Bearer $TOKEN"
```

- [ ] **Step 6: Reingest the PPTX**

Click "重新处理" on the PPTX source in the UI.

- [ ] **Step 7: Verify**

Test chat with questions that previously failed:
- "知识库里有哪些人物？" — should now match entity pages via vector search + type hint
- "什么是 Harness Engineering？" — should use both vector and keyword matching
- "TradingAgents 和 ReAct 有什么关系？" — should cross-reference correctly

---

## Summary

| Task | Description | Files Changed |
|------|-------------|---------------|
| 1 | Bug fixes batch | wiki.py, sources.py, .env.example |
| 2 | pgvector infrastructure | requirements.txt, config.py, models.py, docker-compose.yml |
| 3 | Embedding service | embedding.py (new) |
| 4 | Ingest integration | ingest.py |
| 5 | Hybrid retrieval | query.py (rewrite) |
| 6 | Backfill task | worker.py, wiki.py |
| 7 | Migration & deploy | VPS commands |

Total new/modified files: 11. All changes are backward-compatible — if embedding fails, keyword search still works as fallback.

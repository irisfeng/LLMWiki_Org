# Team LLM Wiki — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted team knowledge base that uses the Karpathy LLM Wiki pattern — sources in, structured wiki out, AI Q&A on compiled knowledge, weekly lint.

**Architecture:** Vue 3 SPA frontend + Python FastAPI backend + Celery async workers + PostgreSQL. LLM (MiniMax/Qwen) compiles sources into structured wiki pages with cross-references. Docker Compose deploys everything on a single VPS.

**Tech Stack:** Vue 3, Vite, Element Plus, FastAPI, SQLAlchemy, Celery, Redis, PostgreSQL, markdown-it, MiniMax/Qwen API (OpenAI-compatible), Docker Compose.

**Project Root:** `~/Workspace/team-wiki/` (new project, separate from Personal Wiki)

---

## File Structure

```
team-wiki/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI entry + CORS + lifespan
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   ├── database.py          # async SQLAlchemy engine + session
│   │   ├── models.py            # ORM models (wiki_pages, raw_sources, wiki_links, chat)
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── sources.py       # POST upload/text/url, GET list
│   │   │   ├── wiki.py          # GET pages, page detail, backlinks, search
│   │   │   ├── chat.py          # POST session, POST message (SSE stream)
│   │   │   └── lint.py          # GET reports, POST trigger
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── llm.py           # OpenAI-compatible client wrapper
│   │   │   ├── ingest.py        # Source → LLM → wiki pages pipeline
│   │   │   ├── query.py         # Search wiki → build context → LLM answer
│   │   │   └── lint.py          # Health check logic
│   │   └── worker.py            # Celery app + tasks (ingest, lint)
│   └── tests/
│       ├── conftest.py
│       ├── test_ingest.py
│       ├── test_wiki_api.py
│       ├── test_chat.py
│       └── test_lint.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── router/index.ts
│   │   ├── api/client.ts        # axios instance
│   │   ├── api/sources.ts
│   │   ├── api/wiki.ts
│   │   ├── api/chat.ts
│   │   ├── components/
│   │   │   ├── AppLayout.vue
│   │   │   ├── MarkdownRenderer.vue
│   │   │   ├── WikiSidebar.vue
│   │   │   ├── SearchBar.vue
│   │   │   └── ChatPanel.vue
│   │   ├── views/
│   │   │   ├── HomeView.vue
│   │   │   ├── WikiListView.vue
│   │   │   ├── WikiPageView.vue
│   │   │   ├── SourceSubmitView.vue
│   │   │   └── ChatView.vue
│   │   └── styles/main.css
│   └── nginx.conf
└── nginx/
    └── nginx.conf
```

---

## Task 1: Project Scaffold + Docker Compose

**Files:**
- Create: `~/Workspace/team-wiki/docker-compose.yml`
- Create: `~/Workspace/team-wiki/.env.example`
- Create: `~/Workspace/team-wiki/backend/Dockerfile`
- Create: `~/Workspace/team-wiki/backend/requirements.txt`
- Create: `~/Workspace/team-wiki/frontend/Dockerfile`
- Create: `~/Workspace/team-wiki/frontend/package.json`

- [ ] **Step 1: Create project directory and initialize git**

```bash
mkdir -p ~/Workspace/team-wiki && cd ~/Workspace/team-wiki
git init
```

- [ ] **Step 2: Create .env.example**

```bash
cat > .env.example << 'EOF'
# Database
POSTGRES_DB=teamwiki
POSTGRES_USER=wiki
POSTGRES_PASSWORD=changeme123

# Redis
REDIS_URL=redis://redis:6379/0

# LLM
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.minimax.chat/v1
LLM_MODEL=abab6.5s-chat

# App
DATABASE_URL=postgresql+asyncpg://wiki:changeme123@postgres:5432/teamwiki
DATABASE_URL_SYNC=postgresql://wiki:changeme123@postgres:5432/teamwiki
RAW_STORAGE_PATH=/app/data/raw
EOF
```

- [ ] **Step 3: Create docker-compose.yml**

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build: ./backend
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/app/app
      - raw_data:/app/data/raw
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build: ./backend
    env_file: .env
    volumes:
      - ./backend/app:/app/app
      - raw_data:/app/data/raw
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.worker.celery_app worker -l info -c 2

  beat:
    build: ./backend
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
    command: celery -A app.worker.celery_app beat -l info

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  pgdata:
  raw_data:
```

- [ ] **Step 4: Create backend/Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 5: Create backend/requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.35
asyncpg==0.29.0
psycopg2-binary==2.9.9
alembic==1.13.2
pydantic-settings==2.5.2
celery[redis]==5.4.0
redis==5.1.0
httpx==0.27.2
python-multipart==0.0.9
markitdown==0.1.1
sse-starlette==2.1.0
```

- [ ] **Step 6: Create backend/app/__init__.py and app/main.py stub**

```python
# backend/app/__init__.py
```

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Team LLM Wiki", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Create frontend/package.json**

```json
{
  "name": "team-wiki-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "element-plus": "^2.8.0",
    "axios": "^1.7.0",
    "markdown-it": "^14.1.0",
    "@element-plus/icons-vue": "^2.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.1.0",
    "vite": "^5.4.0",
    "vue-tsc": "^2.1.0",
    "typescript": "^5.5.0"
  }
}
```

- [ ] **Step 8: Create frontend/Dockerfile**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 9: Create .gitignore and initial commit**

```bash
cat > .gitignore << 'EOF'
.env
__pycache__/
*.pyc
node_modules/
dist/
.vite/
*.egg-info/
pgdata/
EOF

git add -A
git commit -m "feat: project scaffold with Docker Compose"
```

---

## Task 2: Database Models + Config

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/models.py`
- Create: `backend/app/schemas.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`

- [ ] **Step 1: Create config.py**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://wiki:changeme123@localhost:5432/teamwiki"
    database_url_sync: str = "postgresql://wiki:changeme123@localhost:5432/teamwiki"
    redis_url: str = "redis://localhost:6379/0"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.minimax.chat/v1"
    llm_model: str = "abab6.5s-chat"
    raw_storage_path: str = "./data/raw"

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 2: Create database.py**

```python
# backend/app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session
```

- [ ] **Step 3: Create models.py**

```python
# backend/app/models.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Enum, ForeignKey, Index, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from app.database import Base

class WikiPage(Base):
    __tablename__ = "wiki_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # source, entity, concept, analysis
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    frontmatter: Mapped[dict] = mapped_column(JSONB, default=dict)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("raw_sources.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_wiki_pages_fts", "title", "content", postgresql_using="gin"),
    )


class RawSource(Base):
    __tablename__ = "raw_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/processing/done/failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class WikiLink(Base):
    __tablename__ = "wiki_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False)
    to_page_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="SET NULL"), nullable=True)
    to_slug: Mapped[str] = mapped_column(String(255), nullable=False)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user/assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    referenced_pages: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # list of page slugs
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))


class LintReport(Base):
    __tablename__ = "lint_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issues: Mapped[dict] = mapped_column(JSONB, nullable=False)
    auto_fixed: Mapped[int] = mapped_column(default=0)
    pending_review: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Create schemas.py**

```python
# backend/app/schemas.py
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

# --- Sources ---
class SourceTextSubmit(BaseModel):
    text: str
    title: str = ""
    submitted_by: str = ""

class SourceURLSubmit(BaseModel):
    url: str
    submitted_by: str = ""

class SourceResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    submitted_by: str | None
    created_at: datetime
    processed_at: datetime | None

# --- Wiki Pages ---
class WikiPageSummary(BaseModel):
    id: UUID
    type: str
    slug: str
    title: str
    frontmatter: dict
    updated_at: datetime

class WikiPageDetail(BaseModel):
    id: UUID
    type: str
    slug: str
    title: str
    frontmatter: dict
    content: str
    created_at: datetime
    updated_at: datetime
    backlinks: list["WikiPageSummary"] = []

class WikiSearchResult(BaseModel):
    slug: str
    title: str
    type: str
    snippet: str

# --- Chat ---
class ChatMessageCreate(BaseModel):
    content: str
    session_id: UUID | None = None
    user_name: str = ""

class ChatMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    referenced_pages: list[str] | None
    created_at: datetime

# --- Lint ---
class LintReportResponse(BaseModel):
    id: UUID
    issues: dict
    auto_fixed: int
    pending_review: int
    created_at: datetime
```

- [ ] **Step 5: Set up Alembic for migrations**

```bash
cd ~/Workspace/team-wiki/backend
alembic init alembic
```

Edit `alembic/env.py` to use our models:

```python
# backend/alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.config import settings
from app.database import Base
from app.models import *  # noqa: import all models

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 6: Generate and run initial migration**

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: database models, config, and migrations"
```

---

## Task 3: LLM Service Client

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/llm.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_llm.py`

- [ ] **Step 1: Create services/__init__.py**

```python
# backend/app/services/__init__.py
```

- [ ] **Step 2: Write test for LLM client**

```python
# backend/tests/conftest.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_llm_response():
    return {
        "choices": [{
            "message": {
                "content": '{"source_page": {"title": "Test", "slug": "test", "frontmatter": {}, "content": "# Test"}}'
            }
        }]
    }
```

```python
# backend/tests/test_llm.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm import LLMClient

@pytest.mark.asyncio
async def test_llm_client_chat():
    client = LLMClient(api_key="test-key", base_url="http://fake", model="test-model")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello world"}}]
    }

    with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.chat("Say hello")
        assert result == "Hello world"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd ~/Workspace/team-wiki/backend
pip install pytest pytest-asyncio
pytest tests/test_llm.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.llm'`

- [ ] **Step 4: Implement LLM client**

```python
# backend/app/services/llm.py
import json
import httpx
from app.config import settings

class LLMClient:
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ):
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self._client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        user_message: str,
        system_message: str = "",
        temperature: float = 0.3,
    ) -> str:
        """Send a chat completion request. Returns the assistant message content."""
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})

        response = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def chat_json(
        self,
        user_message: str,
        system_message: str = "",
        temperature: float = 0.1,
    ) -> dict:
        """Send a chat request expecting JSON output. Parses and returns dict."""
        raw = await self.chat(user_message, system_message, temperature)
        # Strip markdown code fence if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(raw)

    async def chat_stream(
        self,
        messages: list[dict],
        system_message: str = "",
        temperature: float = 0.5,
    ):
        """Stream chat completion. Yields content chunks."""
        all_messages = []
        if system_message:
            all_messages.append({"role": "system", "content": system_message})
        all_messages.extend(messages)

        async with self._client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": all_messages,
                "temperature": temperature,
                "stream": True,
            },
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]

    async def close(self):
        await self._client.aclose()


# Singleton for the app
llm_client = LLMClient()
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_llm.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: LLM client with chat, JSON, and stream support"
```

---

## Task 4: Ingest Pipeline

**Files:**
- Create: `backend/app/services/ingest.py`
- Create: `backend/app/worker.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/sources.py`
- Create: `backend/tests/test_ingest.py`

- [ ] **Step 1: Write ingest service test**

```python
# backend/tests/test_ingest.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.ingest import IngestService

MOCK_LLM_OUTPUT = {
    "source_page": {
        "title": "测试文章",
        "slug": "test-article",
        "frontmatter": {"source_type": "article", "author": "张三", "tags": ["testing"]},
        "content": "## Summary\n\n这是一篇测试文章的摘要。\n\n## Key Claims\n\n- 断言1\n\n## Connections\n\n- [[entities/张三]]"
    },
    "entity_pages": [
        {
            "slug": "zhang-san",
            "action": "create",
            "title": "张三",
            "frontmatter": {"entity_type": "person", "tags": ["author"]},
            "content": "张三是一位作者。\n\n## Sources\n\n- [[sources/test-article]]"
        }
    ],
    "concept_pages": [],
    "cross_references": []
}

@pytest.mark.asyncio
async def test_ingest_parses_llm_output():
    service = IngestService()
    pages = service.parse_llm_output(MOCK_LLM_OUTPUT)
    assert len(pages) == 2
    assert pages[0]["slug"] == "test-article"
    assert pages[0]["type"] == "source"
    assert pages[1]["slug"] == "zhang-san"
    assert pages[1]["type"] == "entity"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_ingest.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement IngestService**

```python
# backend/app/services/ingest.py
import re
import os
from datetime import datetime, timezone
from app.services.llm import llm_client
from app.config import settings

INGEST_SYSTEM_PROMPT = """你是一个知识库编译器。你的任务是将原始资料编译为结构化的 Wiki 页面。

## 输出格式

你必须输出一个合法 JSON 对象（不要用 markdown code fence 包裹），包含以下字段：

{
  "source_page": {
    "title": "源标题",
    "slug": "url-friendly-slug（英文小写+连字符）",
    "frontmatter": { "source_type": "article|paper|book|report|tweet|other", "author": "作者", "date": "YYYY-MM-DD", "tags": [] },
    "content": "Markdown 正文，包含 ## Summary, ## Key Claims, ## Connections, ## Quotes 章节"
  },
  "entity_pages": [
    {
      "slug": "entity-slug",
      "action": "create",
      "title": "实体名称",
      "frontmatter": { "entity_type": "person|organization|place|product|event", "aliases": [], "tags": [] },
      "content": "实体描述，包含 ## Sources 章节链接到 source 页"
    }
  ],
  "concept_pages": [
    {
      "slug": "concept-slug",
      "action": "create",
      "title": "概念名称",
      "frontmatter": { "aliases": [], "tags": [] },
      "content": "概念解释，包含 ## Sources 章节"
    }
  ],
  "cross_references": [
    { "page_slug": "已有页面slug", "add_links": ["新页面slug"], "add_content": "追加的关联说明" }
  ]
}

## 写作规则
- 每个断言必须可溯源到原始资料
- 使用 [[slug]] 格式做交叉引用
- 简洁精确，无废话
- 中文源用中文写，英文源用英文写
- tags 使用小写连字符格式
- slug 用英文小写+连字符，从标题翻译/转写得到
- 只提取真正重要的实体和概念，不要过度拆分"""


class IngestService:
    def parse_llm_output(self, data: dict) -> list[dict]:
        """Parse LLM JSON output into a flat list of page dicts ready for DB insertion."""
        pages = []

        # Source page
        sp = data["source_page"]
        pages.append({
            "type": "source",
            "slug": sp["slug"],
            "title": sp["title"],
            "frontmatter": sp.get("frontmatter", {}),
            "content": sp["content"],
        })

        # Entity pages
        for ep in data.get("entity_pages", []):
            pages.append({
                "type": "entity",
                "slug": ep["slug"],
                "title": ep["title"],
                "frontmatter": ep.get("frontmatter", {}),
                "content": ep.get("content", ""),
                "action": ep.get("action", "create"),
            })

        # Concept pages
        for cp in data.get("concept_pages", []):
            pages.append({
                "type": "concept",
                "slug": cp["slug"],
                "title": cp["title"],
                "frontmatter": cp.get("frontmatter", {}),
                "content": cp.get("content", ""),
                "action": cp.get("action", "create"),
            })

        return pages

    def extract_wikilinks(self, content: str) -> list[str]:
        """Extract [[slug]] references from markdown content."""
        return re.findall(r'\[\[([^\]]+)\]\]', content)

    async def build_context(self, db_session) -> str:
        """Build existing wiki index for LLM context."""
        from sqlalchemy import select
        from app.models import WikiPage

        result = await db_session.execute(
            select(WikiPage.type, WikiPage.slug, WikiPage.title)
        )
        rows = result.all()
        if not rows:
            return "当前知识库为空，这是第一个源。"

        lines = ["当前知识库已有页面："]
        for row in rows:
            lines.append(f"- [{row.type}] {row.slug}: {row.title}")
        return "\n".join(lines)

    async def process_source(self, source_id: str, content_text: str, db_session):
        """Full ingest pipeline: call LLM → parse → write to DB."""
        from sqlalchemy import select
        from app.models import WikiPage, RawSource, WikiLink

        # Build context
        context = await self.build_context(db_session)

        # Call LLM
        user_message = f"{context}\n\n---\n\n## 待处理的新源材料：\n\n{content_text[:30000]}"
        data = await llm_client.chat_json(user_message, system_message=INGEST_SYSTEM_PROMPT)

        # Parse output
        pages = self.parse_llm_output(data)

        # Write pages to DB
        created_pages = []
        for page_data in pages:
            action = page_data.pop("action", "create")

            if action == "update":
                existing = await db_session.execute(
                    select(WikiPage).where(WikiPage.slug == page_data["slug"])
                )
                existing_page = existing.scalar_one_or_none()
                if existing_page:
                    existing_page.content += "\n\n" + page_data["content"]
                    existing_page.updated_at = datetime.now(timezone.utc)
                    created_pages.append(existing_page)
                    continue

            # Create new page
            if page_data["type"] == "source":
                page_data["source_id"] = source_id

            new_page = WikiPage(**page_data)
            db_session.add(new_page)
            created_pages.append(new_page)

        await db_session.flush()

        # Extract and save wikilinks
        for page in created_pages:
            links = self.extract_wikilinks(page.content)
            for link_slug in links:
                # Resolve target page
                target = await db_session.execute(
                    select(WikiPage.id).where(WikiPage.slug == link_slug)
                )
                target_id = target.scalar_one_or_none()

                wl = WikiLink(
                    from_page_id=page.id,
                    to_page_id=target_id,
                    to_slug=link_slug,
                )
                db_session.add(wl)

        # Handle cross_references
        for xref in data.get("cross_references", []):
            existing = await db_session.execute(
                select(WikiPage).where(WikiPage.slug == xref["page_slug"])
            )
            existing_page = existing.scalar_one_or_none()
            if existing_page and xref.get("add_content"):
                existing_page.content += "\n\n" + xref["add_content"]
                existing_page.updated_at = datetime.now(timezone.utc)

        # Update source status
        source = await db_session.get(RawSource, source_id)
        source.status = "done"
        source.processed_at = datetime.now(timezone.utc)

        await db_session.commit()
        return created_pages


ingest_service = IngestService()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_ingest.py -v
```

Expected: PASS

- [ ] **Step 5: Create Celery worker with ingest task**

```python
# backend/app/worker.py
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
            "schedule": crontab(hour=9, minute=0, day_of_week=1),  # Every Monday 9am
        },
    },
)


@celery_app.task(name="app.worker.process_ingest")
def process_ingest(source_id: str):
    """Celery task: process a raw source through the ingest pipeline."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.config import settings
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
    """Celery task: run weekly wiki lint."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.config import settings
    from app.services.lint import lint_service

    async def _run():
        engine = create_async_engine(settings.database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            await lint_service.run_lint(session)
        await engine.dispose()

    asyncio.run(_run())
```

- [ ] **Step 6: Create sources router**

```python
# backend/app/routers/__init__.py
```

```python
# backend/app/routers/sources.py
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
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
    """Upload a file (PDF, Word, Markdown, TXT) as a new source."""
    os.makedirs(settings.raw_storage_path, exist_ok=True)

    # Save file
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ".txt"
    file_path = os.path.join(settings.raw_storage_path, f"{file_id}{ext}")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Extract text (basic for MVP — plain text / markdown)
    try:
        content_text = content.decode("utf-8")
    except UnicodeDecodeError:
        # For binary files (PDF/Word), use markitdown
        from markitdown import MarkItDown
        mid = MarkItDown()
        result = mid.convert(file_path)
        content_text = result.text_content

    # Create DB record
    source = RawSource(
        id=file_id,
        filename=file.filename or "upload",
        file_path=file_path,
        content_text=content_text,
        submitted_by=submitted_by,
        status="pending",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    # Dispatch async ingest
    process_ingest.delay(str(source.id))

    return source


@router.post("/text", response_model=SourceResponse)
async def submit_text(
    body: SourceTextSubmit,
    db: AsyncSession = Depends(get_db),
):
    """Submit raw text as a new source."""
    os.makedirs(settings.raw_storage_path, exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = os.path.join(settings.raw_storage_path, f"{file_id}.md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(body.text)

    source = RawSource(
        id=file_id,
        filename=body.title or "text-input",
        file_path=file_path,
        content_text=body.text,
        submitted_by=body.submitted_by,
        status="pending",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    process_ingest.delay(str(source.id))
    return source


@router.post("/url", response_model=SourceResponse)
async def submit_url(
    body: SourceURLSubmit,
    db: AsyncSession = Depends(get_db),
):
    """Submit a URL to be fetched and ingested."""
    import httpx
    from markitdown import MarkItDown

    os.makedirs(settings.raw_storage_path, exist_ok=True)

    # Fetch URL content
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(body.url, follow_redirects=True)
        resp.raise_for_status()

    file_id = str(uuid.uuid4())
    file_path = os.path.join(settings.raw_storage_path, f"{file_id}.html")
    with open(file_path, "wb") as f:
        f.write(resp.content)

    # Convert to markdown
    mid = MarkItDown()
    result = mid.convert(file_path)
    content_text = result.text_content

    source = RawSource(
        id=file_id,
        filename=body.url,
        file_path=file_path,
        content_text=content_text,
        submitted_by=body.submitted_by,
        status="pending",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    process_ingest.delay(str(source.id))
    return source


@router.get("/", response_model=list[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """List all submitted sources with their processing status."""
    result = await db.execute(
        select(RawSource).order_by(RawSource.created_at.desc()).limit(100)
    )
    return result.scalars().all()
```

- [ ] **Step 7: Register router in main.py**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import sources

app = FastAPI(title="Team LLM Wiki", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: ingest pipeline — source upload, LLM compilation, Celery worker"
```

---

## Task 5: Wiki Browse API

**Files:**
- Create: `backend/app/routers/wiki.py`
- Create: `backend/tests/test_wiki_api.py`

- [ ] **Step 1: Write wiki API test**

```python
# backend/tests/test_wiki_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test**

```bash
pytest tests/test_wiki_api.py -v
```

Expected: PASS

- [ ] **Step 3: Implement wiki router**

```python
# backend/app/routers/wiki.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text
from app.database import get_db
from app.models import WikiPage, WikiLink
from app.schemas import WikiPageSummary, WikiPageDetail, WikiSearchResult

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


@router.get("/pages", response_model=list[WikiPageSummary])
async def list_pages(
    type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List wiki pages, optionally filtered by type."""
    query = select(WikiPage).order_by(WikiPage.updated_at.desc())
    if type:
        query = query.where(WikiPage.type == type)
    result = await db.execute(query.limit(200))
    return result.scalars().all()


@router.get("/pages/{slug:path}", response_model=WikiPageDetail)
async def get_page(slug: str, db: AsyncSession = Depends(get_db)):
    """Get a single wiki page by slug, including backlinks."""
    result = await db.execute(select(WikiPage).where(WikiPage.slug == slug))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Get backlinks (pages that link TO this page)
    backlinks_q = await db.execute(
        select(WikiPage)
        .join(WikiLink, WikiLink.from_page_id == WikiPage.id)
        .where(WikiLink.to_slug == slug)
    )
    backlinks = backlinks_q.scalars().all()

    return WikiPageDetail(
        id=page.id,
        type=page.type,
        slug=page.slug,
        title=page.title,
        frontmatter=page.frontmatter,
        content=page.content,
        created_at=page.created_at,
        updated_at=page.updated_at,
        backlinks=[WikiPageSummary(
            id=b.id, type=b.type, slug=b.slug,
            title=b.title, frontmatter=b.frontmatter, updated_at=b.updated_at
        ) for b in backlinks],
    )


@router.get("/search", response_model=list[WikiSearchResult])
async def search_pages(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search across wiki pages."""
    # Use PostgreSQL full-text search with simple config (supports CJK better)
    search_query = select(
        WikiPage.slug, WikiPage.title, WikiPage.type, WikiPage.content
    ).where(
        or_(
            WikiPage.title.ilike(f"%{q}%"),
            WikiPage.content.ilike(f"%{q}%"),
        )
    ).limit(20)

    result = await db.execute(search_query)
    rows = result.all()

    results = []
    for row in rows:
        # Extract snippet around match
        content = row.content or ""
        idx = content.lower().find(q.lower())
        if idx >= 0:
            start = max(0, idx - 50)
            end = min(len(content), idx + len(q) + 50)
            snippet = "..." + content[start:end] + "..."
        else:
            snippet = content[:100] + "..."

        results.append(WikiSearchResult(
            slug=row.slug, title=row.title, type=row.type, snippet=snippet
        ))

    return results


@router.get("/stats")
async def wiki_stats(db: AsyncSession = Depends(get_db)):
    """Get wiki statistics for the home page."""
    result = await db.execute(
        select(WikiPage.type, func.count(WikiPage.id)).group_by(WikiPage.type)
    )
    stats = {row[0]: row[1] for row in result.all()}
    return {
        "sources": stats.get("source", 0),
        "entities": stats.get("entity", 0),
        "concepts": stats.get("concept", 0),
        "analyses": stats.get("analysis", 0),
        "total": sum(stats.values()),
    }
```

- [ ] **Step 4: Register wiki router in main.py**

```python
# Add to backend/app/main.py
from app.routers import sources, wiki

app.include_router(sources.router)
app.include_router(wiki.router)
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: wiki browse API — list, detail, backlinks, search, stats"
```

---

## Task 6: AI Q&A (Chat)

**Files:**
- Create: `backend/app/services/query.py`
- Create: `backend/app/routers/chat.py`

- [ ] **Step 1: Implement query service**

```python
# backend/app/services/query.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models import WikiPage
from app.services.llm import llm_client

QUERY_SYSTEM_PROMPT = """你是一个知识库问答助手。你根据提供的 Wiki 页面内容回答问题。

规则：
1. 只根据提供的 Wiki 页面内容回答，不使用外部知识
2. 用 [[页面slug]] 格式引用来源页面
3. 如果提供的页面不足以回答，明确说明"知识库中暂无相关信息"
4. 回答简洁直接，避免废话
5. 如果不同页面存在矛盾，指出矛盾并呈现各方说法
6. 用中文回答（除非用户用英文提问）"""


class QueryService:
    async def find_relevant_pages(self, question: str, db: AsyncSession, top_k: int = 10) -> list[WikiPage]:
        """Find wiki pages relevant to the question using keyword matching."""
        # Split question into keywords (simple approach for MVP)
        keywords = [w for w in question.replace("？", " ").replace("?", " ").split() if len(w) > 1]

        if not keywords:
            # Fallback: return recent pages
            result = await db.execute(
                select(WikiPage).order_by(WikiPage.updated_at.desc()).limit(top_k)
            )
            return list(result.scalars().all())

        # Search pages matching any keyword
        conditions = []
        for kw in keywords[:5]:  # limit to 5 keywords
            conditions.append(WikiPage.title.ilike(f"%{kw}%"))
            conditions.append(WikiPage.content.ilike(f"%{kw}%"))

        result = await db.execute(
            select(WikiPage).where(or_(*conditions)).limit(top_k)
        )
        pages = list(result.scalars().all())

        # If too few results, add recent pages as context
        if len(pages) < 3:
            result2 = await db.execute(
                select(WikiPage).order_by(WikiPage.updated_at.desc()).limit(5)
            )
            for p in result2.scalars().all():
                if p not in pages:
                    pages.append(p)
                    if len(pages) >= top_k:
                        break

        return pages

    def build_context_from_pages(self, pages: list[WikiPage]) -> str:
        """Format wiki pages into context string for LLM."""
        parts = []
        for page in pages:
            parts.append(f"---\n## [{page.type}] {page.title} (slug: {page.slug})\n\n{page.content}\n")
        return "\n".join(parts)

    async def answer(self, question: str, db: AsyncSession, history: list[dict] = None):
        """Answer a question using wiki knowledge. Yields streamed chunks."""
        pages = await self.find_relevant_pages(question, db)
        context = self.build_context_from_pages(pages)

        messages = []
        if history:
            messages.extend(history[-6:])  # Keep last 3 turns
        messages.append({
            "role": "user",
            "content": f"以下是知识库中的相关页面：\n\n{context}\n\n---\n\n用户问题：{question}"
        })

        referenced_slugs = [p.slug for p in pages]

        async for chunk in llm_client.chat_stream(
            messages=messages,
            system_message=QUERY_SYSTEM_PROMPT,
        ):
            yield chunk

        # Return referenced pages info (caller captures full response separately)
        yield {"__meta__": {"referenced_pages": referenced_slugs}}


query_service = QueryService()
```

- [ ] **Step 2: Implement chat router with SSE streaming**

```python
# backend/app/routers/chat.py
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
async def create_session(
    user_name: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session."""
    session = ChatSession(user_name=user_name)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"session_id": str(session.id)}


@router.post("/messages")
async def send_message(
    body: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get a streamed AI response via SSE."""
    # Create or get session
    if body.session_id:
        session_id = body.session_id
    else:
        session = ChatSession(user_name=body.user_name)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        session_id = session.id

    # Save user message
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=body.content,
    )
    db.add(user_msg)
    await db.commit()

    # Get history
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    history_msgs = history_result.scalars().all()
    history = [{"role": m.role, "content": m.content} for m in history_msgs[:-1]]  # exclude current

    # Stream response
    async def event_generator():
        full_response = ""
        referenced_pages = []

        async for chunk in query_service.answer(body.content, db, history):
            if isinstance(chunk, dict) and "__meta__" in chunk:
                referenced_pages = chunk["__meta__"]["referenced_pages"]
            else:
                full_response += chunk
                yield {"event": "message", "data": chunk}

        # Save assistant message
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=full_response,
            referenced_pages=referenced_pages,
        )
        db.add(assistant_msg)
        await db.commit()

        yield {"event": "done", "data": f'{{"session_id": "{session_id}", "referenced_pages": {referenced_pages}}}'}

    return EventSourceResponse(event_generator())


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_session_messages(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all messages in a chat session."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return result.scalars().all()
```

- [ ] **Step 3: Register chat router in main.py**

```python
# backend/app/main.py — final version
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import sources, wiki, chat

app = FastAPI(title="Team LLM Wiki", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources.router)
app.include_router(wiki.router)
app.include_router(chat.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: AI Q&A — query service with wiki context + SSE streaming chat"
```

---

## Task 7: Lint Service

**Files:**
- Create: `backend/app/services/lint.py`
- Create: `backend/app/routers/lint.py`

- [ ] **Step 1: Implement lint service**

```python
# backend/app/services/lint.py
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import WikiPage, WikiLink, LintReport
from app.services.llm import llm_client

LINT_SYSTEM_PROMPT = """你是一个知识库健康检查器。分析以下 Wiki 页面，找出问题。

检查项：
1. 矛盾：不同页面对同一事实的描述不一致
2. 过时：页面内容可能已不准确（基于时间和频率判断）
3. 缺失引用：页面提到的实体/概念没有对应的 Wiki 页面
4. 交叉引用不足：明显相关但互不链接的页面

输出合法 JSON（不要 code fence）：
{
  "issues": [
    {
      "type": "contradiction|stale|missing_page|orphan|missing_link",
      "severity": "high|medium|low",
      "description": "问题描述",
      "affected_pages": ["slug1", "slug2"],
      "suggested_fix": "建议的修复方式"
    }
  ],
  "auto_fixable": [
    {
      "action": "add_link",
      "from_slug": "source-page",
      "to_slug": "target-page",
      "reason": "原因"
    }
  ]
}"""


class LintService:
    async def find_orphan_pages(self, db: AsyncSession) -> list[dict]:
        """Find pages with no incoming links."""
        # Get all pages
        all_pages = await db.execute(select(WikiPage.slug, WikiPage.title, WikiPage.type))
        all_slugs = {row.slug: row for row in all_pages.all()}

        # Get all link targets
        linked_slugs_result = await db.execute(select(WikiLink.to_slug).distinct())
        linked_slugs = {row[0] for row in linked_slugs_result.all()}

        orphans = []
        for slug, row in all_slugs.items():
            if slug not in linked_slugs and row.type != "source":
                orphans.append({
                    "type": "orphan",
                    "severity": "low",
                    "description": f"页面 '{row.title}' 没有任何入链",
                    "affected_pages": [slug],
                    "suggested_fix": "检查是否有相关页面应链接到此页"
                })
        return orphans

    async def find_broken_links(self, db: AsyncSession) -> list[dict]:
        """Find wikilinks pointing to non-existent pages."""
        result = await db.execute(
            select(WikiLink.to_slug, WikiLink.from_page_id)
            .where(WikiLink.to_page_id.is_(None))
        )
        broken = result.all()

        issues = []
        seen_slugs = set()
        for row in broken:
            if row.to_slug not in seen_slugs:
                seen_slugs.add(row.to_slug)
                issues.append({
                    "type": "missing_page",
                    "severity": "medium",
                    "description": f"被引用的页面 [[{row.to_slug}]] 不存在",
                    "affected_pages": [row.to_slug],
                    "suggested_fix": "创建该页面或修正链接"
                })
        return issues

    async def run_lint(self, db: AsyncSession) -> LintReport:
        """Run full lint check: structural checks + LLM-powered analysis."""
        issues = []

        # Structural checks (fast, no LLM needed)
        orphans = await self.find_orphan_pages(db)
        issues.extend(orphans)

        broken_links = await self.find_broken_links(db)
        issues.extend(broken_links)

        # LLM-powered analysis (sample pages for contradiction/staleness check)
        all_pages_result = await db.execute(
            select(WikiPage).order_by(WikiPage.updated_at.desc()).limit(30)
        )
        pages = all_pages_result.scalars().all()

        if len(pages) >= 5:
            # Build condensed view for LLM
            page_summaries = []
            for p in pages:
                page_summaries.append(
                    f"[{p.type}] slug={p.slug} title={p.title}\n{p.content[:500]}\n---"
                )
            context = "\n".join(page_summaries)

            try:
                llm_result = await llm_client.chat_json(
                    f"以下是知识库中最近的页面摘要，请检查问题：\n\n{context}",
                    system_message=LINT_SYSTEM_PROMPT,
                )
                if "issues" in llm_result:
                    issues.extend(llm_result["issues"])
            except Exception:
                pass  # LLM lint is best-effort

        # Save report
        report = LintReport(
            issues={"issues": issues},
            auto_fixed=0,
            pending_review=len(issues),
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        return report


lint_service = LintService()
```

- [ ] **Step 2: Implement lint router**

```python
# backend/app/routers/lint.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import LintReport
from app.schemas import LintReportResponse
from app.services.lint import lint_service

router = APIRouter(prefix="/api/lint", tags=["lint"])


@router.get("/reports", response_model=list[LintReportResponse])
async def list_reports(db: AsyncSession = Depends(get_db)):
    """List lint reports, most recent first."""
    result = await db.execute(
        select(LintReport).order_by(LintReport.created_at.desc()).limit(10)
    )
    return result.scalars().all()


@router.post("/trigger", response_model=LintReportResponse)
async def trigger_lint(db: AsyncSession = Depends(get_db)):
    """Manually trigger a lint check."""
    report = await lint_service.run_lint(db)
    return report
```

- [ ] **Step 3: Register lint router in main.py**

Add `from app.routers import sources, wiki, chat, lint` and `app.include_router(lint.router)`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: weekly lint — orphan/broken link detection + LLM contradiction check"
```

---

## Task 8: Frontend Setup + Layout

**Files:**
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router/index.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/components/AppLayout.vue`
- Create: `frontend/src/styles/main.css`

- [ ] **Step 1: Create vite.config.ts**

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src/**/*.ts", "src/**/*.vue"]
}
```

- [ ] **Step 3: Create index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Team Wiki</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

- [ ] **Step 4: Create main.ts + App.vue + router**

```typescript
// frontend/src/main.ts
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './styles/main.css'

const app = createApp(App)
app.use(ElementPlus)
app.use(router)
app.mount('#app')
```

```vue
<!-- frontend/src/App.vue -->
<template>
  <router-view />
</template>
```

```typescript
// frontend/src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', component: () => import('../views/HomeView.vue') },
  { path: '/wiki', component: () => import('../views/WikiListView.vue') },
  { path: '/wiki/:slug(.*)', component: () => import('../views/WikiPageView.vue') },
  { path: '/submit', component: () => import('../views/SourceSubmitView.vue') },
  { path: '/chat', component: () => import('../views/ChatView.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
```

- [ ] **Step 5: Create API client**

```typescript
// frontend/src/api/client.ts
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export default api
```

- [ ] **Step 6: Create AppLayout component**

```vue
<!-- frontend/src/components/AppLayout.vue -->
<template>
  <el-container class="app-layout">
    <el-header class="app-header">
      <div class="header-left">
        <router-link to="/" class="logo">📚 Team Wiki</router-link>
      </div>
      <div class="header-center">
        <el-input
          v-model="searchQuery"
          placeholder="搜索知识库..."
          @keyup.enter="doSearch"
          clearable
          style="width: 400px"
        />
      </div>
      <div class="header-right">
        <router-link to="/submit">
          <el-button type="primary">提交新源</el-button>
        </router-link>
        <router-link to="/chat">
          <el-button>AI 问答</el-button>
        </router-link>
      </div>
    </el-header>
    <el-container>
      <el-aside width="220px" class="app-aside">
        <el-menu :default-active="$route.path" router>
          <el-menu-item index="/">首页</el-menu-item>
          <el-menu-item index="/wiki?type=source">📄 Sources</el-menu-item>
          <el-menu-item index="/wiki?type=entity">👤 Entities</el-menu-item>
          <el-menu-item index="/wiki?type=concept">💡 Concepts</el-menu-item>
          <el-menu-item index="/wiki?type=analysis">📊 Analyses</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="app-main">
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const searchQuery = ref('')
const router = useRouter()

function doSearch() {
  if (searchQuery.value.trim()) {
    router.push({ path: '/wiki', query: { q: searchQuery.value } })
  }
}
</script>

<style scoped>
.app-layout { min-height: 100vh; }
.app-header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #eee; }
.logo { font-size: 20px; font-weight: bold; text-decoration: none; color: #333; }
.header-right { display: flex; gap: 8px; }
.app-aside { border-right: 1px solid #eee; padding-top: 12px; }
.app-main { padding: 24px; }
</style>
```

- [ ] **Step 7: Create main.css**

```css
/* frontend/src/styles/main.css */
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
a { color: #409eff; text-decoration: none; }
a:hover { text-decoration: underline; }

.wiki-content h1 { font-size: 1.8em; margin-bottom: 0.5em; }
.wiki-content h2 { font-size: 1.4em; margin-top: 1.5em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
.wiki-content blockquote { border-left: 3px solid #409eff; padding-left: 12px; color: #666; margin: 1em 0; }
.wiki-content code { background: #f4f4f5; padding: 2px 6px; border-radius: 3px; }

.wikilink { color: #409eff; cursor: pointer; border-bottom: 1px dashed #409eff; }
.wikilink:hover { color: #337ecc; }
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: frontend scaffold — Vue 3, Element Plus, router, layout"
```

---

## Task 9: Frontend Views

**Files:**
- Create: `frontend/src/views/HomeView.vue`
- Create: `frontend/src/views/WikiListView.vue`
- Create: `frontend/src/views/WikiPageView.vue`
- Create: `frontend/src/views/SourceSubmitView.vue`
- Create: `frontend/src/views/ChatView.vue`
- Create: `frontend/src/components/MarkdownRenderer.vue`
- Create: `frontend/src/api/wiki.ts`
- Create: `frontend/src/api/sources.ts`
- Create: `frontend/src/api/chat.ts`

- [ ] **Step 1: Create API modules**

```typescript
// frontend/src/api/wiki.ts
import api from './client'

export async function getPages(type?: string, q?: string) {
  const params: any = {}
  if (type) params.type = type
  if (q) params.q = q
  if (q) {
    const { data } = await api.get('/wiki/search', { params: { q } })
    return data
  }
  const { data } = await api.get('/wiki/pages', { params })
  return data
}

export async function getPage(slug: string) {
  const { data } = await api.get(`/wiki/pages/${slug}`)
  return data
}

export async function getStats() {
  const { data } = await api.get('/wiki/stats')
  return data
}
```

```typescript
// frontend/src/api/sources.ts
import api from './client'

export async function submitText(text: string, title: string, submittedBy: string) {
  const { data } = await api.post('/sources/text', { text, title, submitted_by: submittedBy })
  return data
}

export async function submitUrl(url: string, submittedBy: string) {
  const { data } = await api.post('/sources/url', { url, submitted_by: submittedBy })
  return data
}

export async function uploadFile(file: File, submittedBy: string) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('submitted_by', submittedBy)
  const { data } = await api.post('/sources/upload', formData)
  return data
}

export async function listSources() {
  const { data } = await api.get('/sources/')
  return data
}
```

```typescript
// frontend/src/api/chat.ts
export function streamChat(content: string, sessionId?: string, userName?: string) {
  const body = JSON.stringify({ content, session_id: sessionId, user_name: userName })

  return fetch('/api/chat/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  })
}
```

- [ ] **Step 2: Create MarkdownRenderer component**

```vue
<!-- frontend/src/components/MarkdownRenderer.vue -->
<template>
  <div class="wiki-content" v-html="rendered"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import { useRouter } from 'vue-router'

const props = defineProps<{ content: string }>()
const router = useRouter()

const md = new MarkdownIt({ html: false, linkify: true })

// Custom rule: convert [[slug]] to clickable links
const rendered = computed(() => {
  let html = md.render(props.content)
  // Replace [[slug]] with router links
  html = html.replace(
    /\[\[([^\]]+)\]\]/g,
    '<a class="wikilink" data-slug="$1">$1</a>'
  )
  return html
})

// Handle wikilink clicks via event delegation
function handleClick(e: Event) {
  const target = e.target as HTMLElement
  if (target.classList.contains('wikilink')) {
    const slug = target.getAttribute('data-slug')
    if (slug) {
      router.push(`/wiki/${slug}`)
    }
  }
}

defineExpose({ handleClick })
</script>
```

- [ ] **Step 3: Create HomeView**

```vue
<!-- frontend/src/views/HomeView.vue -->
<template>
  <AppLayout>
    <div class="home">
      <h1>Team Wiki</h1>
      <p>团队智能知识库 — 基于 LLM Wiki 模式</p>

      <el-row :gutter="20" style="margin-top: 24px">
        <el-col :span="6" v-for="s in statsCards" :key="s.label">
          <el-card shadow="hover">
            <div class="stat-card">
              <span class="stat-num">{{ s.value }}</span>
              <span class="stat-label">{{ s.label }}</span>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <h2 style="margin-top: 32px">最近更新</h2>
      <el-table :data="recentPages" style="width: 100%">
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题">
          <template #default="{ row }">
            <router-link :to="`/wiki/${row.slug}`">{{ row.title }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">{{ new Date(row.updated_at).toLocaleString('zh-CN') }}</template>
        </el-table-column>
      </el-table>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import AppLayout from '../components/AppLayout.vue'
import { getStats, getPages } from '../api/wiki'

const stats = ref({ sources: 0, entities: 0, concepts: 0, analyses: 0, total: 0 })
const recentPages = ref([])

const statsCards = computed(() => [
  { label: 'Sources', value: stats.value.sources },
  { label: 'Entities', value: stats.value.entities },
  { label: 'Concepts', value: stats.value.concepts },
  { label: 'Analyses', value: stats.value.analyses },
])

onMounted(async () => {
  stats.value = await getStats()
  recentPages.value = await getPages()
})
</script>

<style scoped>
.stat-card { text-align: center; }
.stat-num { display: block; font-size: 2em; font-weight: bold; color: #409eff; }
.stat-label { color: #999; }
</style>
```

- [ ] **Step 4: Create WikiListView**

```vue
<!-- frontend/src/views/WikiListView.vue -->
<template>
  <AppLayout>
    <div>
      <h2>{{ pageTitle }}</h2>
      <el-table :data="pages" v-loading="loading">
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题">
          <template #default="{ row }">
            <router-link :to="`/wiki/${row.slug}`">{{ row.title }}</router-link>
          </template>
        </el-table-column>
        <el-table-column label="Tags" width="200">
          <template #default="{ row }">
            <el-tag v-for="t in (row.frontmatter?.tags || [])" :key="t" size="small" style="margin-right:4px">{{ t }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import { getPages } from '../api/wiki'

const route = useRoute()
const pages = ref([])
const loading = ref(false)

const pageTitle = computed(() => {
  const q = route.query.q as string
  if (q) return `搜索: ${q}`
  const type = route.query.type as string
  const map: Record<string, string> = { source: 'Sources', entity: 'Entities', concept: 'Concepts', analysis: 'Analyses' }
  return map[type] || '全部页面'
})

async function load() {
  loading.value = true
  pages.value = await getPages(route.query.type as string, route.query.q as string)
  loading.value = false
}

onMounted(load)
watch(() => route.query, load)
</script>
```

- [ ] **Step 5: Create WikiPageView**

```vue
<!-- frontend/src/views/WikiPageView.vue -->
<template>
  <AppLayout>
    <div v-if="page" class="wiki-page">
      <div class="page-header">
        <el-tag>{{ page.type }}</el-tag>
        <h1>{{ page.title }}</h1>
        <div class="meta">
          更新于 {{ new Date(page.updated_at).toLocaleString('zh-CN') }}
          <span v-if="page.frontmatter?.author"> · {{ page.frontmatter.author }}</span>
        </div>
        <div class="tags" v-if="page.frontmatter?.tags?.length">
          <el-tag v-for="t in page.frontmatter.tags" :key="t" size="small" style="margin-right:4px">{{ t }}</el-tag>
        </div>
      </div>

      <el-divider />

      <MarkdownRenderer :content="page.content" @click="handleWikiClick" />

      <el-divider />

      <div v-if="page.backlinks?.length" class="backlinks">
        <h3>反向链接 ({{ page.backlinks.length }})</h3>
        <ul>
          <li v-for="bl in page.backlinks" :key="bl.slug">
            <router-link :to="`/wiki/${bl.slug}`">{{ bl.title }}</router-link>
            <el-tag size="small" style="margin-left:8px">{{ bl.type }}</el-tag>
          </li>
        </ul>
      </div>
    </div>
    <el-empty v-else-if="!loading" description="页面不存在" />
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import { getPage } from '../api/wiki'

const route = useRoute()
const router = useRouter()
const page = ref<any>(null)
const loading = ref(true)

async function load() {
  loading.value = true
  const slug = route.params.slug as string
  try {
    page.value = await getPage(slug)
  } catch { page.value = null }
  loading.value = false
}

function handleWikiClick(e: Event) {
  const target = e.target as HTMLElement
  if (target.classList.contains('wikilink')) {
    const slug = target.getAttribute('data-slug')
    if (slug) router.push(`/wiki/${slug}`)
  }
}

onMounted(load)
watch(() => route.params.slug, load)
</script>

<style scoped>
.page-header h1 { margin: 8px 0; }
.meta { color: #999; font-size: 0.9em; }
.backlinks ul { list-style: none; padding: 0; }
.backlinks li { margin: 4px 0; }
</style>
```

- [ ] **Step 6: Create SourceSubmitView**

```vue
<!-- frontend/src/views/SourceSubmitView.vue -->
<template>
  <AppLayout>
    <div class="submit-page">
      <h2>提交新源</h2>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="粘贴文本" name="text">
          <el-form label-position="top">
            <el-form-item label="标题">
              <el-input v-model="textForm.title" placeholder="源材料标题" />
            </el-form-item>
            <el-form-item label="内容">
              <el-input v-model="textForm.text" type="textarea" :rows="12" placeholder="粘贴文本内容..." />
            </el-form-item>
            <el-form-item label="提交者">
              <el-input v-model="textForm.submittedBy" placeholder="你的名字" />
            </el-form-item>
            <el-button type="primary" @click="doSubmitText" :loading="submitting">提交</el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="输入 URL" name="url">
          <el-form label-position="top">
            <el-form-item label="URL">
              <el-input v-model="urlForm.url" placeholder="https://..." />
            </el-form-item>
            <el-form-item label="提交者">
              <el-input v-model="urlForm.submittedBy" placeholder="你的名字" />
            </el-form-item>
            <el-button type="primary" @click="doSubmitUrl" :loading="submitting">提交</el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="上传文件" name="file">
          <el-form label-position="top">
            <el-form-item label="文件">
              <el-upload
                :auto-upload="false"
                :on-change="handleFileChange"
                :limit="1"
                accept=".pdf,.docx,.doc,.md,.txt"
              >
                <el-button>选择文件</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item label="提交者">
              <el-input v-model="fileForm.submittedBy" placeholder="你的名字" />
            </el-form-item>
            <el-button type="primary" @click="doSubmitFile" :loading="submitting">上传并处理</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <el-divider />
      <h3>最近提交</h3>
      <el-table :data="sources" size="small">
        <el-table-column prop="filename" label="文件名" />
        <el-table-column prop="submitted_by" label="提交者" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'done' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/AppLayout.vue'
import { submitText, submitUrl, uploadFile, listSources } from '../api/sources'

const activeTab = ref('text')
const submitting = ref(false)
const sources = ref([])

const textForm = ref({ title: '', text: '', submittedBy: '' })
const urlForm = ref({ url: '', submittedBy: '' })
const fileForm = ref({ file: null as File | null, submittedBy: '' })

function handleFileChange(info: any) {
  fileForm.value.file = info.raw
}

async function doSubmitText() {
  if (!textForm.value.text) return ElMessage.warning('请输入内容')
  submitting.value = true
  await submitText(textForm.value.text, textForm.value.title, textForm.value.submittedBy)
  ElMessage.success('已提交，正在处理...')
  textForm.value = { title: '', text: '', submittedBy: textForm.value.submittedBy }
  submitting.value = false
  loadSources()
}

async function doSubmitUrl() {
  if (!urlForm.value.url) return ElMessage.warning('请输入 URL')
  submitting.value = true
  await submitUrl(urlForm.value.url, urlForm.value.submittedBy)
  ElMessage.success('已提交，正在处理...')
  urlForm.value = { url: '', submittedBy: urlForm.value.submittedBy }
  submitting.value = false
  loadSources()
}

async function doSubmitFile() {
  if (!fileForm.value.file) return ElMessage.warning('请选择文件')
  submitting.value = true
  await uploadFile(fileForm.value.file, fileForm.value.submittedBy)
  ElMessage.success('已上传，正在处理...')
  fileForm.value.file = null
  submitting.value = false
  loadSources()
}

async function loadSources() {
  sources.value = await listSources()
}

onMounted(loadSources)
</script>
```

- [ ] **Step 7: Create ChatView**

```vue
<!-- frontend/src/views/ChatView.vue -->
<template>
  <AppLayout>
    <div class="chat-page">
      <h2>AI 问答</h2>
      <p class="hint">基于知识库内容回答，所有答案可溯源。</p>

      <div class="chat-messages" ref="messagesRef">
        <div v-for="msg in messages" :key="msg.id" :class="['message', msg.role]">
          <div class="message-content">
            <MarkdownRenderer v-if="msg.role === 'assistant'" :content="msg.content" @click="handleWikiClick" />
            <span v-else>{{ msg.content }}</span>
          </div>
        </div>
        <div v-if="streaming" class="message assistant">
          <div class="message-content">
            <MarkdownRenderer :content="streamContent" />
            <span class="cursor">▊</span>
          </div>
        </div>
      </div>

      <div class="chat-input">
        <el-input
          v-model="input"
          placeholder="输入问题..."
          @keyup.enter="send"
          :disabled="streaming"
        >
          <template #append>
            <el-button @click="send" :loading="streaming">发送</el-button>
          </template>
        </el-input>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import { streamChat } from '../api/chat'

const router = useRouter()
const input = ref('')
const messages = ref<{ id: number; role: string; content: string }[]>([])
const streaming = ref(false)
const streamContent = ref('')
const sessionId = ref<string | undefined>()
const messagesRef = ref<HTMLElement>()
let msgId = 0

function handleWikiClick(e: Event) {
  const target = e.target as HTMLElement
  if (target.classList.contains('wikilink')) {
    const slug = target.getAttribute('data-slug')
    if (slug) router.push(`/wiki/${slug}`)
  }
}

async function send() {
  const text = input.value.trim()
  if (!text || streaming.value) return

  messages.value.push({ id: msgId++, role: 'user', content: text })
  input.value = ''
  streaming.value = true
  streamContent.value = ''

  await nextTick()
  scrollToBottom()

  try {
    const response = await streamChat(text, sessionId.value)
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()

    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (line.includes('"event": "done"') || line.includes('"session_id"')) {
            // Parse session_id from done event
            try {
              const meta = JSON.parse(data)
              if (meta.session_id) sessionId.value = meta.session_id
            } catch {}
          } else {
            streamContent.value += data
          }
        } else if (line.startsWith('event: message')) {
          // next data line will be content
        } else if (line.startsWith('event: done')) {
          // done
        }
      }
      scrollToBottom()
    }

    messages.value.push({ id: msgId++, role: 'assistant', content: streamContent.value })
  } catch (err) {
    messages.value.push({ id: msgId++, role: 'assistant', content: '抱歉，出现错误，请稍后重试。' })
  }

  streaming.value = false
  streamContent.value = ''
}

function scrollToBottom() {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}
</script>

<style scoped>
.chat-page { display: flex; flex-direction: column; height: calc(100vh - 120px); }
.hint { color: #999; margin: 0 0 16px; }
.chat-messages { flex: 1; overflow-y: auto; padding: 16px; border: 1px solid #eee; border-radius: 8px; margin-bottom: 16px; }
.message { margin-bottom: 16px; }
.message.user .message-content { background: #ecf5ff; padding: 10px 14px; border-radius: 8px; display: inline-block; max-width: 80%; }
.message.assistant .message-content { background: #f4f4f5; padding: 10px 14px; border-radius: 8px; max-width: 90%; }
.cursor { animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0; } }
.chat-input { flex-shrink: 0; }
</style>
```

- [ ] **Step 8: Create frontend/nginx.conf**

```nginx
# frontend/nginx.conf
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;  # Required for SSE
    }
}
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: frontend views — home, wiki browser, source submit, AI chat"
```

---

## Task 10: Integration + Deploy

**Files:**
- Create: `nginx/nginx.conf` (top-level, for production)
- Modify: `docker-compose.yml` (add nginx service for production)
- Create: `Makefile`

- [ ] **Step 1: Create top-level nginx.conf**

```nginx
# nginx/nginx.conf
events { worker_connections 1024; }

http {
    include /etc/nginx/mime.types;

    upstream backend {
        server backend:8000;
    }

    server {
        listen 80;
        server_name _;

        # Frontend
        root /usr/share/nginx/html;
        index index.html;

        location / {
            try_files $uri $uri/ /index.html;
        }

        # API proxy
        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_buffering off;
            proxy_read_timeout 300s;
            client_max_body_size 50M;
        }
    }
}
```

- [ ] **Step 2: Create Makefile for convenience commands**

```makefile
# Makefile
.PHONY: dev up down logs migrate

# Development
dev:
	docker compose up -d postgres redis
	cd backend && uvicorn app.main:app --reload --port 8000 &
	cd frontend && npm run dev

# Production
up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

# Database
migrate:
	cd backend && alembic upgrade head

# Lint (manual trigger)
lint:
	curl -X POST http://localhost:8000/api/lint/trigger
```

- [ ] **Step 3: Create .env from .env.example, verify docker compose builds**

```bash
cp .env.example .env
# Edit .env with real LLM_API_KEY
docker compose build
```

- [ ] **Step 4: Start services and verify**

```bash
docker compose up -d
# Wait for health checks
sleep 10
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

- [ ] **Step 5: Run migration inside container**

```bash
docker compose exec backend alembic upgrade head
```

- [ ] **Step 6: Test end-to-end — submit a source**

```bash
curl -X POST http://localhost:8000/api/sources/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Vue 3 是一个渐进式 JavaScript 框架。它由尤雨溪创建，支持组合式 API 和选项式 API 两种编程模式。", "title": "Vue 3 简介", "submitted_by": "tony"}'
```

Wait 30-60s for Celery worker to process, then:

```bash
curl http://localhost:8000/api/wiki/pages | python -m json.tool
```

Expected: See source page + entity/concept pages created by LLM.

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat: production deploy config — nginx, Makefile, docker compose"
```

---

## Summary

| Task | What it delivers | Estimated time |
|------|-----------------|----------------|
| 1. Scaffold | Docker Compose + project structure | 30 min |
| 2. Database | Models + migrations | 30 min |
| 3. LLM Client | MiniMax/Qwen API wrapper | 20 min |
| 4. Ingest | Source → LLM → Wiki pages pipeline | 1.5 hr |
| 5. Wiki API | Browse + search + backlinks | 45 min |
| 6. Chat | AI Q&A with SSE streaming | 1 hr |
| 7. Lint | Weekly health check | 45 min |
| 8. Frontend Setup | Vue + router + layout | 30 min |
| 9. Frontend Views | All pages (home, wiki, submit, chat) | 1.5 hr |
| 10. Deploy | Nginx + integration test | 30 min |
| **Total** | **Full working MVP** | **~8 hours** |

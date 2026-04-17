# UI & Chat Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Use `frontend-design` skill for all UI implementation tasks.

**Goal:** Transform llmWiki from a raw data dump into an intuitive knowledge tool — guided homepage, dark/light theme, enhanced chat with multi-turn + knowledge explorer, and wiki editing.

**Architecture:** Incremental upgrade on existing Vue 3 + Element Plus + FastAPI stack. CSS variables for theming, no library swap. Each phase deploys independently.

**Tech Stack:** Vue 3, Element Plus 2.x, @vueuse/core (new), FastAPI, PostgreSQL + pgvector, Celery

**Spec:** `docs/superpowers/specs/2026-04-17-ui-chat-optimization-design.md`

---

## File Structure

### New Files
- `frontend/src/styles/theme.css` — CSS variable definitions (light + dark)
- `frontend/src/composables/useTheme.ts` — theme toggle composable
- `frontend/src/components/GlobalSearch.vue` — Cmd+K search overlay
- `frontend/src/components/SkeletonCard.vue` — reusable skeleton loader
- `frontend/src/views/HomeViewNew.vue` — redesigned homepage (replaces HomeView.vue)
- `frontend/src/components/ChatExplorer.vue` — knowledge explorer side panel
- `frontend/src/components/WikiEditor.vue` — lightweight markdown editor

### Modified Files
- `frontend/src/styles/main.css` — migrate hardcoded colors to CSS variables
- `frontend/src/components/AppLayout.vue` — new nav structure, theme toggle, global search
- `frontend/src/views/ChatView.vue` — three-column layout, suggested questions, explorer panel
- `frontend/src/views/WikiPageView.vue` — add edit button + editor toggle
- `frontend/src/api/wiki.ts` — add updatePage(), getRelatedPages()
- `frontend/src/api/chat.ts` — no changes needed (API already complete)
- `frontend/src/router/index.ts` — no route changes needed (paths stay same)
- `frontend/package.json` — add @vueuse/core dependency
- `backend/app/routers/wiki.py` — add PUT /pages/{slug}, GET /pages/{slug}/related
- `backend/app/services/query.py` — add conversation summarization for multi-turn

---

## Phase 1: Theme System + CSS Variables

### Task 1: Install @vueuse/core and create theme composable

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/composables/useTheme.ts`

- [ ] **Step 1: Install dependency**

```bash
cd frontend && npm install @vueuse/core
```

- [ ] **Step 2: Create theme composable**

```typescript
// frontend/src/composables/useTheme.ts
import { useDark, useToggle } from '@vueuse/core'

export const isDark = useDark({
  selector: 'html',
  attribute: 'class',
  valueDark: 'dark',
  valueLight: '',
  storageKey: 'wiki-theme',
})

export const toggleTheme = useToggle(isDark)
```

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/composables/useTheme.ts
git commit -m "feat: add theme composable with @vueuse/core useDark"
```

### Task 2: Define CSS variable system

**Files:**
- Create: `frontend/src/styles/theme.css`
- Modify: `frontend/src/styles/main.css`

- [ ] **Step 1: Create theme.css with light/dark variable sets**

```css
/* frontend/src/styles/theme.css */

/* ===== Light theme (default) ===== */
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f9fafb;
  --bg-card: #ffffff;
  --bg-hover: #f3f4f6;
  --bg-input: #ffffff;

  --text-primary: #111827;
  --text-secondary: #4b5563;
  --text-muted: #9ca3af;
  --text-inverse: #ffffff;

  --border: #e5e7eb;
  --border-light: #f3f4f6;

  --accent: #3b82f6;
  --accent-hover: #2563eb;
  --accent-soft: #eff6ff;
  --accent-text: #1d4ed8;

  --success: #10b981;
  --success-soft: #ecfdf5;
  --warning: #f59e0b;
  --warning-soft: #fffbeb;
  --danger: #ef4444;
  --danger-soft: #fef2f2;
  --info: #6b7280;
  --info-soft: #f3f4f6;

  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -4px rgba(0, 0, 0, 0.04);

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;

  --transition: 0.15s ease;
}

/* ===== Dark theme ===== */
html.dark {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-card: #1e293b;
  --bg-hover: #334155;
  --bg-input: #1e293b;

  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --text-inverse: #0f172a;

  --border: #334155;
  --border-light: #1e293b;

  --accent: #60a5fa;
  --accent-hover: #93c5fd;
  --accent-soft: #1e3a5f;
  --accent-text: #93c5fd;

  --success: #34d399;
  --success-soft: #064e3b;
  --warning: #fbbf24;
  --warning-soft: #451a03;
  --danger: #f87171;
  --danger-soft: #450a0a;
  --info: #94a3b8;
  --info-soft: #1e293b;

  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);

  color-scheme: dark;
}

/* ===== Global base styles ===== */
body {
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: background var(--transition), color var(--transition);
}

/* Element Plus dark mode overrides */
html.dark .el-menu,
html.dark .el-aside {
  background-color: var(--bg-secondary);
  border-color: var(--border);
}

html.dark .el-menu-item {
  color: var(--text-secondary);
}

html.dark .el-menu-item:hover,
html.dark .el-menu-item.is-active {
  color: var(--accent);
  background-color: var(--bg-hover);
}

html.dark .el-card,
html.dark .el-drawer,
html.dark .el-dialog {
  background-color: var(--bg-card);
  border-color: var(--border);
  color: var(--text-primary);
}

html.dark .el-input__wrapper,
html.dark .el-textarea__inner {
  background-color: var(--bg-input);
  box-shadow: 0 0 0 1px var(--border) inset;
  color: var(--text-primary);
}

html.dark .el-button--default {
  background-color: var(--bg-secondary);
  border-color: var(--border);
  color: var(--text-primary);
}

html.dark .el-table {
  background-color: var(--bg-primary);
  color: var(--text-primary);
}

html.dark .el-table tr {
  background-color: var(--bg-primary);
}

html.dark .el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background-color: var(--bg-secondary);
}

html.dark .el-tag {
  border-color: var(--border);
}

html.dark .el-empty__description p {
  color: var(--text-muted);
}
```

- [ ] **Step 2: Migrate main.css to use CSS variables**

Replace `frontend/src/styles/main.css` with:

```css
/* frontend/src/styles/main.css */
@import './theme.css';

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  -webkit-font-smoothing: antialiased;
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Wiki content styles */
.wiki-content h1 { font-size: 1.8em; margin-bottom: 0.5em; color: var(--text-primary); }
.wiki-content h2 { font-size: 1.4em; margin-top: 1.5em; border-bottom: 1px solid var(--border); padding-bottom: 0.3em; color: var(--text-primary); }
.wiki-content blockquote { border-left: 3px solid var(--accent); padding-left: 12px; color: var(--text-secondary); margin: 1em 0; }
.wiki-content code { background: var(--bg-secondary); padding: 2px 6px; border-radius: var(--radius-sm); color: var(--text-primary); }
.wiki-content pre { background: var(--bg-secondary); padding: 16px; border-radius: var(--radius-md); overflow-x: auto; }
.wiki-content pre code { background: none; padding: 0; }

.wikilink { color: var(--accent); cursor: pointer; border-bottom: 1px dashed var(--accent); }
.wikilink:hover { color: var(--accent-hover); }

/* Utility classes */
.text-muted { color: var(--text-muted); }
.text-secondary { color: var(--text-secondary); }
.bg-card { background: var(--bg-card); }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/styles/theme.css frontend/src/styles/main.css
git commit -m "feat: CSS variable theme system with light/dark mode"
```

### Task 3: Wire theme toggle into AppLayout

**Files:**
- Modify: `frontend/src/components/AppLayout.vue`

- [ ] **Step 1: Add theme toggle button to AppLayout header**

In `AppLayout.vue`, add the import and toggle button. In the `<script setup>`:

```typescript
import { isDark, toggleTheme } from '../composables/useTheme'
```

In the template header area (near the logout button), add:

```html
<el-button :icon="isDark ? Sunny : Moon" circle size="small" @click="toggleTheme()" />
```

Add the icon imports:

```typescript
import { Sunny, Moon } from '@element-plus/icons-vue'
```

- [ ] **Step 2: Verify dark mode toggles visually**

Run `cd frontend && npm run dev`, open http://localhost:5173, click the theme toggle button. Verify:
- Background switches from white to dark slate
- Text remains readable
- Element Plus components (menu, buttons, inputs) adapt
- Preference persists on page reload (localStorage `wiki-theme`)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AppLayout.vue
git commit -m "feat: add dark/light theme toggle to app header"
```

---

## Phase 2: Navigation Redesign

### Task 4: Restructure AppLayout navigation

**Files:**
- Modify: `frontend/src/components/AppLayout.vue`

- [ ] **Step 1: Rewrite AppLayout template with new nav structure**

Replace the full `AppLayout.vue` with the new navigation layout. Key changes:
- Top bar: logo left, global search center, theme toggle + logout right
- Sidebar: 首页, AI 问答, 知识库 (collapsible submenu: 全部/信息源/实体/概念), 文档管理
- Promote AI 问答 to second nav item
- Merge wiki type filters into collapsible submenu under 知识库
- Move search from content area to fixed top bar
- Responsive: sidebar collapses on mobile (<768px)

Template structure:

```html
<template>
  <el-container class="app-container">
    <!-- Top Bar -->
    <el-header class="app-header" height="56px">
      <div class="header-left">
        <el-button class="hamburger" :icon="Fold" text @click="collapsed = !collapsed" />
        <router-link to="/" class="logo">团队知识库</router-link>
      </div>
      <div class="header-center">
        <el-input
          v-model="searchQuery"
          placeholder="搜索知识库... (⌘K)"
          :prefix-icon="Search"
          clearable
          class="global-search"
          @keyup.enter="doSearch"
          ref="searchInputRef"
        />
      </div>
      <div class="header-right">
        <el-button :icon="isDark ? Sunny : Moon" circle size="small" @click="toggleTheme()" />
        <el-button :icon="SwitchButton" circle size="small" @click="logout" />
      </div>
    </el-header>

    <el-container>
      <!-- Sidebar -->
      <el-aside :width="collapsed ? '0px' : '220px'" class="app-aside">
        <el-menu :default-active="activeMenu" router :collapse="collapsed">
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>首页</span>
          </el-menu-item>
          <el-menu-item index="/chat">
            <el-icon><ChatDotRound /></el-icon>
            <span>AI 问答</span>
          </el-menu-item>
          <el-sub-menu index="wiki-group">
            <template #title>
              <el-icon><Collection /></el-icon>
              <span>知识库</span>
            </template>
            <el-menu-item index="/wiki">全部</el-menu-item>
            <el-menu-item index="/wiki?type=source">信息源</el-menu-item>
            <el-menu-item index="/wiki?type=entity">实体</el-menu-item>
            <el-menu-item index="/wiki?type=concept">概念</el-menu-item>
          </el-sub-menu>
          <el-menu-item index="/sources">
            <el-icon><FolderOpened /></el-icon>
            <span>文档管理</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- Main Content -->
      <el-main class="app-main">
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>
```

Script: add collapsed ref, Cmd+K listener, activeMenu computed from $route.

Style: new scoped CSS using CSS variables for all colors, smooth transitions, responsive collapse.

- [ ] **Step 2: Add Cmd+K keyboard shortcut for search focus**

In script setup:

```typescript
import { ref, computed, onMounted, onUnmounted } from 'vue'

const searchInputRef = ref()

function handleKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    searchInputRef.value?.focus()
  }
}

onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
```

- [ ] **Step 3: Verify navigation works**

Run dev server, verify:
- All nav links route correctly
- Knowledge base submenu expands/collapses
- Cmd+K focuses search
- Theme toggle still works
- Mobile: sidebar hides, hamburger shows

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AppLayout.vue
git commit -m "feat: redesign navigation with collapsible sidebar and global search"
```

---

## Phase 3: Homepage Redesign

### Task 5: Build new homepage

**Files:**
- Create: `frontend/src/views/HomeViewNew.vue`
- Modify: `frontend/src/router/index.ts` (swap HomeView → HomeViewNew)
- Modify: `frontend/src/api/wiki.ts` (add getRecentPages)

- [ ] **Step 1: Add getRecentPages API function**

Append to `frontend/src/api/wiki.ts`:

```typescript
export async function getRecentPages(limit: number = 15) {
  const { data } = await api.get('/wiki/pages', { params: { limit } })
  return data
}
```

- [ ] **Step 2: Create HomeViewNew.vue**

Key sections:
1. **Welcome + Search hero** — big search box with placeholder rotation, 3 quick action cards
2. **Stats row** — 4 stat cards with icons (using Element Plus icons)
3. **Recent updates** — grouped by day (today/yesterday/earlier), max 15, each with type tag + title + snippet + time
4. **Browse by type** — 3 cards (sources/entities/concepts) each showing top 3 titles

The component should:
- Fetch stats via `getStats()`
- Fetch recent pages via `getRecentPages(15)`
- Group pages by date using a computed property
- Rotate placeholder text every 3 seconds
- Route search input to `/wiki?q=` for short queries, `/chat?q=` for question-like input
- Quick actions: upload → `/submit`, chat → `/chat`, browse → `/wiki`
- All styling via CSS variables for theme support

- [ ] **Step 3: Swap router to use new homepage**

In `frontend/src/router/index.ts`, change:

```typescript
{ path: '/', component: () => import('../views/HomeViewNew.vue') },
```

- [ ] **Step 4: Verify homepage**

Run dev server, verify:
- Welcome section displays with search box
- Stats show correct numbers
- Recent updates grouped by day, not an infinite flat list
- Quick actions route to correct pages
- Dark mode renders correctly

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/HomeViewNew.vue frontend/src/api/wiki.ts frontend/src/router/index.ts
git commit -m "feat: redesign homepage with guided search, stats, and grouped recent updates"
```

---

## Phase 4: Chat Enhancements

### Task 6: Backend — conversation summarization for multi-turn

**Files:**
- Modify: `backend/app/services/query.py`

- [ ] **Step 1: Add summarize_history helper**

Add to `query.py` before the `answer()` method:

```python
async def _summarize_history(self, history: list[dict]) -> str:
    """Summarize older conversation history into a brief context string."""
    conversation_text = "\n".join(
        f"{m['role']}: {m['content'][:200]}" for m in history
    )
    summary_prompt = (
        "将以下对话历史浓缩为一句话摘要，保留关键主题和结论，不超过100字：\n\n"
        f"{conversation_text}"
    )
    result = await llm_client.chat(
        messages=[{"role": "user", "content": summary_prompt}],
        system_message="你是一个对话摘要助手。只输出摘要，不要解释。",
    )
    return result.strip()
```

- [ ] **Step 2: Update answer() to use summarization**

Replace the history injection in `answer()`:

```python
async def answer(self, question: str, db: AsyncSession, history: list[dict] = None):
    pages, chunks_by_slug = await self.retrieve(question, db)
    context = self.build_context(pages, chunks_by_slug)

    messages = []
    if history and len(history) > 0:
        if len(history) > 8:
            # Summarize older history, keep recent 6 messages
            older = history[:-6]
            recent = history[-6:]
            try:
                summary = await self._summarize_history(older)
                messages.append({
                    "role": "system",
                    "content": f"之前的对话摘要：{summary}"
                })
            except Exception:
                pass  # Skip summarization on failure
            messages.extend(recent)
        else:
            messages.extend(history)

    messages.append({
        "role": "user",
        "content": f"以下是知识库中的相关片段：\n\n{context}\n\n---\n\n用户问题：{question}"
    })

    referenced_slugs = [p.slug for p in pages]

    async for chunk in llm_client.chat_stream(messages=messages, system_message=QUERY_SYSTEM_PROMPT):
        yield chunk

    yield {"__meta__": {"referenced_pages": referenced_slugs}}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/query.py
git commit -m "feat: add conversation summarization for multi-turn chat (>8 messages)"
```

### Task 7: Backend — related pages endpoint

**Files:**
- Modify: `backend/app/routers/wiki.py`

- [ ] **Step 1: Add GET /pages/{slug}/related endpoint**

Add to `wiki.py`:

```python
@router.get("/pages/{slug:path}/related", response_model=list[WikiPageSummary])
async def get_related_pages(slug: str, db: AsyncSession = Depends(get_db)):
    """Get pages related via wikilinks (1-degree connections)."""
    page = (await db.execute(
        select(WikiPage).where(WikiPage.slug == slug)
    )).scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="页面不存在")

    # Outgoing links
    outgoing = await db.execute(
        select(WikiPage)
        .join(WikiLink, WikiLink.to_page_id == WikiPage.id)
        .where(WikiLink.from_page_id == page.id)
    )
    # Incoming links (backlinks)
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
```

Import `WikiLink` if not already imported:

```python
from app.models import WikiPage, WikiChunk, WikiLink
```

- [ ] **Step 2: Add frontend API function**

Append to `frontend/src/api/wiki.ts`:

```typescript
export async function getRelatedPages(slug: string) {
  const { data } = await api.get(`/wiki/pages/${slug}/related`)
  return data
}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/wiki.py frontend/src/api/wiki.ts
git commit -m "feat: add related pages endpoint for knowledge exploration"
```

### Task 8: Frontend — chat UI enhancements

**Files:**
- Modify: `frontend/src/views/ChatView.vue`
- Create: `frontend/src/components/ChatExplorer.vue`

- [ ] **Step 1: Create ChatExplorer component**

```typescript
// frontend/src/components/ChatExplorer.vue
// A collapsible right panel that shows:
// 1. Referenced pages from current answer (title + type tag + chunk preview)
// 2. Related pages via wikilinks
// Props: referencedPages: string[], loading: boolean
// Uses getPage() to fetch page details, getRelatedPages() for connections
// Each page card is clickable → opens wiki page in new tab
```

The component fetches page details for each referenced slug and displays:
- Section "引用来源": cards with page title, type tag, first 60 chars of content
- Section "相关页面": list of 1-degree connected pages
- All links open in new tab

- [ ] **Step 2: Redesign ChatView with three-column layout**

Update `ChatView.vue`:
- Left sidebar (240px, collapsible): session history list (move from drawer to permanent sidebar)
- Center (flex-1): conversation flow (keep existing logic)
- Right panel (300px, collapsible, default collapsed): ChatExplorer component
- Add toggle button for right panel
- Add suggested questions when conversation is empty (3-4 hardcoded starter questions)
- Change Enter → send, Shift+Enter → newline
- Replace cursor blink with skeleton "thinking" animation

- [ ] **Step 3: Add suggested questions for empty state**

When no messages exist, show clickable question cards:

```typescript
const suggestedQuestions = [
  '知识库里有哪些主题？',
  '最近上传的文档讲了什么？',
  '帮我总结一下所有信息源的核心观点',
]
```

Clicking a suggestion fills the input and sends it.

- [ ] **Step 4: Verify chat enhancements**

Run dev server, verify:
- Empty state shows suggested questions
- Sending a question streams response
- Right panel shows referenced pages after answer
- Left sidebar shows session history
- Enter sends, Shift+Enter creates newline
- Dark mode works correctly
- Mobile: single column, panels hidden

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatExplorer.vue frontend/src/views/ChatView.vue
git commit -m "feat: enhanced chat with three-column layout, knowledge explorer, and suggested questions"
```

---

## Phase 5: Wiki Lightweight Editing

### Task 9: Backend — page update endpoint

**Files:**
- Modify: `backend/app/routers/wiki.py`
- Modify: `backend/app/schemas.py`

- [ ] **Step 1: Add WikiPageUpdate schema**

Add to `backend/app/schemas.py`:

```python
class WikiPageUpdate(BaseModel):
    content: str
    edited_by: str = ""
```

- [ ] **Step 2: Add PUT /pages/{slug} endpoint**

Add to `backend/app/routers/wiki.py`:

```python
from app.schemas import WikiPageUpdate

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
```

- [ ] **Step 3: Add Celery task for single-page re-chunk**

Add to `backend/app/worker.py`:

```python
@celery_app.task
def backfill_chunks_for_page(page_id: str):
    """Re-chunk and re-embed a single page after edit."""
    import asyncio
    from app.database import async_session
    from app.services.chunker import chunker_service
    from app.services.embedding import embedding_service

    async def _process():
        async with async_session() as db:
            page = await db.get(WikiPage, page_id)
            if not page:
                return

            # Delete old chunks
            await db.execute(
                delete(WikiChunk).where(WikiChunk.page_id == page.id)
            )

            # Re-chunk
            chunks = chunker_service.chunk_page(page.content, page.title)
            for i, c in enumerate(chunks):
                chunk = WikiChunk(
                    page_id=page.id,
                    position=i,
                    heading_path=c.get('heading_path', []),
                    content=c['content'],
                    char_count=len(c['content']),
                )
                # Embed
                try:
                    chunk.embedding = await embedding_service.embed(c['content'])
                except Exception:
                    pass
                db.add(chunk)

            await db.commit()

    asyncio.run(_process())
```

Add necessary imports (`delete`, `WikiChunk`).

- [ ] **Step 4: Add frontend API function**

Append to `frontend/src/api/wiki.ts`:

```typescript
export async function updatePage(slug: string, content: string, editedBy?: string) {
  const { data } = await api.put(`/wiki/pages/${slug}`, {
    content,
    edited_by: editedBy || '',
  })
  return data
}
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/wiki.py backend/app/schemas.py backend/app/worker.py frontend/src/api/wiki.ts
git commit -m "feat: wiki page update endpoint with async re-chunk + re-embed"
```

### Task 10: Frontend — wiki editor component and integration

**Files:**
- Create: `frontend/src/components/WikiEditor.vue`
- Modify: `frontend/src/views/WikiPageView.vue`

- [ ] **Step 1: Create WikiEditor component**

A side-by-side markdown editor:
- Left: textarea with monospace font, auto-resize
- Right: live preview via MarkdownRenderer
- Bottom: "保存" (primary) and "取消" (default) buttons
- Props: `content: string`, `slug: string`
- Emits: `save(content)`, `cancel`

- [ ] **Step 2: Add edit mode to WikiPageView**

Add to WikiPageView:
- "编辑" button next to page title (using Edit icon)
- Clicking toggles `editing` ref → shows WikiEditor, hides content
- WikiEditor `@save` → calls `updatePage()` API → shows success message → exits edit mode → reloads page
- WikiEditor `@cancel` → exits edit mode without saving

- [ ] **Step 3: Verify editing flow**

Run dev server, navigate to any wiki page:
- Click "编辑" → editor appears with current content
- Modify text → right panel shows live preview
- Click "保存" → success message → page shows updated content
- Click "取消" → returns to reading mode without changes
- Dark mode: editor textarea and preview render correctly

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/WikiEditor.vue frontend/src/views/WikiPageView.vue
git commit -m "feat: lightweight wiki editor with live preview"
```

---

## Phase 6: Global UX Polish

### Task 11: Skeleton loaders and empty states

**Files:**
- Create: `frontend/src/components/SkeletonCard.vue`
- Modify: multiple views (HomeViewNew, WikiListView, SourceLibraryView, ChatView)

- [ ] **Step 1: Create SkeletonCard component**

A reusable skeleton loader using `el-skeleton`:

```vue
<template>
  <el-skeleton :rows="rows" animated :loading="loading">
    <template #default>
      <slot />
    </template>
  </el-skeleton>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ loading: boolean; rows?: number }>(), { rows: 3 })
</script>
```

- [ ] **Step 2: Replace v-loading with skeletons across all views**

In each view, replace `v-loading="loading"` with SkeletonCard wrapper.

- [ ] **Step 3: Improve all empty states with guidance**

Replace generic `<el-empty>` descriptions:
- HomeView: "还没有知识，上传第一份文档开始吧" + upload button
- WikiListView: "没有找到相关内容，试试在 AI 问答中提问？" + chat link
- ChatView empty: suggested questions (already done in Task 8)
- SourceLibraryView: "还没有文档，上传一份试试" + upload button

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/SkeletonCard.vue frontend/src/views/
git commit -m "feat: skeleton loaders and guided empty states across all views"
```

### Task 12: Breadcrumbs and responsive polish

**Files:**
- Modify: `frontend/src/views/WikiPageView.vue`
- Modify: `frontend/src/components/AppLayout.vue`
- Modify: `frontend/src/styles/main.css`

- [ ] **Step 1: Add breadcrumbs to WikiPageView**

Add above the page title:

```html
<el-breadcrumb separator="/">
  <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
  <el-breadcrumb-item :to="{ path: '/wiki' }">知识库</el-breadcrumb-item>
  <el-breadcrumb-item v-if="page?.type" :to="{ path: '/wiki', query: { type: page.type } }">
    {{ typeLabel(page.type) }}
  </el-breadcrumb-item>
  <el-breadcrumb-item>{{ page?.title }}</el-breadcrumb-item>
</el-breadcrumb>
```

- [ ] **Step 2: Add responsive media queries**

Add to `main.css`:

```css
@media (max-width: 768px) {
  .app-aside { display: none; }
  .hamburger { display: inline-flex !important; }
  .global-search { max-width: 200px; }
  .header-center { flex: 1; }
}

@media (min-width: 769px) {
  .hamburger { display: none; }
}
```

- [ ] **Step 3: Final visual pass**

Check all pages in both light and dark mode:
- Homepage, Wiki list, Wiki detail, Chat, Source library, Source submit
- Mobile viewport (375px width)
- Tablet viewport (768px width)
- Desktop viewport (1440px width)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/WikiPageView.vue frontend/src/components/AppLayout.vue frontend/src/styles/main.css
git commit -m "feat: breadcrumbs, responsive polish, and final theme pass"
```

### Task 13: Deploy to VPS

- [ ] **Step 1: Push all changes**

```bash
git push origin main
```

- [ ] **Step 2: Update VPS**

Via OrcaTerm (腾讯云 Web Shell):

```bash
cd /opt/team-wiki && git fetch origin && git reset --hard origin/main && docker compose up -d --build
```

- [ ] **Step 3: Verify production**

Open http://124.222.82.73:9527 and verify:
- Homepage shows guided layout (not a flat table)
- Theme toggle works
- Chat with multi-turn works
- Wiki edit saves correctly
- All pages render in both themes

---

## Summary

| Phase | Tasks | Key Deliverables |
|-------|-------|-----------------|
| 1. Theme System | Tasks 1-3 | CSS variables, dark/light toggle |
| 2. Navigation | Task 4 | New sidebar, Cmd+K search, responsive |
| 3. Homepage | Task 5 | Guided hero, stats, grouped updates |
| 4. Chat | Tasks 6-8 | Multi-turn summarization, knowledge explorer, suggested Qs |
| 5. Wiki Edit | Tasks 9-10 | PUT endpoint, markdown editor + live preview |
| 6. Polish | Tasks 11-13 | Skeletons, empty states, breadcrumbs, responsive, deploy |

Total: 13 tasks, 6 phases, each phase independently deployable.

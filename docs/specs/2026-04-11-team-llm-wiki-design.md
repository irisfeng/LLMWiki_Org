# Team LLM Wiki — MVP Design Spec

**Date:** 2026-04-11
**Author:** Tony (with Claude)
**Status:** Draft

---

## 概述

为 15-20 人的产品+交付团队构建一个基于 Karpathy LLM Wiki 模式的智能知识库。核心理念：LLM 预编译结构化知识页面（而非 RAG 式的实时检索），知识通过交叉引用不断复利积累。

### 设计原则

1. **LLM 写，人类用** — LLM 负责所有知识整理、关联、编译；团队只需提交源和提问
2. **预编译优于实时检索** — 每个源被处理成结构化 wiki 页面，查询时读已编译知识
3. **可溯源** — 每个断言都链接到原始来源
4. **知识复利** — 交叉引用让新知识自动关联已有知识，越用越厚
5. **简单直接** — Web 界面零学习成本，丢进去就能用

---

## MVP 功能范围

### F1: Ingest（源提交 → 自动编译）

**用户操作：**
- 上传文件（PDF、Word、Markdown、TXT）
- 粘贴文本
- 输入 URL（自动抓取转 Markdown）

**系统处理（异步）：**
1. 保存原始文件到 raw 存储（不可变）
2. 提取文本内容（PDF/Word 用 markitdown 转换）
3. 调用 LLM（MiniMax/Qwen）按 Schema 编译：
   - 创建 1 个 source summary 页
   - 创建/更新 N 个 entity 页（人、组织、产品等）
   - 创建/更新 N 个 concept 页（概念、主题、方法论等）
   - 更新已有页面的交叉引用
4. 解析生成内容中的 `[[wikilinks]]`，建立链接索引
5. 标记处理完成（status=done），前端轮询状态显示结果

**LLM Prompt 设计核心：**
- System prompt = 精简版 Schema（定义页面格式、写作风格、交叉引用规则）
- 提供现有 wiki index（页面标题列表），让 LLM 判断是新建还是更新
- 要求 LLM 输出结构化 JSON（页面列表 + 内容），后端解析写入

### F2: Browse（Wiki 浏览）

**功能：**
- 按类型（Sources / Entities / Concepts / Analyses）分类浏览
- Markdown 渲染，支持 `[[wikilink]]` 点击跳转
- 全文搜索（PostgreSQL pg_trgm）
- 每个页面显示：frontmatter 元信息、正文、反向链接（谁链接了本页）
- 首页显示：最近更新、各分类统计、最近提交的源

**不做：** 在线编辑（MVP 阶段 wiki 内容完全由 LLM 生成）

### F3: AI 问答

**用户操作：**
- 在对话框中用自然语言提问

**系统处理：**
1. 根据问题做全文搜索，找到相关 wiki 页面（top-K）
2. 将相关页面内容 + 用户问题发给 LLM
3. LLM 综合回答，引用 `[[wikilink]]` 作为来源
4. 支持多轮对话（保持上下文）
5. 若回答有复用价值，自动建议保存为 analysis 页

**检索策略：**
- Phase 1（MVP）：PostgreSQL 全文搜索 + 关键词匹配
- Phase 2（后续）：可加向量搜索增强语义匹配

### F4: Lint（每周定时健康检查）

**自动检查项：**
- 矛盾检测：不同 source 页对同一实体/概念的描述冲突
- 孤页检测：没有任何入链的页面
- 过时检测：超过 N 天未更新且被频繁引用的页面
- 缺失页面：被 `[[wikilink]]` 引用但不存在的页面
- 交叉引用缺失：相关页面之间缺少链接

**输出：**
- 生成一份 Lint Report 页面（analysis 类型）
- 列出发现的问题 + 建议的修复
- 自动执行部分修复（如补充缺失的交叉引用）
- 需要人工判断的（如矛盾）标记为待处理

**触发方式：** Cron job，每周一次（可配置）

---

## 技术架构

### 整体架构

```
                    ┌─────────────┐
                    │   Nginx     │
                    │  (反向代理)  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼                         ▼
    ┌──────────────────┐     ┌──────────────────┐
    │   Vue 3 + Vite   │     │   FastAPI        │
    │   (前端 SPA)      │     │   (后端 API)     │
    │                  │     │                  │
    │  - Wiki 浏览器    │     │  - REST API      │
    │  - 源提交表单     │     │  - WebSocket     │
    │  - AI 对话界面    │     │    (问答流式)     │
    │  - 搜索          │     │  - 文件上传       │
    └──────────────────┘     └────────┬─────────┘
                                      │
                          ┌───────────┼───────────┐
                          ▼           ▼           ▼
                   ┌───────────┐ ┌────────┐ ┌─────────┐
                   │PostgreSQL │ │ Redis  │ │ 文件系统 │
                   │           │ │        │ │  (raw/)  │
                   │- wiki页面  │ │- 任务队列│ │- 原始文件│
                   │- 链接索引  │ │- 会话缓存│ │          │
                   │- 全文搜索  │ │        │ │          │
                   └───────────┘ └────────┘ └─────────┘
                          ▲
                          │
                   ┌───────────┐
                   │  Celery   │
                   │  Worker   │
                   │           │
                   │- Ingest   │
                   │- Lint     │
                   │- 调用LLM  │
                   └───────────┘
                          │
                          ▼
                   ┌───────────┐
                   │ MiniMax/  │
                   │ Qwen API  │
                   └───────────┘
```

### 技术选型明细

| 组件 | 技术 | 版本 | 理由 |
|------|------|------|------|
| 前端框架 | Vue 3 + Vite | 3.4+ | 国内生态好，轻量，SFC 开发快 |
| UI 组件 | Element Plus | 2.x | 成熟稳定，团队类产品首选 |
| Markdown 渲染 | markdown-it + 自定义 wikilink 插件 | - | 灵活、可扩展 |
| 后端框架 | Python FastAPI | 0.110+ | 异步、自动文档、LLM 生态好 |
| 数据库 | PostgreSQL | 16 | JSONB + 全文搜索 + 成熟可靠 |
| 任务队列 | Celery + Redis | 5.3+ | 异步 ingest/lint 处理 |
| 文件转换 | markitdown | latest | PDF/Word/URL → Markdown |
| LLM SDK | openai-compatible client | - | MiniMax/Qwen 均兼容 OpenAI 格式 |
| 部署 | Docker Compose | - | 一键启动，适合单 VPS |
| 反向代理 | Nginx | - | SSL + 静态资源 + API 路由 |

### 数据库 Schema

```sql
-- Wiki 页面（核心表）
CREATE TABLE wiki_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(20) NOT NULL,  -- source, entity, concept, analysis
    slug VARCHAR(255) UNIQUE NOT NULL,  -- URL-friendly 标识
    title TEXT NOT NULL,
    frontmatter JSONB DEFAULT '{}',  -- tags, author, date, aliases 等
    content TEXT NOT NULL,  -- Markdown body
    source_id UUID REFERENCES raw_sources(id),  -- 关联的原始源（source类型页面）
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 全文搜索索引
CREATE INDEX idx_wiki_pages_fts ON wiki_pages
    USING GIN (to_tsvector('simple', title || ' ' || content));

-- JSONB 索引（按 tag 查询）
CREATE INDEX idx_wiki_pages_tags ON wiki_pages
    USING GIN ((frontmatter->'tags'));

-- 原始源文件
CREATE TABLE raw_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,  -- 本地存储路径
    content_text TEXT,  -- 提取的纯文本（供 LLM 处理）
    submitted_by VARCHAR(100),  -- 提交者
    status VARCHAR(20) DEFAULT 'pending',  -- pending/processing/done/failed
    error_message TEXT,  -- 失败原因
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- Wiki 链接关系（交叉引用索引）
CREATE TABLE wiki_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    to_page_id UUID REFERENCES wiki_pages(id) ON DELETE SET NULL,
    to_slug VARCHAR(255) NOT NULL,  -- 目标 slug（即使目标页不存在也记录）
    context TEXT,  -- 链接所在句子
    UNIQUE(from_page_id, to_slug)
);

-- AI 对话记录
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_name VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id),
    role VARCHAR(20) NOT NULL,  -- user/assistant
    content TEXT NOT NULL,
    referenced_pages UUID[],  -- 引用的 wiki 页面 ID
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Lint 报告
CREATE TABLE lint_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issues JSONB NOT NULL,  -- [{type, severity, description, affected_pages}]
    auto_fixed INTEGER DEFAULT 0,
    pending_review INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## LLM 交互设计

### Ingest System Prompt（精简版 Schema）

```
你是一个知识库编译器。你的任务是将原始资料编译为结构化的 Wiki 页面。

## 输出格式

你必须输出一个 JSON 对象，包含以下字段：

{
  "source_page": {
    "title": "源标题",
    "slug": "url-friendly-slug",
    "frontmatter": { "source_type": "article", "author": "...", "date": "...", "tags": [] },
    "content": "Markdown 正文（包含 Summary, Key Claims, Connections, Quotes 章节）"
  },
  "entity_pages": [
    {
      "slug": "existing-slug 或 new-slug",
      "action": "create" | "update",
      "title": "...",
      "frontmatter": { "entity_type": "person|organization|...", "aliases": [], "tags": [] },
      "content": "Markdown 正文" | "append_content": "追加内容（update 时）"
    }
  ],
  "concept_pages": [...同上结构...],
  "cross_references": [
    { "page_slug": "已有页面slug", "add_links": ["新页面slug"], "add_content": "追加的关联说明" }
  ]
}

## 写作规则
- 每个断言必须可溯源到原始资料
- 使用 [[slug]] 格式做交叉引用
- 简洁精确，无废话
- 若源中有多方观点，都要呈现
- tags 使用小写连字符格式，复用已有 tags
```

### Query System Prompt

```
你是一个知识库问答助手。你根据提供的 Wiki 页面内容回答问题。

规则：
1. 只根据提供的 Wiki 页面内容回答，不使用外部知识
2. 用 [[页面标题]] 格式引用来源页面
3. 如果提供的页面不足以回答，明确说明"知识库中暂无相关信息"
4. 回答简洁直接，避免废话
5. 如果不同页面存在矛盾，指出矛盾并呈现各方说法
```

### Lint System Prompt

```
你是一个知识库健康检查器。分析以下 Wiki 页面，找出问题。

检查项：
1. 矛盾：不同页面对同一事实的描述不一致
2. 过时：页面内容可能已不准确（基于时间判断）
3. 缺失引用：页面提到的实体/概念没有对应的 Wiki 页面
4. 孤立页面：没有其他页面链接到的页面
5. 交叉引用不足：明显相关但互不链接的页面

输出 JSON 格式：
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
      "action": "add_link|create_page|update_content",
      "target_slug": "...",
      "content": "..."
    }
  ]
}
```

---

## API 设计

### 核心端点

```
POST   /api/sources/upload      # 上传文件
POST   /api/sources/text        # 粘贴文本
POST   /api/sources/url         # 提交 URL
GET    /api/sources             # 源列表 + 处理状态

GET    /api/wiki/pages          # 页面列表（支持 type 筛选）
GET    /api/wiki/pages/:slug    # 单个页面详情
GET    /api/wiki/pages/:slug/backlinks  # 反向链接
GET    /api/wiki/search?q=...   # 全文搜索

POST   /api/chat/sessions       # 创建会话
POST   /api/chat/messages       # 发送消息（SSE 流式响应）
GET    /api/chat/sessions/:id   # 获取会话历史

GET    /api/lint/reports        # Lint 报告列表
POST   /api/lint/trigger        # 手动触发 Lint
```

---

## 部署配置

### Docker Compose 服务

```yaml
version: '3.8'
services:
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./frontend/dist:/usr/share/nginx/html

  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://wiki:xxx@postgres:5432/teamwiki
      - REDIS_URL=redis://redis:6379
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_BASE_URL=${LLM_BASE_URL}  # MiniMax 或 Qwen 端点
      - LLM_MODEL=${LLM_MODEL}
    depends_on: [postgres, redis]

  worker:
    build: ./backend
    command: celery -A app.worker worker -l info
    environment: *backend-env
    depends_on: [postgres, redis]

  beat:
    build: ./backend
    command: celery -A app.worker beat -l info  # 定时任务（Lint）
    depends_on: [redis]

  postgres:
    image: postgres:16-alpine
    volumes: ["pgdata:/var/lib/postgresql/data"]
    environment:
      POSTGRES_DB: teamwiki
      POSTGRES_USER: wiki
      POSTGRES_PASSWORD: ${DB_PASSWORD}

  redis:
    image: redis:7-alpine

volumes:
  pgdata:
```

### VPS 最低配置建议

- CPU: 2 核
- RAM: 4GB（PostgreSQL + Celery + FastAPI）
- 磁盘: 50GB（raw 文件 + 数据库）
- 带宽: 标准即可

---

## 用户流程

### 流程 1：提交新源

```
团队成员打开网页 → 点「提交新源」
  → 选择：上传文件 / 粘贴文本 / 输入 URL
  → 填写提交者名字（简单标识，无需登录）
  → 提交
  → 页面显示"处理中..."
  → 1-2 分钟后刷新，看到新生成的 wiki 页面
  → 点击 source 页面，查看自动生成的 entity/concept 交叉引用
```

### 流程 2：AI 问答

```
团队成员打开网页 → 点「AI 问答」
  → 输入问题："我们团队之前在 X 项目上做了什么决策？"
  → AI 读取相关 wiki 页面，综合回答
  → 回答中带 [[页面名]] 链接，可点击查看原始 wiki 页面
  → 支持追问
```

### 流程 3：日常浏览

```
团队成员打开网页 → 看到首页
  → 最近更新列表（哪些知识新增/变更了）
  → 按分类浏览（Entities: 项目、人物、客户...）
  → 点进某个 entity 页面
  → 看到关于它的综合信息 + 所有相关 source 链接
  → 点 [[wikilink]] 跳转到关联页面
```

---

## 后续迭代方向（非 MVP）

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P1 | 用户认证 | 简单的用户系统 + 权限 |
| P1 | Wiki 手动编辑 | 允许人工修正 LLM 生成的内容 |
| P2 | 向量搜索 | 增强语义匹配（pgvector） |
| P2 | 审核流程 | Ingest 后先 draft → review → publish |
| P2 | 通知推送 | 新知识入库通知（企业微信/飞书 webhook） |
| P3 | 批量导入 | 一次性导入已有文档仓库 |
| P3 | Analysis 生成 | 用户触发跨源综合分析 |
| P3 | 知识图谱可视化 | entity/concept 关系图 |

---

## 与 RAG 方案的对比（设计选择依据）

| 维度 | 本方案（LLM Wiki） | 传统 RAG（FastGPT 等） |
|------|-------------------|----------------------|
| 知识形态 | 预编译结构化页面 | 文档碎片(chunk) |
| 查询准确性 | 高（读已编译、可溯源） | 中（依赖检索召回率） |
| 知识积累 | 复利（交叉引用网络） | 线性（文档堆叠） |
| 一致性 | 强（一个事实一个编译版本） | 弱（同一问题可能不同答案） |
| 矛盾处理 | 显式标记 | 静默忽略 |
| 可审计 | 完全可读、可追溯 | 黑箱 |
| 处理成本 | Ingest 时高（每源调 LLM） | Ingest 时低（只做 embedding） |
| 查询成本 | 中（读页面 + LLM 综合） | 中（检索 + LLM 生成） |
| 适合场景 | 团队知识沉淀、决策追溯 | 大规模文档快速问答 |

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| LLM 生成质量不稳定 | 页面内容有误或结构不对 | 结构化 JSON 输出 + 校验；失败重试 |
| Ingest 处理慢（大文档） | 用户等待久 | 异步队列 + 进度提示；大文档分段处理 |
| Wiki 页面冲突（同时更新同一页） | 数据覆盖 | 乐观锁 + 版本号；update 用 append 而非覆盖 |
| LLM token 超限 | 无法处理大源或大 wiki index | 分段处理；index 只传标题列表不传全文 |
| VPS 资源不足 | 服务卡顿 | 限制并发 worker 数；必要时升配 |

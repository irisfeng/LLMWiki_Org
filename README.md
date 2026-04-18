# llmWiki_Org

> 团队知识库与 RAG 助手 — Vue 3 前端 + FastAPI 后端 + pgvector + Celery + Element Plus。

一站式收集团队文档、自动切分入库、向量检索，并通过侧边 AI 助手以引用来源的形式回答问题。配套 Lint 流水线对内容进行结构化健康检查。

## 功能亮点

- **知识库管理** — 文档上传 / Markdown 编辑 / 标签 / 分类树
- **RAG 问答** — 流式回答 + 引用来源 + 历史会话
- **向量检索** — pgvector 混合检索（向量 + 关键词）
- **内容质量** — Lint 流水线（结构、引用、风格）+ 健康分数报表
- **Paper Tones 设计** — 暖纸色调 + Rail/WikiTree 双栏布局，长时阅读友好

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vite、Element Plus、markdown-it、Mermaid |
| 后端 | FastAPI、SQLAlchemy 2、Pydantic、JWT |
| 数据 | PostgreSQL 16 + pgvector |
| 异步 | Celery + Redis |
| 部署 | Docker Compose + Nginx |

## 快速开始

```bash
cp .env.example .env             # 配置 LLM key、数据库密码等
docker compose up -d --build     # 启动全部服务
# 访问 http://localhost:8080
```

本地开发：

```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
cd frontend && pnpm install && pnpm dev
```

## 目录结构

```
backend/    FastAPI 应用（routers、services、models、worker）
frontend/   Vue 3 SPA（views、components、composables、styles）
nginx/      反向代理 + SPA 路由
docs/       设计稿、规范、TODO
```

## 部署

生产部署到 Docker Compose 单机环境（默认 8080 端口）。详见 [docs/](docs/) 与 `docker-compose.yml`。

## License

MIT

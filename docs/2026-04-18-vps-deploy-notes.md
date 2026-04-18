# 2026-04-18 VPS 部署更新说明

本次本地改动清单，按「部署风险」从高到低排序。VPS pull 后按顺序操作。

---

## 🔴 高风险 / 必做

### 1. 数据库迁移（首次必跑）
本次加了**初始 schema 迁移**和**启动时自动迁移**，VPS 升级后首次启动会尝试跑 `alembic upgrade head`。

**背景**：项目原本只有 `001_add_wiki_chunks`，缺失初始 schema。新环境部署会因表不存在而 500。本次新增 `000_initial_schema` 补上全部基础表（raw_sources / wiki_pages / wiki_links / chat_sessions / chat_messages / lint_reports）。

**VPS 已有数据库的处理**：
- VPS 数据库已有表，但 `alembic_version` 表里可能已经 stamp 在 `001_wiki_chunks` 了
- 新迁移 `000` 的 down_revision 是 None，`001` 的 down_revision 改成了 `000_initial_schema`
- 跑 `alembic upgrade head` 时，如果已经 stamp 001，alembic 会认为所有迁移都已执行，**不会重复建表**
- 但如果 alembic 没 stamp（比如老 VPS 手动建表），会试图建已经存在的表，报错

**VPS 检查一次**（部署前）：
```bash
docker compose exec backend sh -c 'PYTHONPATH=/app alembic current'
```

- 输出 `001_wiki_chunks` → 安全，直接部署
- 输出空 / `None` → **先 stamp**：`alembic stamp head` 再部署
- 迁移报错 → 贴给我看

---

### 2. 依赖包变更（必须 rebuild 镜像）
- `backend/requirements.txt`：`markitdown==0.1.1` → `markitdown[all]==0.1.1`
  - 装上 docx / xlsx / pptx / audio 等 extras
  - 不装的话 .xlsx 和 .docx 上传会在文本提取时失败
- 会拉额外 ~100MB 依赖（pandas / openpyxl 等）

**部署命令**：
```bash
docker compose build --no-cache backend worker   # --no-cache 保证装新依赖
docker compose up -d --force-recreate backend worker
```

---

## 🟠 中风险

### 3. 启动行为变更
`backend/Dockerfile` 加了 `ENTRYPOINT ["/app/entrypoint.sh"]`，启动时**自动跑 alembic 迁移**再启动 uvicorn。

- 好处：新环境/新迁移零手动
- 注意：worker 也会跑迁移（幂等，不冲突），但首次启动会慢几秒

如果 VPS 某些定制启动脚本依赖直接 CMD，注意这里行为变了。

### 4. 路由变更（用户书签/外部引用会失效）
- 🗑 删除：`/submit`、`/sources`（列表页）
- 🆕 新增：`/source/:id`（单个信息源详情）、`/graph`（关系图谱占位）
- 上传入口统一到 **sidebar 的「新建/上传」按钮**，弹 modal

**如果有人书签了 `/submit`**，跳转会 404。可按需加 router redirect。

### 5. 前端上传流程重写
- 老的 `SourceSubmitView`、`SourceLibraryView` 删除
- 新组件 `UploadModal.vue` — 拖拽、并发 3 路、独立状态、失败可重试、解析进度轮询
- 入口：sidebar 按钮 / WikiListView header / 任意地方调 `openUploadModal()`

---

## 🟡 低风险（纯优化/bugfix）

### 6. Backend 逻辑修复
- `backend/app/services/embedding.py`：`embed_batch` 按 10 条分批（DashScope v3 单次最多 10 条，之前会 400）
- `backend/app/services/ingest.py`：slug 冲突时 defensive merge 而非报 UniqueViolation（reingest 同一文件会成功）
- `backend/app/routers/sources.py`：新增 `GET /api/sources/{id}` 单条详情端点

### 7. 前端文案 / 视觉修复
- `HomeView.vue`：
  - "ny" bug（userName 取后 2 字对英文名错）→ 纯 ASCII 显 全名，中文仍取后 2 字
  - "11 份文档"歧义 → 改为「N 份信息源、共 M 个知识页面」，删除 `todayEdits` 假数据
- `AppLayout.vue`：侧栏「文档」nav 换成「关系图谱」，合并「上传文档」大按钮为「新建/上传」
- `WikiListView.vue` / `WikiPageView.vue` / `SourceDetailView.vue`：统一 header-strip + paper-tones 布局

---

## 部署步骤（VPS 标准流程）

```bash
cd /path/to/llmWiki_Org      # VPS 项目路径
git pull origin main

# 1. 先看 alembic 状态
docker compose exec backend sh -c 'PYTHONPATH=/app alembic current'
# 如果不是 001_wiki_chunks，按上面"高风险#1"处理

# 2. rebuild + 重启（后端 / worker 必须重建，前端看情况）
docker compose build --no-cache backend worker
docker compose up -d --force-recreate backend worker

# 3. 前端（如果用全 docker 编排）
docker compose build frontend
docker compose up -d frontend

# 4. 验证
docker compose logs -f backend  # 看 alembic 有无错误
curl -sf http://127.0.0.1:8080/  # nginx 入口（按实际端口）
```

---

## 回滚准备

如果部署后出问题：

```bash
# 回滚代码
git checkout <上个 commit>
docker compose build backend worker
docker compose up -d --force-recreate backend worker

# 如果数据库乱了（不太可能，因为 000 是首建）
docker compose exec backend sh -c 'PYTHONPATH=/app alembic downgrade -1'
```

---

## 还没做（留待 VPS 上完再决策）

- 🔲 **原文档嵌入预览**（方案 A：LibreOffice 转 PDF + iframe）— 已评估待你拍板
- 🔲 **多用户系统（Phase B）**— 用户系统 + 邀请码 + 权限；已评估待你拍板 6 个决策
- 🔲 **MINERU_API_KEY**：本地没测 PDF，VPS 上的如果之前 key 过期记得刷新
- 🔲 **AUTH_PASSWORD**：当前本地 `.env` 是 `your-team-password` 占位；VPS 的保持不动

---

## 快速自测清单（部署完走一遍）

1. [ ] 登录进去首页显示"晚上好，XXX"（不是 "ny"）
2. [ ] 首页 KPI 卡片数字对得上数据库
3. [ ] 侧栏「新建/上传」弹 modal，不是跳 `/submit`
4. [ ] 传一个 docx 和 xlsx，10-20s 内看到「已入库 · 生成 N 页 · 查看 →」
5. [ ] 点「查看」跳 `/source/:id`，能预览解析内容、下载原文、删除
6. [ ] 点 wiki 页面的「查看信息源详情」能到 `/source/:id`
7. [ ] `/chat` 问一个问题，流式返回有引用
8. [ ] `/graph` 是占位页（Beta 标签）
9. [ ] `/lint` 点「立即检查」有结果

有任何一步挂了，贴 `docker compose logs backend` 和 `docker compose logs worker`。

# llmWiki_Org 待办事项

## Lint 检查发现的问题（2026-04-18）

### 内容问题（3 个，高优先级）
- [ ] AICC 定义矛盾：`aicc`、`bailing-aicc`、`bailing-intelligent-knowledge-base-solution` 页面描述不一致
- [ ] 缺失链接：`json-structured-output` 应链接到 `cc-gateway` 相关页面
- [ ] 缺失链接：`harness-engineering` 应链接到 `claude-code` 页面

### 断链（14 个，中优先级）
- [ ] 讨论处理方式：A) 自动创建缺失概念页面 B) 修复/移除无效链接 C) 优化 ingest 流程避免产生断链
- [ ] 主要来源：`tradingagents-multi-agents-llm-financial-trading-framework`（6 个断链）
- [ ] 主要来源：`microgpt-explained-interactively`（7 个断链）

### 孤儿页面（24 个，低优先级）
- [ ] 暂不处理，随文档增加会自然产生交叉引用
- [ ] 后续考虑：是否需要优化 ingest 的链接生成策略

## Codex 审核待修复（Medium/Low 级别）

### Medium
- [ ] 文档预览：请求竞态保护（AbortController）
- [ ] 文档预览：纯文本模式可选（防钓鱼）
- [ ] 标签筛选：`/wiki/tags` 全表 JSONB 展开性能优化（GIN 索引或缓存）
- [ ] 标签筛选：`tag` 过滤改用 `json.dumps` 避免特殊字符 500
- [ ] 标签筛选：`/wiki/tags` 脏数据防护（`jsonb_typeof='array'` 前置判断）
- [ ] 级联删除：N+1 DML 改批量删除
- [ ] 级联删除：勾选后按钮文案动态改为"删除文档和页面"
- [ ] 会话删除：移动端删除按钮可发现性（hover 不适用触屏）
- [ ] 会话删除：`chat_messages.session_id` 加索引
- [ ] Lint 仪表盘：trigger 改异步任务+轮询（避免长请求超时）
- [ ] Lint 仪表盘：初始加载与运行检查并发竞态保护

### Low
- [ ] 文档预览：新接口补 `response_model`，前端补严格 TS 类型
- [ ] 文档预览：截断按段落而非硬切 3000 字符
- [ ] 标签筛选：`loadTags()` 静默吞错改为区分空数据与加载失败
- [ ] Lint 仪表盘：列表 `:key="idx"` 改稳定 key

## 上一轮审核待修复

### Medium（之前的 Codex 全面审核）
- [ ] 大组件拆分：ChatView 815 行、HomeViewNew 713 行
- [ ] 数据库索引：ChatMessage、WikiChunk 外键和排序列
- [ ] 硬编码常量：Token TTL、搜索 top-k 改 env 配置
- [ ] 删除旧 HomeView.vue 死代码
- [ ] Alembic 迁移链补全
- [ ] 测试覆盖：核心 API 测试
- [ ] README 文档

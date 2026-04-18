from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import WikiPage, WikiLink, LintReport
from app.services.llm import llm_client

LINT_SYSTEM_PROMPT = """你是一个知识库健康检查器。分析以下 Wiki 页面，找出问题。

检查项：
1. 矛盾：不同页面对同一事实的描述不一致
2. 过时：页面内容可能已不准确
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
  ]
}"""


class LintService:
    async def find_orphan_pages(self, db: AsyncSession) -> list[dict]:
        all_pages = await db.execute(select(WikiPage.slug, WikiPage.title, WikiPage.type))
        all_slugs = {row.slug: row for row in all_pages.all()}
        linked_slugs_result = await db.execute(select(WikiLink.to_slug).distinct())
        linked_slugs = {row[0] for row in linked_slugs_result.all()}

        orphans = []
        for slug, row in all_slugs.items():
            if slug not in linked_slugs and row.type != "source":
                orphans.append({
                    "type": "orphan", "severity": "low",
                    "description": f"页面 '{row.title}' 没有任何入链",
                    "affected_pages": [slug], "suggested_fix": "检查是否有相关页面应链接到此页"
                })
        return orphans

    async def find_broken_links(self, db: AsyncSession) -> list[dict]:
        # Include from_page slug so the dashboard can show which page has the broken link
        result = await db.execute(
            select(WikiLink.to_slug, WikiPage.slug.label("from_slug"))
            .join(WikiPage, WikiLink.from_page_id == WikiPage.id)
            .where(WikiLink.to_page_id.is_(None))
        )
        broken = result.all()
        issues = []
        seen: dict[str, list[str]] = {}  # to_slug -> list of from_slugs
        for row in broken:
            if row.to_slug not in seen:
                seen[row.to_slug] = []
            seen[row.to_slug].append(row.from_slug)
        for to_slug, from_slugs in seen.items():
            issues.append({
                "type": "missing_page", "severity": "medium",
                "description": f"被引用的页面 [[{to_slug}]] 不存在",
                "affected_pages": [to_slug],
                "from_pages": from_slugs,
                "suggested_fix": "创建该页面或修正链接"
            })
        return issues

    async def run_lint(self, db: AsyncSession) -> LintReport:
        issues = []
        issues.extend(await self.find_orphan_pages(db))
        issues.extend(await self.find_broken_links(db))

        all_pages_result = await db.execute(select(WikiPage).order_by(WikiPage.updated_at.desc()).limit(30))
        pages = all_pages_result.scalars().all()

        if len(pages) >= 5:
            page_summaries = [f"[{p.type}] slug={p.slug} title={p.title}\n{p.content[:500]}\n---" for p in pages]
            context = "\n".join(page_summaries)
            try:
                llm_result = await llm_client.chat_json(
                    f"以下是知识库中最近的页面摘要，请检查问题：\n\n{context}",
                    system_message=LINT_SYSTEM_PROMPT,
                )
                if "issues" in llm_result:
                    issues.extend(llm_result["issues"])
            except Exception:
                pass

        report = LintReport(issues={"issues": issues}, auto_fixed=0, pending_review=len(issues))
        db.add(report)
        await db.commit()
        await db.refresh(report)
        return report


lint_service = LintService()

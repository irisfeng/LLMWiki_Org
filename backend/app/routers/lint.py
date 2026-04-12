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
    result = await db.execute(select(LintReport).order_by(LintReport.created_at.desc()).limit(10))
    return result.scalars().all()


@router.post("/trigger", response_model=LintReportResponse)
async def trigger_lint(db: AsyncSession = Depends(get_db)):
    report = await lint_service.run_lint(db)
    return report

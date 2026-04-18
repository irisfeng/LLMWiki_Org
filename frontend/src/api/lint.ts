import api from './client'

export interface LintIssue {
  type: string // 'orphan' | 'missing_page' | 'contradiction' | 'stale' | 'missing_link'
  severity: 'high' | 'medium' | 'low'
  description: string
  affected_pages: string[]
  from_pages?: string[] // For broken links: which pages contain the broken reference
  suggested_fix: string
}

export interface LintReport {
  id: string
  issues: { issues: LintIssue[] } // Backend stores as {"issues": [...]}
  auto_fixed: number
  pending_review: number
  created_at: string
}

/** Extract the flat issue list from a report, handling missing/malformed data. */
export function getIssueList(report: LintReport): LintIssue[] {
  if (!report.issues) return []
  if (Array.isArray(report.issues)) return report.issues as unknown as LintIssue[]
  if (Array.isArray(report.issues.issues)) return report.issues.issues
  return []
}

export async function getReports(): Promise<LintReport[]> {
  const { data } = await api.get('/lint/reports')
  return data
}

export async function triggerLint(): Promise<LintReport> {
  const { data } = await api.post('/lint/trigger')
  return data
}

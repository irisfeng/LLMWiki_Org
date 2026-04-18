import api from './client'

export interface LintIssue {
  type: string
  severity: 'high' | 'medium' | 'low'
  description: string
  affected_pages: string[]
  suggested_fix: string
}

export interface LintReport {
  id: string
  issues: {
    orphan_pages?: { slug: string; title: string }[]
    broken_links?: { from_slug: string; to_slug: string }[]
    content_issues?: LintIssue[]
  }
  auto_fixed: number
  pending_review: number
  created_at: string
}

export async function getReports(): Promise<LintReport[]> {
  const { data } = await api.get('/lint/reports')
  return data
}

export async function triggerLint(): Promise<LintReport> {
  const { data } = await api.post('/lint/trigger')
  return data
}

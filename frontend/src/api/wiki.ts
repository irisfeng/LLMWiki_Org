import api from './client'

export async function getPages(type?: string, q?: string, tag?: string) {
  if (q) {
    const { data } = await api.get('/wiki/search', { params: { q } })
    return data
  }
  const params: any = {}
  if (type) params.type = type
  if (tag) params.tag = tag
  const { data } = await api.get('/wiki/pages', { params })
  return data
}

export async function getTags() {
  const { data } = await api.get('/wiki/tags')
  return data as { tag: string; count: number }[]
}

export async function getPage(slug: string) {
  const { data } = await api.get(`/wiki/pages/${slug}`)
  return data
}

export async function getStats() {
  const { data } = await api.get('/wiki/stats')
  return data
}

export async function getRelatedPages(slug: string) {
  const { data } = await api.get(`/wiki/pages/${slug}/related`)
  return data
}

export async function getRecentPages(limit: number = 20) {
  const { data } = await api.get('/wiki/pages', { params: { limit } })
  return data
}

/** Public URL to download the original raw source file (PDF/DOCX/...) */
export function sourceDownloadUrl(sourceId: string) {
  return `/api/sources/${sourceId}/download`
}

export async function updatePage(slug: string, content: string, editedBy?: string) {
  const { data } = await api.put(`/wiki/pages/${slug}`, {
    content,
    edited_by: editedBy || '',
  })
  return data
}

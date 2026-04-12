import api from './client'

export async function getPages(type?: string, q?: string) {
  if (q) {
    const { data } = await api.get('/wiki/search', { params: { q } })
    return data
  }
  const params: any = {}
  if (type) params.type = type
  const { data } = await api.get('/wiki/pages', { params })
  return data
}

export async function getPage(slug: string) {
  const { data } = await api.get(`/wiki/pages/${slug}`)
  return data
}

export async function getStats() {
  const { data } = await api.get('/wiki/stats')
  return data
}

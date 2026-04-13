import api from './client'

export async function submitText(text: string, title: string, submittedBy: string) {
  const { data } = await api.post('/sources/text', { text, title, submitted_by: submittedBy })
  return data
}

export async function submitUrl(url: string, submittedBy: string) {
  const { data } = await api.post('/sources/url', { url, submitted_by: submittedBy })
  return data
}

export async function uploadFile(file: File, submittedBy: string, onProgress?: (pct: number) => void) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('submitted_by', submittedBy)
  const { data } = await api.post('/sources/upload', formData, {
    onUploadProgress: e => onProgress?.(Math.round((e.loaded / (e.total || 1)) * 100)),
  })
  return data
}

export async function listSources() {
  const { data } = await api.get('/sources/')
  return data
}

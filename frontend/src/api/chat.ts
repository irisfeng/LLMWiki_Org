import api from './client'

export interface ChatSource {
  index: number
  slug: string
  title: string
  type: string
  score: number
  excerpt: string
  heading?: string
}

export interface StoredChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  // Structured sources; legacy rows (if any) may still be string[].
  referenced_pages: ChatSource[] | string[] | null
}

export async function saveMessageAsAnalysis(messageId: string): Promise<{ slug: string; title: string }> {
  const { data } = await api.post(`/chat/messages/${messageId}/save-as-analysis`)
  return data
}

export function streamChat(content: string, sessionId?: string, userName?: string) {
  const body = JSON.stringify({ content, session_id: sessionId, user_name: userName })
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  return fetch('/api/chat/messages', {
    method: 'POST',
    headers,
    body,
  })
}

export async function getSessionMessages(sessionId: string): Promise<StoredChatMessage[]> {
  const { data } = await api.get(`/chat/sessions/${sessionId}/messages`)
  return data
}

export interface SessionSummary {
  id: string
  user_name: string
  created_at: string
  title: string
  message_count: number
}

export async function listSessions(): Promise<SessionSummary[]> {
  const { data } = await api.get('/chat/sessions')
  return data
}

export async function deleteSession(sessionId: string) {
  const { data } = await api.delete(`/chat/sessions/${sessionId}`)
  return data
}

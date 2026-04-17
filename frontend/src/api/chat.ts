import api from './client'

export interface StoredChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  referenced_pages: string[] | null
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

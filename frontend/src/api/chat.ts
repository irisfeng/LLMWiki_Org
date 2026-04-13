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

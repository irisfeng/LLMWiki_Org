export function streamChat(content: string, sessionId?: string, userName?: string) {
  const body = JSON.stringify({ content, session_id: sessionId, user_name: userName })

  return fetch('/api/chat/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  })
}

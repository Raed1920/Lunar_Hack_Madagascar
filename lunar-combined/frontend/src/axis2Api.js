const API_BASE_URL = import.meta.env.VITE_AXIS2_API_BASE_URL ?? import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export async function sendAxis2Chat(payload) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || 'Failed to send chat message')
  }

  return response.json()
}

export async function fetchAxis2ChatSessions(userId) {
  const response = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(userId)}?limit=40`)
  if (!response.ok) {
    throw new Error('Failed to load chat sessions')
  }
  return response.json()
}

export async function fetchAxis2SessionMessages(userId, sessionId) {
  const response = await fetch(
    `${API_BASE_URL}/sessions/${encodeURIComponent(userId)}/${encodeURIComponent(sessionId)}/messages?limit=300`,
  )
  if (!response.ok) {
    throw new Error('Failed to load session messages')
  }
  return response.json()
}

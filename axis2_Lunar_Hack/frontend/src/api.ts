import type {
  ChatApiRequest,
  ChatApiResponse,
  ChatSessionSummary,
  SessionHistoryMessage
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function sendChat(payload: ChatApiRequest): Promise<ChatApiResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to send chat message");
  }

  return (await response.json()) as ChatApiResponse;
}

export async function fetchChatSessions(userId: string): Promise<ChatSessionSummary[]> {
  const response = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(userId)}?limit=40`);
  if (!response.ok) {
    throw new Error("Failed to load chat sessions");
  }
  return (await response.json()) as ChatSessionSummary[];
}

export async function fetchSessionMessages(userId: string, sessionId: string): Promise<SessionHistoryMessage[]> {
  const response = await fetch(
    `${API_BASE_URL}/sessions/${encodeURIComponent(userId)}/${encodeURIComponent(sessionId)}/messages?limit=300`
  );
  if (!response.ok) {
    throw new Error("Failed to load session messages");
  }
  return (await response.json()) as SessionHistoryMessage[];
}

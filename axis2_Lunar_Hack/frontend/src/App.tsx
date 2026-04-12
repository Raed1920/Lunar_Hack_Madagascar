import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import { fetchChatSessions, fetchSessionMessages, sendChat } from "./api";
import type { ChatMessage, ChatSessionSummary, Language, SessionHistoryMessage } from "./types";

type LocalizedCopy = {
  title: string;
  subtitle: string;
  assistantTag: string;
  userTag: string;
  inputPlaceholder: string;
  sendLabel: string;
  loading: string;
  welcome: string;
  error: string;
  clearChat: string;
  historyTitle: string;
  emptyHistory: string;
  keyboardHint: string;
  languageLabel: string;
};

const COPY: Record<Language, LocalizedCopy> = {
  en: {
    title: "Lunar Hack Chat",
    subtitle: "Dark-mode decision assistant",
    assistantTag: "Assistant",
    userTag: "You",
    inputPlaceholder: "Type your question or decision challenge...",
    sendLabel: "Send",
    loading: "Analyzing your request...",
    welcome: "Tell me what business decision you need help with.",
    error: "Backend unreachable. Please confirm the API is running.",
    clearChat: "New Session",
    historyTitle: "Chat History",
    emptyHistory: "No previous sessions yet",
    keyboardHint: "Enter to send, Shift+Enter for newline.",
    languageLabel: "Language"
  },
  fr: {
    title: "Lunar Hack Chat",
    subtitle: "Assistant de decision en mode sombre",
    assistantTag: "Assistant",
    userTag: "Vous",
    inputPlaceholder: "Ecrivez votre question ou votre decision business...",
    sendLabel: "Envoyer",
    loading: "Analyse en cours...",
    welcome: "Expliquez la decision business pour laquelle vous avez besoin d'aide.",
    error: "Backend indisponible. Verifiez que l'API est active.",
    clearChat: "Nouvelle Session",
    historyTitle: "Historique",
    emptyHistory: "Aucune session precedente",
    keyboardHint: "Entree pour envoyer, Maj+Entree pour nouvelle ligne.",
    languageLabel: "Langue"
  },
  ar: {
    title: "Lunar Hack Chat",
    subtitle: "مساعد قرارات بوضع داكن",
    assistantTag: "المساعد",
    userTag: "انت",
    inputPlaceholder: "اكتب سؤالك او التحدي الخاص بالقرار...",
    sendLabel: "ارسال",
    loading: "جاري التحليل...",
    welcome: "اخبرني بالقرار التجاري الذي تحتاج المساعدة فيه.",
    error: "تعذر الوصول للخلفية. تاكد من تشغيل الـ API.",
    clearChat: "جلسة جديدة",
    historyTitle: "سجل المحادثات",
    emptyHistory: "لا توجد جلسات سابقة",
    keyboardHint: "Enter للارسال وShift+Enter لسطر جديد.",
    languageLabel: "اللغة"
  }
};

function createSessionId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `session-${Date.now()}`;
}

function formatTimestamp(value: number): string {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function isWelcomeMessage(text: string): boolean {
  return Object.values(COPY).some((entry) => entry.welcome === text);
}

function createId(): string {
  const random = Math.random().toString(16).slice(2);
  return `${Date.now()}-${random}`;
}

function formatSessionTimestamp(value: string): string {
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return "";
  }
  return new Date(parsed).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function truncateText(value: string, max = 68): string {
  const text = (value || "").trim();
  if (text.length <= max) {
    return text;
  }
  return `${text.slice(0, max).trim()}...`;
}

function mapHistoryToMessages(history: SessionHistoryMessage[]): ChatMessage[] {
  return history.map((item, index) => ({
    id: `history-${index}-${Date.parse(item.created_at) || Date.now()}`,
    role: item.role === "assistant" ? "assistant" : "user",
    text: item.message,
    createdAt: Date.parse(item.created_at) || Date.now()
  }));
}

function formatSourceLabel(value: string): string {
  const text = (value || "").trim();
  if (!text) {
    return "Knowledge Base";
  }

  const lowered = text.toLowerCase();
  if (lowered.startsWith("dataset:")) {
    const datasetName = text.split(":", 2)[1] ?? "Knowledge Base";
    return datasetName
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase())
      .trim();
  }

  return text
    .replace(/\.(txt|md|pdf|docx|csv|json)$/i, "")
    .replace(/[_-]+/g, " ")
    .trim();
}

function getOrCreateUserId(): string {
  const key = "ai_sales_user_id";
  const existing = window.localStorage.getItem(key);
  if (existing) {
    return existing;
  }

  const generated = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `user-${Date.now()}`;

  window.localStorage.setItem(key, generated);
  return generated;
}

export default function App() {
  const [language, setLanguage] = useState<Language>("en");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: createId(),
      role: "assistant",
      text: COPY.en.welcome,
      createdAt: Date.now()
    }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);

  const [sessionId, setSessionId] = useState<string>(() => createSessionId());
  const [userId] = useState<string>(() => getOrCreateUserId());
  const messageListRef = useRef<HTMLDivElement | null>(null);

  const copy = useMemo(() => COPY[language], [language]);

  useEffect(() => {
    if (!messageListRef.current) {
      return;
    }
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
  }, [messages, isLoading]);

  useEffect(() => {
    setMessages((prev) => {
      if (
        prev.length === 1
        && prev[0].role === "assistant"
        && isWelcomeMessage(prev[0].text)
      ) {
        return [{ ...prev[0], text: COPY[language].welcome }];
      }
      return prev;
    });
  }, [language]);

  useEffect(() => {
    let isActive = true;

    async function bootstrapHistory(): Promise<void> {
      setIsHistoryLoading(true);
      try {
        const sessionList = await fetchChatSessions(userId);
        if (!isActive) {
          return;
        }

        setSessions(sessionList);
        if (sessionList.length === 0) {
          return;
        }

        const latestSession = sessionList[0].session_id;
        setSessionId(latestSession);
        const history = await fetchSessionMessages(userId, latestSession);
        if (!isActive) {
          return;
        }
        if (history.length > 0) {
          setMessages(mapHistoryToMessages(history));
        }
      } catch {
        if (!isActive) {
          return;
        }
        setSessions([]);
      } finally {
        if (isActive) {
          setIsHistoryLoading(false);
        }
      }
    }

    void bootstrapHistory();
    return () => {
      isActive = false;
    };
  }, [userId]);

  async function refreshSessionList(preferredSessionId?: string): Promise<void> {
    try {
      const sessionList = await fetchChatSessions(userId);
      setSessions(sessionList);
      if (preferredSessionId && sessionList.some((item) => item.session_id === preferredSessionId)) {
        setSessionId(preferredSessionId);
      }
    } catch {
      // Keep current UI state if history refresh fails.
    }
  }

  async function pushMessage(rawMessage: string): Promise<void> {
    const message = rawMessage.trim();
    if (!message || isLoading) {
      return;
    }

    const userBubble: ChatMessage = {
      id: createId(),
      role: "user",
      text: message,
      createdAt: Date.now()
    };

    setMessages((prev) => [...prev, userBubble]);
    setInput("");
    setIsLoading(true);

    try {
      const data = await sendChat({
        user_id: userId,
        session_id: sessionId,
        message,
        language
      });

      setMessages((prev) => [
        ...prev,
        {
          id: createId(),
          role: "assistant",
          text: data.response,
          createdAt: Date.now(),
          rag_sources: data.rag_sources
        }
      ]);
      await refreshSessionList(sessionId);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: createId(),
          role: "assistant",
          text: copy.error,
          createdAt: Date.now()
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  async function openSession(targetSessionId: string): Promise<void> {
    if (!targetSessionId || targetSessionId === sessionId || isLoading) {
      return;
    }

    setIsHistoryLoading(true);
    try {
      const history = await fetchSessionMessages(userId, targetSessionId);
      setSessionId(targetSessionId);
      if (history.length === 0) {
        setMessages([
          {
            id: createId(),
            role: "assistant",
            text: COPY[language].welcome,
            createdAt: Date.now()
          }
        ]);
      } else {
        setMessages(mapHistoryToMessages(history));
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: createId(),
          role: "assistant",
          text: copy.error,
          createdAt: Date.now()
        }
      ]);
    } finally {
      setIsHistoryLoading(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void pushMessage(input);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isLoading && input.trim()) {
        void pushMessage(input);
      }
    }
  }

  function resetConversation(): void {
    const nextSessionId = createSessionId();
    setMessages([
      {
        id: createId(),
        role: "assistant",
        text: COPY[language].welcome,
        createdAt: Date.now()
      }
    ]);
    setInput("");
    setSessionId(nextSessionId);
  }

  return (
    <div className={`app ${language === "ar" ? "rtl" : ""}`} dir={language === "ar" ? "rtl" : "ltr"}>
      <div className="ambient" />

      <header className="topbar">
        <div className="title-wrap">
          <span className="eyebrow">Lunar-Hack Dark Ops</span>
          <h1>{copy.title}</h1>
          <p>{copy.subtitle}</p>
        </div>
        <div className="top-controls">
          <label className="lang-picker">
            <span>{copy.languageLabel}</span>
            <select value={language} onChange={(event) => setLanguage(event.target.value as Language)}>
              <option value="en">English</option>
              <option value="fr">Francais</option>
              <option value="ar">العربية</option>
            </select>
          </label>
        </div>
      </header>

      <main className="layout">
        <aside className="history-shell">
          <div className="history-head">
            <h2>{copy.historyTitle}</h2>
            <button type="button" className="ghost-btn" onClick={resetConversation}>
              {copy.clearChat}
            </button>
          </div>

          <div className="history-list">
            {isHistoryLoading ? (
              <p className="history-empty">{copy.loading}</p>
            ) : null}

            {!isHistoryLoading && sessions.length === 0 ? (
              <p className="history-empty">{copy.emptyHistory}</p>
            ) : null}

            {!isHistoryLoading && sessions.map((session) => (
              <button
                key={session.session_id}
                type="button"
                className={`history-item ${session.session_id === sessionId ? "active" : ""}`}
                onClick={() => {
                  void openSession(session.session_id);
                }}
              >
                <div className="history-item-top">
                  <strong>{formatSessionTimestamp(session.last_created_at) || session.session_id.slice(0, 8)}</strong>
                  <span>{session.message_count}</span>
                </div>
                <p>{truncateText(session.last_message)}</p>
              </button>
            ))}
          </div>
        </aside>

        <section className="chat-shell">
          <div className="message-list" ref={messageListRef}>
            {messages.map((message, index) => (
              <article
                key={message.id}
                className={`bubble ${message.role}`}
                style={{ animationDelay: `${index * 45}ms` }}
              >
                <div className="bubble-meta">
                  <span className="bubble-role">
                    {message.role === "assistant" ? copy.assistantTag : copy.userTag}
                  </span>
                  <time>{formatTimestamp(message.createdAt)}</time>
                </div>
                <p>{message.text}</p>
                {message.role === "assistant" && message.rag_sources && message.rag_sources.length > 0 ? (
                  <div className="source-strip">
                    <span className="source-label">Sources</span>
                    <div className="source-chips">
                      {message.rag_sources.map((source) => (
                        <span key={`${message.id}-${source}`} className="source-chip">
                          {formatSourceLabel(source)}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </article>
            ))}

            {isLoading ? (
              <div className="loading-state">
                <div className="typing-dots">
                  <span />
                  <span />
                  <span />
                </div>
                <p>{copy.loading}</p>
              </div>
            ) : null}
          </div>

          <form className="composer" onSubmit={handleSubmit}>
            <div className="composer-row">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                rows={2}
                placeholder={copy.inputPlaceholder}
              />
              <button type="submit" disabled={isLoading || !input.trim()}>
                {copy.sendLabel}
              </button>
            </div>
            <small className="composer-hint">{copy.keyboardHint}</small>
          </form>
        </section>
      </main>
    </div>
  );
}

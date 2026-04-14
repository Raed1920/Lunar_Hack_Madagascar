import { useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchAxis2ChatSessions,
  fetchAxis2SessionMessages,
  sendAxis2Chat,
} from './axis2Api'
import './Axis2ChatTab.css'

const COPY = {
  en: {
    title: 'Sa3ed Chat',
    subtitle: 'Decision assistant from Axis 2',
    assistantTag: 'Assistant',
    userTag: 'You',
    inputPlaceholder: 'Type your question or decision challenge...',
    sendLabel: 'Send',
    loading: 'Analyzing your request...',
    welcome: 'Tell me what business decision you need help with.',
    error: 'Backend unreachable. Please confirm the API is running.',
    clearChat: 'New Session',
    historyTitle: 'Chat History',
    emptyHistory: 'No previous sessions yet',
    keyboardHint: 'Enter to send, Shift+Enter for newline.',
    languageLabel: 'Language',
  },
  fr: {
    title: 'Sa3ed Chat',
    subtitle: 'Assistant de decision depuis Axis 2',
    assistantTag: 'Assistant',
    userTag: 'Vous',
    inputPlaceholder: 'Ecrivez votre question ou votre decision business...',
    sendLabel: 'Envoyer',
    loading: 'Analyse en cours...',
    welcome: "Expliquez la decision business pour laquelle vous avez besoin d'aide.",
    error: "Backend indisponible. Verifiez que l'API est active.",
    clearChat: 'Nouvelle Session',
    historyTitle: 'Historique',
    emptyHistory: 'Aucune session precedente',
    keyboardHint: 'Entree pour envoyer, Maj+Entree pour nouvelle ligne.',
    languageLabel: 'Langue',
  },
  ar: {
    title: 'Sa3ed Chat',
    subtitle: 'Axis 2 chat assistant',
    assistantTag: 'Assistant',
    userTag: 'You',
    inputPlaceholder: 'Type your question...',
    sendLabel: 'Send',
    loading: 'Analyzing...',
    welcome: 'Tell me what business decision you need help with.',
    error: 'Backend unreachable. Please confirm the API is running.',
    clearChat: 'New Session',
    historyTitle: 'Chat History',
    emptyHistory: 'No previous sessions yet',
    keyboardHint: 'Enter to send, Shift+Enter for newline.',
    languageLabel: 'Language',
  },
}

function createSessionId() {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `session-${Date.now()}`
}

function createId() {
  const random = Math.random().toString(16).slice(2)
  return `${Date.now()}-${random}`
}

function formatTimestamp(value) {
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatSessionTimestamp(value) {
  const parsed = Date.parse(value)
  if (Number.isNaN(parsed)) return ''
  return new Date(parsed).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function truncateText(value, max = 68) {
  const text = (value || '').trim()
  if (text.length <= max) return text
  return `${text.slice(0, max).trim()}...`
}

function mapHistoryToMessages(history) {
  return history.map((item, index) => ({
    id: `history-${index}-${Date.parse(item.created_at) || Date.now()}`,
    role: item.role === 'assistant' ? 'assistant' : 'user',
    text: item.message,
    createdAt: Date.parse(item.created_at) || Date.now(),
  }))
}

function formatSourceLabel(value) {
  const text = (value || '').trim()
  if (!text) return 'Knowledge Base'

  const lowered = text.toLowerCase()
  if (lowered.startsWith('dataset:')) {
    const datasetName = text.split(':', 2)[1] ?? 'Knowledge Base'
    return datasetName
      .replace(/[_-]+/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase())
      .trim()
  }

  return text
    .replace(/\.(txt|md|pdf|docx|csv|json)$/i, '')
    .replace(/[_-]+/g, ' ')
    .trim()
}

function getOrCreateUserId() {
  const key = 'ai_sales_user_id'
  const existing = window.localStorage.getItem(key)
  if (existing) return existing

  const generated = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `user-${Date.now()}`

  window.localStorage.setItem(key, generated)
  return generated
}

export default function Axis2ChatTab() {
  const [language, setLanguage] = useState('en')
  const [messages, setMessages] = useState([
    {
      id: createId(),
      role: 'assistant',
      text: COPY.en.welcome,
      createdAt: Date.now(),
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isHistoryLoading, setIsHistoryLoading] = useState(false)
  const [sessions, setSessions] = useState([])
  const [sessionId, setSessionId] = useState(() => createSessionId())
  const [userId] = useState(() => getOrCreateUserId())

  const messageListRef = useRef(null)
  const copy = useMemo(() => COPY[language], [language])

  useEffect(() => {
    if (!messageListRef.current) return
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight
  }, [messages, isLoading])

  useEffect(() => {
    let isActive = true

    async function bootstrapHistory() {
      setIsHistoryLoading(true)
      try {
        const sessionList = await fetchAxis2ChatSessions(userId)
        if (!isActive) return
        setSessions(sessionList)

        if (sessionList.length === 0) return

        const latestSession = sessionList[0].session_id
        setSessionId(latestSession)
        const history = await fetchAxis2SessionMessages(userId, latestSession)
        if (!isActive) return
        if (history.length > 0) setMessages(mapHistoryToMessages(history))
      } catch {
        if (!isActive) return
        setSessions([])
      } finally {
        if (isActive) setIsHistoryLoading(false)
      }
    }

    void bootstrapHistory()
    return () => {
      isActive = false
    }
  }, [userId])

  async function refreshSessionList(preferredSessionId) {
    try {
      const sessionList = await fetchAxis2ChatSessions(userId)
      setSessions(sessionList)
      if (preferredSessionId && sessionList.some((item) => item.session_id === preferredSessionId)) {
        setSessionId(preferredSessionId)
      }
    } catch {
      // Keep current UI state if history refresh fails.
    }
  }

  async function pushMessage(rawMessage) {
    const message = rawMessage.trim()
    if (!message || isLoading) return

    const userBubble = {
      id: createId(),
      role: 'user',
      text: message,
      createdAt: Date.now(),
    }

    setMessages((prev) => [...prev, userBubble])
    setInput('')
    setIsLoading(true)

    try {
      const data = await sendAxis2Chat({
        user_id: userId,
        session_id: sessionId,
        message,
        language,
      })

      setMessages((prev) => [
        ...prev,
        {
          id: createId(),
          role: 'assistant',
          text: data.response,
          createdAt: Date.now(),
          rag_sources: Array.isArray(data.rag_sources) ? data.rag_sources : [],
        },
      ])

      await refreshSessionList(sessionId)
    } catch (err) {
      const details = err instanceof Error && err.message ? err.message : copy.error
      setMessages((prev) => [
        ...prev,
        {
          id: createId(),
          role: 'assistant',
          text: details,
          createdAt: Date.now(),
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  async function openSession(targetSessionId) {
    if (!targetSessionId || targetSessionId === sessionId || isLoading) return

    setIsHistoryLoading(true)
    try {
      const history = await fetchAxis2SessionMessages(userId, targetSessionId)
      setSessionId(targetSessionId)
      if (history.length === 0) {
        setMessages([
          {
            id: createId(),
            role: 'assistant',
            text: COPY[language].welcome,
            createdAt: Date.now(),
          },
        ])
      } else {
        setMessages(mapHistoryToMessages(history))
      }
    } catch (err) {
      const details = err instanceof Error && err.message ? err.message : copy.error
      setMessages((prev) => [
        ...prev,
        {
          id: createId(),
          role: 'assistant',
          text: details,
          createdAt: Date.now(),
        },
      ])
    } finally {
      setIsHistoryLoading(false)
    }
  }

  function handleSubmit(event) {
    event.preventDefault()
    void pushMessage(input)
  }

  function handleComposerKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (!isLoading && input.trim()) void pushMessage(input)
    }
  }

  function resetConversation() {
    const nextSessionId = createSessionId()
    setMessages([
      {
        id: createId(),
        role: 'assistant',
        text: COPY[language].welcome,
        createdAt: Date.now(),
      },
    ])
    setInput('')
    setSessionId(nextSessionId)
  }

  return (
    <div className="axis2-tab" dir={language === 'ar' ? 'rtl' : 'ltr'}>
      <header className="axis2-topbar">
        <div className="axis2-title-wrap">
          <span className="axis2-eyebrow">Axis 2</span>
          <h1>{copy.title}</h1>
          <p>{copy.subtitle}</p>
        </div>
        <label className="axis2-lang-picker">
          <span>{copy.languageLabel}</span>
          <select value={language} onChange={(event) => setLanguage(event.target.value)}>
            <option value="en">English</option>
            <option value="fr">Francais</option>
            <option value="ar">Arabic</option>
          </select>
        </label>
      </header>

      <main className="axis2-layout">
        <aside className="axis2-history-shell">
          <div className="axis2-history-head">
            <h2>{copy.historyTitle}</h2>
            <button type="button" className="axis2-ghost-btn" onClick={resetConversation}>
              {copy.clearChat}
            </button>
          </div>

          <div className="axis2-history-list">
            {isHistoryLoading ? <p className="axis2-history-empty">{copy.loading}</p> : null}
            {!isHistoryLoading && sessions.length === 0 ? (
              <p className="axis2-history-empty">{copy.emptyHistory}</p>
            ) : null}

            {!isHistoryLoading && sessions.map((session) => (
              <button
                key={session.session_id}
                type="button"
                className={`axis2-history-item ${session.session_id === sessionId ? 'active' : ''}`}
                onClick={() => {
                  void openSession(session.session_id)
                }}
              >
                <div className="axis2-history-item-top">
                  <strong>{formatSessionTimestamp(session.last_created_at) || session.session_id.slice(0, 8)}</strong>
                  <span>{session.message_count}</span>
                </div>
                <p>{truncateText(session.last_message)}</p>
              </button>
            ))}
          </div>
        </aside>

        <section className="axis2-chat-shell">
          <div className="axis2-message-list" ref={messageListRef}>
            {messages.map((message, index) => (
              <article
                key={message.id}
                className={`axis2-bubble ${message.role}`}
                style={{ animationDelay: `${index * 45}ms` }}
              >
                <div className="axis2-bubble-meta">
                  <span className="axis2-bubble-role">
                    {message.role === 'assistant' ? copy.assistantTag : copy.userTag}
                  </span>
                  <time>{formatTimestamp(message.createdAt)}</time>
                </div>
                <p>{message.text}</p>
                {message.role === 'assistant' && message.rag_sources && message.rag_sources.length > 0 ? (
                  <div className="axis2-source-strip">
                    <span className="axis2-source-label">Sources</span>
                    <div className="axis2-source-chips">
                      {message.rag_sources.map((source) => (
                        <span key={`${message.id}-${source}`} className="axis2-source-chip">
                          {formatSourceLabel(source)}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </article>
            ))}

            {isLoading ? (
              <div className="axis2-loading-state">
                <div className="axis2-typing-dots"><span /><span /><span /></div>
                <p>{copy.loading}</p>
              </div>
            ) : null}
          </div>

          <form className="axis2-composer" onSubmit={handleSubmit}>
            <div className="axis2-composer-row">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                rows={2}
                placeholder={copy.inputPlaceholder}
              />
              <button type="submit" disabled={isLoading || !input.trim()}>{copy.sendLabel}</button>
            </div>
            <small>{copy.keyboardHint}</small>
          </form>
        </section>
      </main>
    </div>
  )
}

import { useMemo, useState } from 'react'
import './Pillar3QualityTab.css'

const DEFAULT_WORKSPACE_ID = '11111111-1111-1111-1111-111111111111'
const DEFAULT_MESSAGE = 'I want to promote my artisan bread in Tunis for 2 weeks with a 100-800 TND budget.'
const WORKSPACE_ID = (import.meta.env.VITE_PILLAR3_WORKSPACE_ID ?? DEFAULT_WORKSPACE_ID).trim() || DEFAULT_WORKSPACE_ID

function getApiBase() {
  const raw = import.meta.env.VITE_PILLAR3_API_BASE_URL ?? '/pillar3-api'
  return String(raw).trim().replace(/\/+$/, '')
}

const API_BASE = getApiBase()

function parseErrorMessage(payload, fallback) {
  if (!payload) return fallback
  if (typeof payload === 'string') return payload
  if (typeof payload?.detail === 'string') return payload.detail
  if (typeof payload?.message === 'string') return payload.message
  return fallback
}

function readImageDimensions(file) {
  return new Promise((resolve) => {
    const objectUrl = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(objectUrl)
      resolve({ width: img.width, height: img.height })
    }
    img.onerror = () => {
      URL.revokeObjectURL(objectUrl)
      resolve({ width: null, height: null })
    }
    img.src = objectUrl
  })
}

function readImageBase64(file) {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = String(reader.result || '')
      const parts = dataUrl.split(',')
      resolve(parts.length > 1 ? parts[1] : null)
    }
    reader.onerror = () => resolve(null)
    reader.readAsDataURL(file)
  })
}

async function buildImageMeta(file) {
  const baseMeta = {
    filename: file.name,
    mime_type: file.type || null,
    size_bytes: file.size || null,
    width: null,
    height: null,
    notes: null,
    data_base64: null,
  }

  if (!String(file.type || '').startsWith('image/')) {
    return baseMeta
  }

  const [dims, dataBase64] = await Promise.all([
    readImageDimensions(file),
    readImageBase64(file),
  ])

  return {
    ...baseMeta,
    width: dims.width,
    height: dims.height,
    data_base64: dataBase64,
  }
}

export default function Pillar3QualityTab() {
  const [message, setMessage] = useState(DEFAULT_MESSAGE)
  const [submittedMessage, setSubmittedMessage] = useState('')
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [chatEnvelope, setChatEnvelope] = useState(null)

  const questions = useMemo(() => {
    const list = Array.isArray(chatEnvelope?.clarifying_questions)
      ? chatEnvelope.clarifying_questions
      : []
    return list.filter((item) => String(item || '').trim())
  }, [chatEnvelope])

  const showClarification = chatEnvelope?.status === 'question_asked'

  async function onImagesChange(event) {
    const files = Array.from(event.target.files || [])
    const metas = await Promise.all(files.map(buildImageMeta))
    setImages(metas)
  }

  async function submit() {
    if (!message.trim() || loading) return

    setLoading(true)
    setError('')

    try {
      const payload = {
        message,
        workspace_id: WORKSPACE_ID,
        images,
      }

      const response = await fetch(`${API_BASE}/v1/marketing/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      const contentType = response.headers.get('content-type') || ''
      const data = contentType.includes('application/json') ? await response.json() : await response.text()

      if (!response.ok) {
        throw new Error(parseErrorMessage(data, 'Generation failed'))
      }

      setSubmittedMessage(message.trim())
      setChatEnvelope(data)
    } catch (err) {
      setError(String(err?.message || err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p3-shell">
      <section className="p3-panel">
        <h1>Pillar 3 Quality Chat Test</h1>
        <p className="p3-muted">User-facing chat preview only.</p>

        <div className="p3-field">
          <label>Your message</label>
          <textarea value={message} onChange={(event) => setMessage(event.target.value)} />
        </div>

        <div className="p3-field">
          <label>Optional images</label>
          <input type="file" accept="image/*" multiple onChange={onImagesChange} />
        </div>

        <div className="p3-actions">
          <button type="button" onClick={submit} disabled={loading || !message.trim()}>
            {loading ? 'Sending...' : 'Send'}
          </button>
        </div>

        {error ? <div className="p3-error">{error}</div> : null}
      </section>

      <section className="p3-panel">
        <h2>Conversation</h2>
        <div className="p3-chat-window">
          {!chatEnvelope && !loading ? (
            <p className="p3-muted">The assistant reply appears here after you send a message.</p>
          ) : null}

          {submittedMessage ? <div className="p3-bubble p3-user">{submittedMessage}</div> : null}

          {chatEnvelope?.assistant_message ? (
            <div className="p3-bubble p3-assistant">{chatEnvelope.assistant_message}</div>
          ) : null}

          {showClarification ? (
            <div className="p3-clarification-box">
              <h3>Please clarify</h3>
              {questions.length > 0 ? (
                <ol>
                  {questions.map((question, index) => (
                    <li key={`${index}-${question}`}>{question}</li>
                  ))}
                </ol>
              ) : (
                <div>{chatEnvelope?.assistant_message || 'Could you share more details so I can generate your plan?'}</div>
              )}
            </div>
          ) : null}
        </div>
      </section>
    </div>
  )
}

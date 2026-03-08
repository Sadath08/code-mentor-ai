import { useState, useRef, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const TOPICS = [
  'Recursion', 'Arrays', 'Dynamic Programming', 'Trees', 'Binary Search',
  'Sorting', 'Graphs', 'Linked Lists', 'Hashing', 'OOP',
  'SQL', 'Operating Systems', 'Pointers', 'Quicksort', 'Stacks & Queues',
]

const SECTION_META = [
  { key: 'definition', icon: '📖', label: 'Definition' },
  { key: 'layman', icon: '🧒', label: 'Simple Explanation' },
  { key: 'how_it_works', icon: '⚙️', label: 'How It Works' },
  { key: 'code_example', icon: '💻', label: 'Code Example' },
  { key: 'complexity', icon: '📊', label: 'Complexity' },
  { key: 'real_world_uses', icon: '🌍', label: 'Real World Uses' },
  { key: 'common_mistakes', icon: '⚠️', label: 'Common Mistakes' },
  { key: 'interview_questions', icon: '🎯', label: 'Interview Questions' },
  { key: 'quick_revision', icon: '📝', label: 'Quick Revision' },
  { key: 'related_topics', icon: '🔗', label: 'Related Topics' },
]

// Render an individual section value
function SectionContent({ sectionKey, value }) {
  if (!value) return null

  if (sectionKey === 'code_example' && typeof value === 'object') {
    return (
      <div>
        <pre style={st.code}><code>{value.code}</code></pre>
        {value.explanation && <p style={st.codeNote}>{value.explanation}</p>}
      </div>
    )
  }

  if (sectionKey === 'complexity' && typeof value === 'object') {
    return (
      <div style={st.complexRow}>
        {value.time && <span style={st.complexBadge}>🕐 Time: <b>{value.time}</b></span>}
        {value.space && <span style={st.complexBadge}>💾 Space: <b>{value.space}</b></span>}
      </div>
    )
  }

  if (Array.isArray(value)) {
    return (
      <ul style={st.list}>
        {value.map((item, i) => (
          <li key={i} style={st.listItem}>{item}</li>
        ))}
      </ul>
    )
  }

  return <p style={st.bodyText}>{value}</p>
}

// Full structured response card
function ConceptCard({ data, question }) {
  if (!data) return null

  return (
    <div style={st.card}>
      <div style={st.cardHeader}>
        <span style={st.cardEmoji}>🤖</span>
        <div>
          <p style={st.cardQ}>You asked: <em>"{question}"</em></p>
        </div>
      </div>

      {SECTION_META.map(({ key, icon, label }) => {
        const val = data[key]
        if (!val || (Array.isArray(val) && val.length === 0)) return null
        return (
          <div key={key} style={st.section}>
            <h4 style={st.sectionTitle}>{icon} {label}</h4>
            <SectionContent sectionKey={key} value={val} />
          </div>
        )
      })}
    </div>
  )
}

// Loading skeleton card
function LoadingCard() {
  return (
    <div style={{ ...st.card, opacity: 0.7 }}>
      <div style={st.cardHeader}>
        <span style={st.cardEmoji}>🤖</span>
        <div>
          <p style={st.cardQ}>Thinking…</p>
          <div style={st.shimmerBar} />
          <div style={{ ...st.shimmerBar, width: '60%' }} />
        </div>
      </div>
    </div>
  )
}

export default function AskQuestions() {
  const [input, setInput] = useState('')
  const [history, setHistory] = useState([])   // [{question, data, error}]
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, loading])

  const ask = async (question) => {
    const q = question.trim()
    if (!q || loading) return
    setInput('')
    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/api/ask/concept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, language: 'python' }),
      })
      const json = await res.json()
      setHistory(prev => [...prev, { question: q, data: json, error: null }])
    } catch (e) {
      setHistory(prev => [...prev, { question: q, data: null, error: 'Failed to get answer. Please try again.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={st.page}>

      {/* ── Header ─────────────────────────────────────────────── */}
      <div style={st.header}>
        <div>
          <h1 style={st.title}>💬 Ask Questions</h1>
          <p style={st.subtitle}>Get deep explanations on any CS topic — definitions, code, complexity & interview tips</p>
        </div>
      </div>

      {/* ── Topic chips ─────────────────────────────────────────── */}
      <div style={st.topicsWrap}>
        <span style={st.topicsLabel}>Popular Topics:</span>
        <div style={st.chips}>
          {TOPICS.map(t => (
            <button
              key={t}
              style={st.chip}
              onClick={() => setInput(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* ── Conversation area ────────────────────────────────────── */}
      <div style={st.feed}>
        {history.length === 0 && !loading && (
          <div style={st.welcome}>
            <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>🤖</div>
            <p style={st.welcomeText}>
              Hi! Ask me any CS concept and I'll give you a <b>structured explanation</b> with
              examples, complexity and interview tips.
            </p>
            <p style={{ color: '#94a3b8', fontSize: '0.82rem' }}>Try: "What is recursion?" or click a topic above</p>
          </div>
        )}

        {history.map((item, i) => (
          <div key={i}>
            {/* User bubble */}
            <div style={st.userBubbleWrap}>
              <div style={st.userBubble}>👤 {item.question}</div>
            </div>

            {item.error
              ? <div style={st.errorCard}>⚠️ {item.error}</div>
              : <ConceptCard data={item.data} question={item.question} />
            }
          </div>
        ))}

        {loading && (
          <>
            <div style={st.userBubbleWrap}>
              <div style={st.userBubble}>👤 {input || '…'}</div>
            </div>
            <LoadingCard />
          </>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input ───────────────────────────────────────────────── */}
      <div style={st.inputRow}>
        <input
          style={st.input}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(input) } }}
          placeholder="Ask any CS concept… e.g. What is dynamic programming?"
          disabled={loading}
        />
        <button
          style={{ ...st.sendBtn, opacity: loading ? 0.55 : 1 }}
          disabled={loading}
          onClick={() => ask(input)}
        >
          {loading ? '⏳' : 'Ask →'}
        </button>
      </div>
    </div>
  )
}

// ── Styles ─────────────────────────────────────────────────────────────────────
const st = {
  page: {
    maxWidth: 900, margin: '0 auto', padding: '1.5rem 2rem 7rem',
    fontFamily: 'Inter, system-ui, sans-serif', minHeight: '100vh',
  },
  header: { marginBottom: '1rem' },
  title: { margin: 0, fontSize: '1.55rem', fontWeight: 800, color: '#0f172a' },
  subtitle: { margin: '0.3rem 0 0', color: '#64748b', fontSize: '0.84rem' },

  topicsWrap: {
    display: 'flex', flexWrap: 'wrap', gap: '0.5rem',
    alignItems: 'center', marginBottom: '1rem',
    padding: '0.75rem 1rem', background: '#f8fafc',
    borderRadius: '10px', border: '1px solid #e2e8f0',
  },
  topicsLabel: { fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', whiteSpace: 'nowrap' },
  chips: { display: 'flex', flexWrap: 'wrap', gap: '0.4rem' },
  chip: {
    background: 'white', border: '1px solid #e2e8f0', borderRadius: '20px',
    padding: '0.3rem 0.85rem', fontSize: '0.77rem', color: '#3b82f6',
    fontWeight: 600, cursor: 'pointer', transition: 'all .15s',
  },

  feed: { display: 'flex', flexDirection: 'column', gap: '1.5rem', paddingBottom: '1rem' },

  welcome: {
    textAlign: 'center', margin: 'auto', padding: '2rem',
    background: '#f8fafc', borderRadius: '16px', border: '1px dashed #e2e8f0',
  },
  welcomeText: { color: '#475569', fontSize: '0.95rem', lineHeight: 1.7, margin: '0 0 0.5rem' },

  userBubbleWrap: { display: 'flex', justifyContent: 'flex-end' },
  userBubble: {
    background: 'linear-gradient(135deg,#3b82f6,#6366f1)',
    color: 'white', padding: '0.75rem 1.25rem',
    borderRadius: '18px 18px 4px 18px', maxWidth: '65%',
    fontSize: '0.9rem', fontWeight: 600,
  },

  card: {
    background: 'white', borderRadius: '14px',
    border: '1px solid #e2e8f0', boxShadow: '0 2px 12px rgba(0,0,0,0.05)',
    overflow: 'visible', width: '100%',
  },
  cardHeader: {
    display: 'flex', gap: '0.75rem', alignItems: 'flex-start',
    padding: '1rem 1.25rem', background: 'linear-gradient(135deg,#f0fdf4,#eff6ff)',
    borderBottom: '1px solid #e2e8f0',
  },
  cardEmoji: { fontSize: '1.8rem' },
  cardQ: { margin: 0, fontSize: '0.82rem', color: '#475569' },

  section: {
    padding: '1.1rem 1.5rem', borderBottom: '1px solid #f1f5f9',
  },
  sectionTitle: {
    margin: '0 0 0.6rem', fontSize: '0.92rem',
    fontWeight: 700, color: '#1e293b', letterSpacing: '0.01em',
  },
  bodyText: { margin: 0, color: '#334155', fontSize: '0.92rem', lineHeight: 1.8 },
  list: { margin: '0.25rem 0 0', paddingLeft: '1.4rem' },
  listItem: { color: '#334155', fontSize: '0.9rem', lineHeight: 1.9, marginBottom: '0.2rem' },

  code: {
    background: '#0f172a', color: '#86efac', borderRadius: '10px',
    padding: '1rem 1.25rem', fontSize: '0.83rem', lineHeight: 1.7,
    overflowX: 'auto', overflowY: 'visible',
    margin: '0 0 0.5rem', whiteSpace: 'pre', wordBreak: 'normal',
  },
  codeNote: { margin: '0.25rem 0 0', color: '#64748b', fontSize: '0.8rem', fontStyle: 'italic' },

  complexRow: { display: 'flex', gap: '0.75rem', flexWrap: 'wrap' },
  complexBadge: {
    background: '#f0fdf4', border: '1px solid #bbf7d0',
    borderRadius: '8px', padding: '0.3rem 0.75rem',
    fontSize: '0.82rem', color: '#065f46',
  },

  errorCard: {
    background: '#fff1f2', border: '1px solid #fecdd3',
    borderRadius: '10px', padding: '1rem 1.25rem',
    color: '#be123c', fontSize: '0.85rem',
  },

  shimmerBar: {
    height: 10, borderRadius: 4, background: 'linear-gradient(90deg,#e2e8f0,#f1f5f9,#e2e8f0)',
    marginTop: 8, width: '80%', animation: 'shimmer 1.5s infinite',
  },

  inputRow: {
    position: 'fixed', bottom: 0, left: 0, right: 0,
    display: 'flex', gap: '0.75rem', alignItems: 'center',
    padding: '0.85rem 1.5rem', background: 'white',
    borderTop: '1px solid #e2e8f0',
    boxShadow: '0 -4px 24px rgba(0,0,0,0.06)',
    zIndex: 100,
  },
  input: {
    flex: 1, padding: '0.85rem 1.25rem', borderRadius: '12px',
    border: '1px solid #e2e8f0', fontSize: '0.9rem',
    outline: 'none', fontFamily: 'inherit',
  },
  sendBtn: {
    background: 'linear-gradient(135deg,#3b82f6,#6366f1)', color: 'white',
    border: 'none', borderRadius: '12px', padding: '0 1.5rem',
    fontSize: '0.9rem', cursor: 'pointer', fontWeight: 700, whiteSpace: 'nowrap',
  },
}

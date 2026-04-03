import { useState, useRef, useEffect, useCallback } from 'react'
import './App.css'

const API = 'http://localhost:8000'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(isoString) {
  if (!isoString) return ''
  const diff = (Date.now() - new Date(isoString)) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function getVerdictClass(verdict = '') {
  const v = verdict.toLowerCase()
  if (v.includes('fake') || v.includes('misleading') || v.includes('false')) return 'danger'
  if (v.includes('suspicious') || v.includes('unverified') || v.includes('exaggerated')) return 'warning'
  return 'safe'
}

function getRiskClass(level = '') {
  const map = { Critical: 'risk-critical', High: 'risk-high', Medium: 'risk-medium', Low: 'risk-low' }
  return map[level] || 'risk-low'
}

function getRiskColor(score) {
  if (score > 0.7) return 'var(--danger)'
  if (score > 0.45) return 'var(--warning)'
  return 'var(--success)'
}

const CATEGORIES = [
  { key: null, label: 'All' },
  { key: 'technology', label: '💻 Tech' },
  { key: 'business', label: '📈 Business' },
  { key: 'health', label: '🏥 Health' },
  { key: 'science', label: '🔬 Science' },
  { key: 'entertainment', label: '🎬 Entertainment' },
]

// ─── Sub-components ───────────────────────────────────────────────────────────

function NewsFeedPanel({ onVerifyHeadline }) {
  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeCategory, setActiveCategory] = useState(null)

  const loadNews = useCallback(async (category) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ country: 'in', page_size: 12 })
      if (category) params.set('category', category)
      const res = await fetch(`${API}/api/news-feed?${params}`)
      const data = await res.json()
      setArticles(data.articles || [])
    } catch {
      setArticles([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadNews(activeCategory) }, [activeCategory, loadNews])

  return (
    <aside className="panel panel-news">
      <div className="panel-header">
        <span className="panel-title">
          <span className="panel-icon">📡</span> Live News Feed
        </span>
        <button
          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '0.7rem', cursor: 'pointer' }}
          onClick={() => loadNews(activeCategory)}
          title="Refresh"
        >↻ Refresh</button>
      </div>

      <div className="news-category-tabs">
        {CATEGORIES.map(c => (
          <button
            key={c.label}
            className={`cat-tab ${activeCategory === c.key ? 'active' : ''}`}
            onClick={() => setActiveCategory(c.key)}
          >{c.label}</button>
        ))}
      </div>

      <div className="panel-body">
        {loading ? (
          <div className="news-loading">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="news-skeleton" style={{ animationDelay: `${i * 0.1}s` }} />
            ))}
          </div>
        ) : articles.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            No articles found.
          </div>
        ) : (
          articles.map((a, i) => (
            <div
              key={i}
              className="news-card"
              style={{ animationDelay: `${i * 0.04}s` }}
            >
              <div className="news-card-source">{a.source}</div>
              <div className="news-card-title">{a.title}</div>
              {a.description && <div className="news-card-desc">{a.description}</div>}
              <div className="news-card-footer">
                <span className="news-card-time">{timeAgo(a.published_at)}</span>
                <button
                  id={`verify-news-${i}`}
                  className="news-card-verify-btn"
                  onClick={() => onVerifyHeadline(a.title)}
                >🔍 Verify</button>
              </div>
            </div>
          ))
        )}
      </div>
    </aside>
  )
}


function VerdictCard({ data }) {
  const vc = getVerdictClass(data.final_verdict)
  const score = data.pattern_analysis?.score ?? 0
  const propScore = data.propaganda_analysis?.propaganda_risk_score ?? 0
  const liveNews = data.live_news_context || []

  const verdictIcons = { safe: '✅', warning: '⚠️', danger: '🚨' }

  return (
    <div className="verdict-card animate-fade-up">
      {/* Top Banner */}
      <div className={`verdict-banner ${vc}`}>
        <span className={`verdict-label ${vc}`}>
          {verdictIcons[vc]} {data.final_verdict}
        </span>
        <div className="verdict-badges">
          {data.fact_check_match && <span className="badge badge-info">📖 Verified by Fact-Check API</span>}
          {data.propaganda_analysis?.techniques_found > 0 && (
            <span className="badge badge-warn">⚠️ {data.propaganda_analysis.techniques_found} Techniques</span>
          )}
          {data.live_news_context?.length > 0 && <span className="badge badge-info">📡 Live News Cross-Check</span>}
        </div>
      </div>

      {/* Body */}
      <div className="verdict-body">
        <p className="verdict-explanation">{data.explanation}</p>

        {/* FACT CHECK SUMMARY */}
        {data.fact_check_context && (
          <div className="news-refs" style={{ borderColor: 'var(--info-dim)', background: 'rgba(6, 182, 212, 0.05)', padding: '0.8rem', borderRadius: '8px', marginBottom: '1rem' }}>
            <div className="news-refs-title" style={{ color: 'var(--info)' }}>
              🛡️ Google Fact Check Explorer
            </div>
            <div className="news-ref-item" style={{ flexDirection: 'column', gap: '4px' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: '500', color: 'var(--text)' }}>
                Claim by {data.fact_check_context.claimant}: "{data.fact_check_context.claim_text}"
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                <strong style={{ color: 'var(--info)' }}>{data.fact_check_context.reviewer}</strong> rated it:{' '}
                <strong style={{ background: 'var(--danger-dim)', color: 'var(--danger)', padding: '2px 6px', borderRadius: '4px' }}>
                  {data.fact_check_context.rating}
                </strong>
              </div>
              {data.fact_check_context.url && (
                <a href={data.fact_check_context.url} target="_blank" rel="noreferrer" style={{ fontSize: '0.65rem', color: 'var(--primary)', marginTop: '4px', display: 'inline-block' }}>
                  Read Full Review ↗
                </a>
              )}
            </div>
          </div>
        )}

        {/* Risk Bars */}
        <div className="risk-bar-wrap">
          <div className="risk-bar-label">
            <span>Stylistic Suspicion (LIAR Dataset Model)</span>
            <span style={{ color: getRiskColor(score) }}>{Math.round(score * 100)}%</span>
          </div>
          <div className="risk-bar">
            <div
              className="risk-bar-fill"
              style={{ width: `${score * 100}%`, background: getRiskColor(score) }}
            />
          </div>
        </div>

        {propScore > 0 && (
          <div className="risk-bar-wrap">
            <div className="risk-bar-label">
              <span>Propaganda Risk</span>
              <span style={{ color: getRiskColor(propScore) }}>{Math.round(propScore * 100)}%</span>
            </div>
            <div className="risk-bar">
              <div
                className="risk-bar-fill"
                style={{ width: `${propScore * 100}%`, background: 'linear-gradient(90deg, var(--warning), var(--danger))' }}
              />
            </div>
          </div>
        )}

        {/* Live News Context */}
        {liveNews.length > 0 && (
          <div className="news-refs">
            <div className="news-refs-title">
              📡 Related Current News
            </div>
            {liveNews.slice(0, 3).map((n, i) => (
              <div key={i} className="news-ref-item">
                <div className="news-ref-dot" />
                <span className="news-ref-text">
                  <span className="news-ref-source">{n.source}</span>: {n.title}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Meta */}
        <div className="verdict-meta">
          <span className="verdict-meta-item">Style: {data.pattern_analysis?.label}</span>
          <span className="verdict-meta-item">Score: {score}</span>
          {data.rag_match && <span className="verdict-meta-item">Source: KB</span>}
          {data.propaganda_analysis?.risk_level && (
            <span className="verdict-meta-item">Prop. Risk: {data.propaganda_analysis.risk_level}</span>
          )}
        </div>
      </div>
    </div>
  )
}


function AnalysisPanel({ analysis }) {
  if (!analysis) {
    return (
      <aside className="panel panel-analysis">
        <div className="panel-header">
          <span className="panel-title"><span className="panel-icon">🔬</span> Deep Analysis</span>
        </div>
        <div className="analysis-empty">
          <span className="analysis-empty-icon">🔬</span>
          <span className="analysis-empty-text">
            Submit a claim to see a<br />detailed AI propaganda breakdown.
          </span>
        </div>
      </aside>
    )
  }

  const pa = analysis.propaganda_analysis || {}

  return (
    <aside className="panel panel-analysis">
      <div className="panel-header">
        <span className="panel-title"><span className="panel-icon">🔬</span> Deep Analysis</span>
        <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Latest result</span>
      </div>

      <div className="panel-body">
        {/* AI Deep Analysis */}
        {pa.gemini_analysis && (
          <div className="gemini-section">
            <div className="gemini-section-title">✨ AI Deep Analysis</div>

            {pa.manipulation_intent && (
              <div className="gemini-field">
                <div className="gemini-field-label">Manipulation Intent</div>
                <span className="intent-chip">{pa.manipulation_intent}</span>
              </div>
            )}

            {pa.target_audience && (
              <div className="gemini-field">
                <div className="gemini-field-label">Target Audience</div>
                <div className="gemini-field-value">{pa.target_audience}</div>
              </div>
            )}

            {pa.news_correlation && (
              <div className="gemini-field">
                <div className="gemini-field-label">News Correlation</div>
                <div className="gemini-field-value" style={{
                  color: pa.news_correlation.includes('Contradicts') ? 'var(--danger)' :
                    pa.news_correlation.includes('Aligns') ? 'var(--success)' : 'var(--text-muted)'
                }}>{pa.news_correlation}</div>
              </div>
            )}

            {pa.gemini_analysis && (
              <div className="gemini-field">
                <div className="gemini-field-label">Analysis</div>
                <div className="gemini-field-value">{pa.gemini_analysis}</div>
              </div>
            )}

            {pa.counter_narrative && (
              <div className="gemini-field">
                <div className="gemini-field-label">Counter Narrative</div>
                <div className="gemini-field-value" style={{ fontStyle: 'italic', color: 'var(--success)' }}>
                  "{pa.counter_narrative}"
                </div>
              </div>
            )}
          </div>
        )}

        {!pa.gemini_analysis && (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            No AI analysis available for this result.
          </div>
        )}
      </div>
    </aside>
  )
}


// ─── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'bot',
      text: "👋 Welcome to TruthSeeker v2. I can verify WhatsApp forwards, detect propaganda techniques, and cross-check claims against live news. Try pasting a suspicious message!"
    }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [latestAnalysis, setLatestAnalysis] = useState(null)
  const chatEndRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleVerify = async (textOverride) => {
    const text = (textOverride || input).trim()
    if (!text || isLoading) return

    setInput('')
    setIsLoading(true)

    const userMsg = { id: Date.now(), sender: 'user', text }
    setMessages(prev => [...prev, userMsg])

    try {
      const res = await fetch(`${API}/api/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      })
      const data = await res.json()

      const botMsg = { id: Date.now() + 1, sender: 'bot', analysis: data }
      setMessages(prev => [...prev, botMsg])
      setLatestAnalysis(data)
    } catch {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        sender: 'bot',
        text: "⚠️ Could not connect to the backend. Please ensure the server is running on port 8000."
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleVerify()
    }
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-brand">
          <div className="header-logo">🛡️</div>
          <h1 className="header-title">
            <span>Truth</span>Seeker
            <span className="header-badge">v2</span>
          </h1>
        </div>
        <div className="header-status">
          <div className="status-dot" />
          AI Systems Online
        </div>
      </header>

      {/* 3-Panel Layout */}
      <main className="main-content">
        {/* Left: Live News Feed */}
        <NewsFeedPanel onVerifyHeadline={(headline) => handleVerify(headline)} />

        {/* Center: Chat Verifier */}
        <section className="panel panel-chat">
          <div className="panel-header">
            <span className="panel-title">
              <span className="panel-icon">💬</span> Claim Verifier
            </span>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
              Compound AI · Pattern + Fact-Check + Groq + DuckDuckGo
            </span>
          </div>

          <div className="chat-window">
            {messages.map((msg) => (
              <div key={msg.id} className={`message ${msg.sender}`}>
                {msg.text && (
                  <div className="message-bubble">{msg.text}</div>
                )}
                {msg.analysis && (
                  <VerdictCard data={msg.analysis} />
                )}
              </div>
            ))}

            {isLoading && (
              <div className="message bot">
                <div className="thinking-indicator">
                  <div className="thinking-spinner" />
                  <span className="thinking-text">
                    Analyzing patterns, searching live news, consulting Groq AI…
                  </span>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          <div className="input-area">
            <textarea
              id="verify-input"
              className="input-textarea"
              placeholder="Paste a WhatsApp forward, headline, or suspicious claim to verify…"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
            />
            <button
              id="verify-submit-btn"
              className="send-btn"
              onClick={() => handleVerify()}
              disabled={isLoading || !input.trim()}
            >
              🔍 Verify
            </button>
          </div>
        </section>

        {/* Right: Propaganda Analysis Panel */}
        <AnalysisPanel analysis={latestAnalysis} />
      </main>
    </div>
  )
}

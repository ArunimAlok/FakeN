import { useState, useRef, useEffect } from 'react'
import './App.css'

function App() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "Hello! I am your Fake News Verification Assistant. Paste a WhatsApp forward or news snippet, and I'll analyze it for propaganda patterns.",
      sender: 'bot'
    }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const chatEndRef = useRef(null)

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleVerify = async () => {
    if (!input.trim()) return

    const userMsg = { id: Date.now(), text: input, sender: 'user' }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsLoading(true)

    try {
      const response = await fetch('http://localhost:8000/api/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: input })
      })

      const data = await response.json()

      const botMsg = {
        id: Date.now() + 1,
        sender: 'bot',
        analysis: data
      }

      setMessages(prev => [...prev, botMsg])
    } catch (error) {
      console.error(error)
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        text: "Error connecting to server. Please ensure the backend is running.",
        sender: 'bot'
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
    <div className="app-container">
      <header className="header">
        <h1>🛡️ TruthSeeker <span style={{ fontSize: '0.8rem', opacity: 0.7 }}>Prototype</span></h1>
      </header>

      <div className="chat-window">
        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.sender}`}>
            {msg.text && <div className="text-content">{msg.text}</div>}

            {msg.analysis && (
              <div className="analysis-content">
                <div className="verdict-card" style={{
                  borderColor: msg.analysis.final_verdict.toLowerCase().includes('fake') || msg.analysis.final_verdict.toLowerCase().includes('misleading') ? 'var(--danger)' :
                    msg.analysis.final_verdict.toLowerCase().includes('suspicious') || msg.analysis.final_verdict.toLowerCase().includes('unverified') || msg.analysis.final_verdict.toLowerCase().includes('exaggerated') ? 'var(--warning)' : 'var(--success)'
                }}>
                  <div className={`verdict-header ${msg.analysis.final_verdict.toLowerCase().includes('fake') || msg.analysis.final_verdict.toLowerCase().includes('misleading') ? 'verdict-fake' :
                      msg.analysis.final_verdict.toLowerCase().includes('suspicious') || msg.analysis.final_verdict.toLowerCase().includes('unverified') || msg.analysis.final_verdict.toLowerCase().includes('exaggerated') ? 'verdict-suspicious' : 'verdict-safe'
                    }`}>
                    {msg.analysis.final_verdict}
                    {msg.analysis.rag_match && (
                      <span className="fact-badge">📖 Fact-Checked</span>
                    )}
                  </div>

                  <div className="score-bar">
                    <div className="score-fill" style={{
                      width: `${msg.analysis.pattern_analysis.score * 100}%`,
                      backgroundColor: msg.analysis.pattern_analysis.score > 0.7 ? 'var(--danger)' :
                        msg.analysis.pattern_analysis.score > 0.4 ? 'var(--warning)' : 'var(--success)'
                    }}></div>
                  </div>

                  <div style={{ fontSize: '0.9rem', color: '#cbd5e1', lineHeight: '1.4' }}>
                    {msg.analysis.explanation}
                  </div>
                  <div className="meta-info">
                    Style Score: {msg.analysis.pattern_analysis.score} | Type: {msg.analysis.pattern_analysis.label}
                    {msg.analysis.rag_match && " | Source: Knowledge Base"}
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="message bot">
            <span className="loading-dots">Thinking...</span>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      <div className="input-area">
        <textarea
          placeholder="Paste text here to verify..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button className="send-btn" onClick={handleVerify} disabled={isLoading || !input.trim()}>
          Verify
        </button>
      </div>
    </div>
  )
}

export default App

/**
 * Coach (Phase 8) — Claude-powered planning over your own data.
 * - One-tap planners (next workout / day / study) return a proposal card;
 *   nothing is saved until you tap Accept (→ routine or plan items).
 * - Free-form chat streams replies, grounded in the same data brief.
 * When no ANTHROPIC_API_KEY is set, the page shows a quiet setup note instead.
 */
import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, apiStream } from '../api'
import { Loading, ErrorBox } from '../components/States'

function localTodayIso() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

const CAT_LABEL = { workout: 'Workout', study: 'Study', task: 'Task', meal: 'Meal', other: 'Other' }

// ---- Proposal cards -------------------------------------------------------

function WorkoutProposal({ proposal, onAccept, accepting, accepted }) {
  return (
    <div className="card" style={{ borderColor: 'var(--color-border-str)' }}>
      <div className="row" style={{ marginBottom: '0.3rem' }}>
        <h3 style={{ margin: 0, flex: 1 }}>{proposal.title}</h3>
        <span className="badge primary">proposed workout</span>
      </div>
      {proposal.rationale && (
        <p className="muted" style={{ fontSize: '0.85rem', marginBottom: '0.6rem' }}>{proposal.rationale}</p>
      )}
      <div className="col" style={{ gap: '0.35rem' }}>
        {proposal.exercises.map((ex, i) => (
          <div key={i} className="row" style={{ justifyContent: 'space-between', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.3rem' }}>
            <span style={{ fontSize: '0.9rem' }}>{ex.name}</span>
            <span className="muted tnum" style={{ fontSize: '0.82rem' }}>
              {ex.sets}×{ex.rep_low}–{ex.rep_high}{ex.rest_seconds ? ` · ${ex.rest_seconds}s` : ''}
            </span>
          </div>
        ))}
      </div>
      {accepted ? (
        <p className="text-success" style={{ marginTop: '0.7rem', fontSize: '0.85rem' }}>
          ✓ Saved as a routine. <Link to="/routines">Start it ›</Link>
        </p>
      ) : (
        <button onClick={onAccept} disabled={accepting} style={{ width: '100%', marginTop: '0.75rem' }}>
          {accepting ? 'Saving…' : 'Save as routine'}
        </button>
      )}
    </div>
  )
}

function DayProposal({ proposal, onAccept, accepting, accepted }) {
  return (
    <div className="card" style={{ borderColor: 'var(--color-border-str)' }}>
      <div className="row" style={{ marginBottom: '0.3rem' }}>
        <h3 style={{ margin: 0, flex: 1 }}>{proposal.kind === 'study' ? 'Study plan' : 'Day plan'}</h3>
        <span className="badge primary">{proposal.date}</span>
      </div>
      {proposal.summary && (
        <p className="muted" style={{ fontSize: '0.85rem', marginBottom: '0.6rem' }}>{proposal.summary}</p>
      )}
      <div className="col" style={{ gap: '0.35rem' }}>
        {proposal.items.map((it, i) => (
          <div key={i} className="row" style={{ gap: '0.5rem', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.3rem' }}>
            {it.start_time && <span className="tnum muted" style={{ fontSize: '0.8rem', width: 42 }}>{it.start_time}</span>}
            <span style={{ flex: 1, fontSize: '0.9rem' }}>{it.title}</span>
            <span className="muted" style={{ fontSize: '0.72rem' }}>{CAT_LABEL[it.category] || it.category}</span>
          </div>
        ))}
      </div>
      {accepted ? (
        <p className="text-success" style={{ marginTop: '0.7rem', fontSize: '0.85rem' }}>
          ✓ Added to your plan. <Link to="/">See dashboard ›</Link>
        </p>
      ) : (
        <button onClick={onAccept} disabled={accepting} style={{ width: '100%', marginTop: '0.75rem' }}>
          {accepting ? 'Adding…' : 'Add to plan'}
        </button>
      )}
    </div>
  )
}

export default function Coach() {
  const [status, setStatus] = useState(null)       // {enabled, model}
  const [statusErr, setStatusErr] = useState(null)

  const [proposal, setProposal] = useState(null)   // {kind, ...}
  const [planning, setPlanning] = useState(null)   // which planner is running
  const [accepting, setAccepting] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [error, setError] = useState(null)

  const [messages, setMessages] = useState([])     // {role, content}
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const threadRef = useRef(null)

  useEffect(() => {
    apiFetch('/api/coach/status').then(setStatus).catch(e => setStatusErr(e.message))
  }, [])

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight
  }, [messages])

  async function runPlanner(kind) {
    setPlanning(kind)
    setProposal(null)
    setAccepted(false)
    setError(null)
    const path = kind === 'workout' ? '/api/coach/plan/workout'
      : kind === 'study' ? '/api/coach/plan/study'
      : '/api/coach/plan/day'
    try {
      const body = kind === 'workout' ? {} : { date: localTodayIso() }
      const p = await apiFetch(path, { method: 'POST', body: JSON.stringify(body) })
      setProposal(p)
    } catch (e) {
      setError(e.message)
    } finally {
      setPlanning(null)
    }
  }

  async function acceptProposal() {
    if (!proposal) return
    setAccepting(true)
    setError(null)
    try {
      if (proposal.kind === 'workout') {
        await apiFetch('/api/coach/accept/workout', {
          method: 'POST',
          body: JSON.stringify({ title: proposal.title, exercises: proposal.exercises }),
        })
      } else {
        await apiFetch('/api/coach/accept/day', {
          method: 'POST',
          body: JSON.stringify({ date: proposal.date, items: proposal.items }),
        })
      }
      setAccepted(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setAccepting(false)
    }
  }

  async function send(e) {
    e?.preventDefault()
    const text = input.trim()
    if (!text || streaming) return
    setInput('')
    setError(null)
    const next = [...messages, { role: 'user', content: text }, { role: 'assistant', content: '' }]
    setMessages(next)
    setStreaming(true)
    try {
      const history = next.slice(0, -1)  // everything except the empty assistant turn
      await apiStream('/api/coach/chat', { messages: history }, chunk => {
        setMessages(cur => {
          const copy = [...cur]
          copy[copy.length - 1] = { role: 'assistant', content: copy[copy.length - 1].content + chunk }
          return copy
        })
      })
    } catch (e) {
      setError(e.message)
      setMessages(cur => cur.slice(0, -1))  // drop the empty assistant turn on failure
    } finally {
      setStreaming(false)
    }
  }

  if (statusErr) return <div className="page"><ErrorBox error={statusErr} /></div>
  if (!status) return <div className="page"><Loading /></div>

  return (
    <div className="page">
      <h1>Your <em>coach</em></h1>
      <p className="muted" style={{ marginBottom: '1.25rem' }}>
        Plans built from your training, sleep, and habits — you approve before anything's saved.
      </p>

      {!status.enabled && (
        <div className="card">
          <h3>Set up the coach</h3>
          <p className="muted" style={{ fontSize: '0.88rem' }}>
            The coach uses Claude. Add <code>ANTHROPIC_API_KEY</code> to your backend
            <code> .env</code> and restart the server. Until then, everything else in
            the app works as usual.
          </p>
        </div>
      )}

      {status.enabled && (
        <>
          <ErrorBox error={error} />

          {/* Planners */}
          <div className="row" style={{ flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
            <button className="secondary" onClick={() => runPlanner('workout')} disabled={!!planning}>
              {planning === 'workout' ? 'Planning…' : 'Plan next workout'}
            </button>
            <button className="secondary" onClick={() => runPlanner('day')} disabled={!!planning}>
              {planning === 'day' ? 'Planning…' : 'Plan my day'}
            </button>
            <button className="secondary" onClick={() => runPlanner('study')} disabled={!!planning}>
              {planning === 'study' ? 'Planning…' : 'Plan studying'}
            </button>
          </div>

          {proposal && proposal.kind === 'workout' && (
            <WorkoutProposal proposal={proposal} onAccept={acceptProposal} accepting={accepting} accepted={accepted} />
          )}
          {proposal && proposal.kind !== 'workout' && (
            <DayProposal proposal={proposal} onAccept={acceptProposal} accepting={accepting} accepted={accepted} />
          )}

          {/* Chat */}
          <div className="card">
            <h3 style={{ marginBottom: '0.5rem' }}>Ask anything</h3>
            <div
              ref={threadRef}
              style={{ maxHeight: 360, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.6rem', marginBottom: '0.75rem' }}
            >
              {messages.length === 0 && (
                <p className="muted" style={{ fontSize: '0.85rem' }}>
                  e.g. “Should I train legs today?” · “How's my protein this week?”
                </p>
              )}
              {messages.map((m, i) => (
                <div
                  key={i}
                  style={{
                    alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '85%',
                    background: m.role === 'user' ? 'var(--color-surface2)' : 'transparent',
                    border: m.role === 'user' ? '1px solid var(--color-border)' : 'none',
                    borderRadius: 14,
                    padding: m.role === 'user' ? '0.5rem 0.8rem' : '0',
                    fontSize: '0.9rem',
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.5,
                  }}
                >
                  {m.content || (streaming && i === messages.length - 1 ? '…' : '')}
                </div>
              ))}
            </div>
            <form onSubmit={send} className="row" style={{ gap: '0.5rem' }}>
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Message your coach…"
                disabled={streaming}
                style={{ flex: 1 }}
              />
              <button type="submit" disabled={streaming || !input.trim()} style={{ minWidth: 80 }}>
                {streaming ? '…' : 'Send'}
              </button>
            </form>
          </div>
        </>
      )}
    </div>
  )
}

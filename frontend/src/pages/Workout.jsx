/**
 * Workout page (Phase 1b) — the most important screen, optimised for phone use.
 *
 * Three states:
 *   1. No active session  → Start screen (empty workout or pick a routine)
 *   2. Active session     → live logging UI (exercises, sets, rest timer)
 *   3. Finished           → summary (duration, volume, PRs)
 *
 * Persistence: every change is written to the DB immediately, so closing the
 * tab mid-workout is safe — on reload we fetch the in-progress session back.
 */
import React, { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { apiFetch } from '../api'
import ExercisePicker from '../components/ExercisePicker'
import RestTimer from '../components/RestTimer'
import { Loading, ErrorBox } from '../components/States'

export default function Workout() {
  const location = useLocation()
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [summary, setSummary] = useState(null)  // set when workout finished

  // On mount: if Routines passed a sessionId, load it; else look for an active session
  useEffect(() => {
    const passedId = location.state?.sessionId
    const loader = passedId
      ? apiFetch(`/api/sessions/${passedId}`)
      : apiFetch('/api/sessions/active')
    loader
      .then(s => setSession(s))           // may be null (no active session)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [location.state])

  // Re-fetch the session from the DB (after any structural change)
  const refresh = useCallback(async () => {
    if (!session) return
    try {
      const fresh = await apiFetch(`/api/sessions/${session.id}`)
      setSession(fresh)
    } catch (err) {
      setError(err.message)
    }
  }, [session])

  if (loading) return <div className="page"><Loading /></div>

  if (summary) {
    return <WorkoutSummary summary={summary} onDone={() => { setSummary(null); setSession(null) }} />
  }

  if (!session) {
    return <StartScreen onStarted={setSession} setError={setError} error={error} />
  }

  return (
    <ActiveSession
      session={session}
      setSession={setSession}
      refresh={refresh}
      onFinish={setSummary}
      error={error}
      setError={setError}
    />
  )
}

// ---------------------------------------------------------------------------
// Start screen
// ---------------------------------------------------------------------------

function StartScreen({ onStarted, setError, error }) {
  const [routines, setRoutines] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch('/api/routines')
      .then(setRoutines)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [setError])

  async function start(routine) {
    try {
      const body = routine
        ? { name: routine.name, routine_id: routine.id }
        : { name: `Workout ${new Date().toLocaleDateString()}` }
      const session = await apiFetch('/api/sessions', { method: 'POST', body: JSON.stringify(body) })
      onStarted(session)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="page">
      <h1>Start a <em>workout</em></h1>
      <ErrorBox error={error} />

      <button onClick={() => start(null)} style={{ width: '100%', marginBottom: '1rem' }}>
        + Start empty workout
      </button>

      <h3>Or start from a routine</h3>
      {loading && <Loading />}
      <div className="col" style={{ gap: '0.5rem', marginTop: '0.5rem' }}>
        {routines.map(r => (
          <button key={r.id} className="secondary" style={{ justifyContent: 'space-between', display: 'flex', width: '100%' }} onClick={() => start(r)}>
            <span>{r.name}</span>
            <span className="muted">{r.exercises.length} ex</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Active session
// ---------------------------------------------------------------------------

function ActiveSession({ session, setSession, refresh, onFinish, error, setError }) {
  const [showPicker, setShowPicker] = useState(false)
  const [restSeconds, setRestSeconds] = useState(null)   // active rest timer duration, or null
  const [restKey, setRestKey] = useState(0)              // bumped only when a set completes, to (re)start the timer
  const [restByExercise, setRestByExercise] = useState({})  // exercise_id -> rest seconds (from routine)
  const [elapsed, setElapsed] = useState('')
  const navigate = useNavigate()

  // Ask for notification permission once (for rest-timer alerts)
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  // If the session came from a routine, fetch per-exercise rest seconds
  useEffect(() => {
    if (!session.routine_id) return
    apiFetch(`/api/routines/${session.routine_id}`)
      .then(routine => {
        const map = {}
        routine.exercises.forEach(re => { map[re.exercise_id] = re.rest_seconds })
        setRestByExercise(map)
      })
      .catch(() => {})  // non-critical; default rest applies
  }, [session.routine_id])

  // Live elapsed-time clock in the header
  useEffect(() => {
    const started = new Date(session.started_at + 'Z')  // backend stores UTC naive
    const tick = () => {
      const sec = Math.max(0, Math.floor((Date.now() - started.getTime()) / 1000))
      const m = Math.floor(sec / 60)
      const s = sec % 60
      setElapsed(`${m}:${String(s).padStart(2, '0')}`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [session.started_at])

  function restForExercise(exerciseId) {
    return restByExercise[exerciseId] ?? 120  // default 120s
  }

  // Start (or restart) the rest timer for a given exercise. Bumping restKey
  // remounts the timer so it counts down from the full duration again.
  function startRest(exerciseId) {
    setRestSeconds(restForExercise(exerciseId))
    setRestKey(k => k + 1)
  }

  // Add an exercise mid-workout
  async function addExercise(ex) {
    setShowPicker(false)
    try {
      await apiFetch(`/api/sessions/${session.id}/exercises`, {
        method: 'POST',
        body: JSON.stringify({
          exercise_id: ex.id,
          position: session.exercises.length,
          sets: [{ set_number: 1, weight_kg: 0, reps: 0 }],
        }),
      })
      refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  async function removeExercise(seId) {
    if (!confirm('Remove this exercise from the workout?')) return
    try {
      await apiFetch(`/api/sessions/${session.id}/exercises/${seId}`, { method: 'DELETE' })
      refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  async function finishWorkout() {
    if (!confirm('Finish this workout?')) return
    try {
      const nowUtc = new Date().toISOString().slice(0, 19)  // naive UTC for backend
      await apiFetch(`/api/sessions/${session.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ ended_at: nowUtc }),
      })
      const stats = await apiFetch(`/api/stats/session/${session.id}/summary`)
      onFinish(stats)
    } catch (err) {
      setError(err.message)
    }
  }

  async function cancelWorkout() {
    if (!confirm('Discard this workout? All logged sets will be deleted.')) return
    try {
      await apiFetch(`/api/sessions/${session.id}`, { method: 'DELETE' })
      setSession(null)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="page">
      {/* Sticky: name, clock and Finish stay reachable mid-session */}
      <div className="workout-header">
        <div>
          <h1>{session.name}</h1>
          <span className="muted tnum" style={{ fontSize: '0.78rem' }}>{elapsed} elapsed</span>
        </div>
        <span className="spacer" />
        <button onClick={finishWorkout}>Finish</button>
      </div>

      <ErrorBox error={error} />

      <div className="col" style={{ gap: '1rem', marginTop: '1rem' }}>
        {session.exercises.map(se => (
          <ExerciseCard
            key={se.id}
            sessionId={session.id}
            se={se}
            onChanged={refresh}
            onRemove={() => removeExercise(se.id)}
            onSetCompleted={() => startRest(se.exercise_id)}
            setError={setError}
          />
        ))}
      </div>

      {session.exercises.length === 0 && (
        <p className="muted" style={{ textAlign: 'center', padding: '1rem' }}>
          No exercises yet. Add one to begin.
        </p>
      )}

      <button className="secondary" onClick={() => setShowPicker(true)} style={{ width: '100%', marginTop: '1rem' }}>
        + Add exercise
      </button>

      <button className="danger" onClick={cancelWorkout} style={{ width: '100%', marginTop: '0.75rem' }}>
        Discard workout
      </button>

      {showPicker && <ExercisePicker onSelect={addExercise} onClose={() => setShowPicker(false)} />}

      {restSeconds !== null && (
        <RestTimer
          key={restKey}             // stable across re-renders; only changes when a set completes
          seconds={restSeconds}
          onClose={() => setRestSeconds(null)}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Exercise card with set rows
// ---------------------------------------------------------------------------

function ExerciseCard({ sessionId, se, onChanged, onRemove, onSetCompleted, setError }) {
  const [prevSets, setPrevSets] = useState([])

  // Fetch what was lifted last time, to pre-fill placeholders
  useEffect(() => {
    apiFetch(`/api/sessions/${sessionId}/previous-sets/${se.exercise_id}`)
      .then(setPrevSets)
      .catch(() => {})
  }, [sessionId, se.exercise_id])

  // Look up the previous set by set_number for a placeholder hint
  function prevFor(setNumber) {
    return prevSets.find(p => p.set_number === setNumber)
  }

  async function addSet() {
    try {
      const nextNum = se.sets.length + 1
      await apiFetch(`/api/sessions/${sessionId}/exercises/${se.id}/sets`, {
        method: 'POST',
        body: JSON.stringify({ set_number: nextNum, weight_kg: 0, reps: 0 }),
      })
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  async function deleteSet(setId) {
    try {
      await apiFetch(`/api/sessions/${sessionId}/exercises/${se.id}/sets/${setId}`, { method: 'DELETE' })
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="card" style={{ margin: 0 }}>
      <div className="row">
        <h3 style={{ flex: 1, margin: 0 }}>{se.exercise.name}</h3>
        <button className="secondary" style={{ minWidth: 40, padding: '0.3rem 0.5rem' }} onClick={onRemove}>✕</button>
      </div>
      <div className="muted" style={{ fontSize: '0.75rem', marginBottom: '0.5rem' }}>
        {se.exercise.primary_muscle}{se.exercise.equipment ? ` · ${se.exercise.equipment}` : ''}
      </div>

      {/* Column headers */}
      <div className="row" style={{ fontSize: '0.7rem', color: 'var(--color-muted)', padding: '0 0.25rem', gap: '0.4rem' }}>
        <span style={{ width: 28, textAlign: 'center' }}>Set</span>
        <span style={{ flex: 1 }}>kg</span>
        <span style={{ flex: 1 }}>reps</span>
        <span style={{ width: 48, textAlign: 'center' }}>RPE</span>
        <span style={{ width: 44, textAlign: 'center' }}>✓</span>
        <span style={{ width: 30 }} />
      </div>

      <div className="col" style={{ gap: '0.4rem', marginTop: '0.25rem' }}>
        {se.sets.map(set => (
          <SetRow
            key={set.id}
            sessionId={sessionId}
            seId={se.id}
            set={set}
            prev={prevFor(set.set_number)}
            onChanged={onChanged}
            onCompleted={onSetCompleted}
            onDelete={() => deleteSet(set.id)}
            setError={setError}
          />
        ))}
      </div>

      <button className="secondary" onClick={addSet} style={{ width: '100%', marginTop: '0.5rem', padding: '0.4rem' }}>
        + Add set
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Single set row — weight, reps, RPE, warmup, complete checkbox
// ---------------------------------------------------------------------------

function SetRow({ sessionId, seId, set, prev, onChanged, onCompleted, onDelete, setError }) {
  // Local input state. Initialise from the set; if untouched (0) leave blank
  // so the previous-session value shows as a placeholder.
  const [weight, setWeight] = useState(set.weight_kg || '')
  const [reps, setReps] = useState(set.reps || '')
  const [rpe, setRpe] = useState(set.rpe ?? '')
  const [completed, setCompleted] = useState(set.is_completed)
  const [isWarmup, setIsWarmup] = useState(set.is_warmup)

  const base = `/api/sessions/${sessionId}/exercises/${seId}/sets/${set.id}`

  // Persist a partial update to the DB
  async function patch(payload) {
    try {
      await apiFetch(base, { method: 'PATCH', body: JSON.stringify(payload) })
    } catch (err) {
      setError(err.message)
    }
  }

  // Save weight/reps/rpe on blur (avoids a request per keystroke)
  function saveField() {
    patch({
      weight_kg: weight === '' ? 0 : Number(weight),
      reps: reps === '' ? 0 : Number(reps),
      rpe: rpe === '' ? null : Number(rpe),
    })
  }

  async function toggleComplete() {
    const next = !completed
    setCompleted(next)
    // When completing: use the prefilled previous value if the field is blank
    const w = weight === '' ? (prev?.weight_kg || 0) : Number(weight)
    const r = reps === '' ? (prev?.reps || 0) : Number(reps)
    if (weight === '' && prev) setWeight(prev.weight_kg)
    if (reps === '' && prev) setReps(prev.reps)
    await patch({
      weight_kg: w,
      reps: r,
      rpe: rpe === '' ? null : Number(rpe),
      is_completed: next,
      is_warmup: isWarmup,
    })
    if (next) onCompleted()   // start rest timer
    onChanged()
  }

  async function toggleWarmup() {
    const next = !isWarmup
    setIsWarmup(next)
    await patch({ is_warmup: next })
  }

  const rowBg = completed
    ? 'var(--tint-success)'
    : 'transparent'

  return (
    <div
      className="row"
      style={{ gap: '0.4rem', background: rowBg, borderRadius: 10, padding: '0.2rem 0.25rem', transition: 'background 0.2s var(--ease)' }}
    >
      {/* Set number — tap to toggle warmup. 44px controls: gym thumbs. */}
      <button
        onClick={toggleWarmup}
        title="Tap to toggle warm-up"
        className="secondary"
        style={{
          width: 28, minWidth: 28, height: 44, minHeight: 44, padding: 0,
          fontSize: '0.8rem',
          color: isWarmup ? 'var(--color-warning)' : 'var(--color-text)',
          background: 'transparent', border: 'none',
        }}
      >
        {isWarmup ? 'W' : set.set_number}
      </button>

      <input
        style={{ flex: 1, minHeight: 44, textAlign: 'center' }}
        type="number" inputMode="decimal"
        placeholder={prev ? String(prev.weight_kg) : '0'}
        value={weight}
        onChange={e => setWeight(e.target.value)}
        onBlur={saveField}
      />
      <input
        style={{ flex: 1, minHeight: 44, textAlign: 'center' }}
        type="number" inputMode="numeric"
        placeholder={prev ? String(prev.reps) : '0'}
        value={reps}
        onChange={e => setReps(e.target.value)}
        onBlur={saveField}
      />
      <input
        style={{ width: 48, minHeight: 44, textAlign: 'center', padding: '0.3rem' }}
        type="number" inputMode="decimal"
        placeholder="–"
        value={rpe}
        onChange={e => setRpe(e.target.value)}
        onBlur={saveField}
      />
      <button
        onClick={toggleComplete}
        aria-label={completed ? 'Mark set incomplete' : 'Mark set complete'}
        style={{
          width: 44, minWidth: 44, height: 44, minHeight: 44, padding: 0,
          background: completed ? 'var(--color-success)' : 'var(--color-surface2)',
          color: completed ? 'var(--color-on-primary)' : 'var(--color-text)',
          fontSize: '1.05rem', boxShadow: 'none',
          transition: 'background 0.18s var(--ease), color 0.18s var(--ease)',
        }}
      >
        ✓
      </button>
      {/* Delete this set — muted and slim to avoid mis-taps next to ✓ */}
      <button
        onClick={onDelete}
        title="Delete set"
        aria-label="Delete set"
        style={{
          width: 30, minWidth: 30, height: 44, minHeight: 44, padding: 0,
          background: 'transparent', border: 'none', boxShadow: 'none',
          color: 'var(--color-muted)', fontSize: '0.95rem',
        }}
      >
        ✕
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Finished-workout summary
// ---------------------------------------------------------------------------

function WorkoutSummary({ summary, onDone }) {
  const navigate = useNavigate()
  const prLabel = { heaviest: 'Heaviest weight', best_1rm: 'Best est. 1RM', best_volume: 'Best set volume' }

  return (
    <div className="page">
      <h1>Workout <em>complete</em></h1>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-around', textAlign: 'center' }}>
          <div>
            <div className="stat-num" style={{ fontSize: '2.1rem' }}>{summary.duration_minutes ?? 0}</div>
            <div className="muted" style={{ fontSize: '0.72rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>minutes</div>
          </div>
          <div>
            <div className="stat-num" style={{ fontSize: '2.1rem' }}>{summary.total_volume_kg}</div>
            <div className="muted" style={{ fontSize: '0.72rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>kg volume</div>
          </div>
          <div>
            <div className="stat-num" style={{ fontSize: '2.1rem' }}>{summary.completed_sets}</div>
            <div className="muted" style={{ fontSize: '0.72rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>sets</div>
          </div>
        </div>
      </div>

      {summary.prs_hit.length > 0 ? (
        <div className="card">
          <h2>New PRs <em>({summary.prs_hit.length})</em></h2>
          <div className="col" style={{ gap: '0.5rem', marginTop: '0.5rem' }}>
            {summary.prs_hit.map((pr, i) => (
              <div key={i} className="row">
                <div style={{ flex: 1 }}>
                  <strong>{pr.exercise_name}</strong>
                  <div className="muted" style={{ fontSize: '0.8rem' }}>{prLabel[pr.kind]}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span className="text-success" style={{ fontWeight: 700 }}>{pr.value}</span>
                  {pr.previous_best != null && (
                    <div className="muted" style={{ fontSize: '0.75rem' }}>prev {pr.previous_best}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="card">
          <p className="muted" style={{ textAlign: 'center' }}>No new records this session — showing up is the win.</p>
        </div>
      )}

      <button onClick={() => { onDone(); navigate('/history') }} style={{ width: '100%' }}>
        View history
      </button>
      <button className="secondary" onClick={onDone} style={{ width: '100%', marginTop: '0.5rem' }}>
        Done
      </button>
    </div>
  )
}

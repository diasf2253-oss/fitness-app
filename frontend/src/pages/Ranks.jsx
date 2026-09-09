/**
 * Ranks — a League-style ladder (Tier → Division → LP) per lift and per body
 * part, shown on a tappable body map. Strength is read from logged 1RM ÷
 * bodyweight against the configurable standards. Body parts without a
 * calibrated lift show "unranked" rather than a fake rank.
 */
import React, { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../api'
import { Loading, ErrorBox } from '../components/States'
import WidgetLabel from '../components/WidgetLabel'
import { IMG_W, IMG_H, MUSCLE_SHAPES } from '../data/muscleShapes'
import { detectRankUp } from '../rankSignature'
import { playRankUp } from '../audio'

// Persisted promotion score — compared on each Ranks load to fire the rank-up
// cue exactly when the ladder actually climbs (device-local; not synced data).
const RANK_SIG_KEY = 'rank_signature'

// Body map = the realistic anatomy render (front figure on the left, back on the
// right) with precise muscle outlines overlaid on top. The outlines are traced
// from a hand-drawn muscle separation (see ../data/muscleShapes) in the image's
// own 2400×1792 pixel space. A ranked muscle is filled with its tier colour (a
// flat veil plus a multiply pass so the muscle's real detail shows through);
// unranked muscles stay untinted but tappable, and the selected group is outlined.
const MUSCLE_ORDER = ['Shoulders', 'Chest', 'Biceps', 'Abs', 'Quads', 'Calves', 'Back', 'Triceps', 'Glutes', 'Hamstrings', 'Forearms', 'Adductors']
const REGIONS = MUSCLE_ORDER.map(muscle => ({ muscle, p: MUSCLE_SHAPES[muscle] || [] }))
const ptsStr = pts => pts.map(p => p.join(',')).join(' ')

function BodyMap({ byMuscle, selected, onSelect }) {
  return (
    <div style={{ width: '100%', maxWidth: 540, margin: '0 auto' }}>
      <div style={{ position: 'relative', width: '100%' }}>
        <img src="/body-map.png" alt="Anatomy body map" draggable={false}
          style={{ width: '100%', display: 'block', userSelect: 'none' }} />
        <svg viewBox={`0 0 ${IMG_W} ${IMG_H}`} preserveAspectRatio="none"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
          {REGIONS.map((r, idx) => {
            const bp = byMuscle[r.muscle]
            const ranked = bp?.ranked
            const sel = selected === r.muscle
            return (
              <g key={idx} onClick={() => onSelect(r.muscle)} role="button" aria-label={r.muscle}
                style={{ cursor: 'pointer' }}>
                {/* Ranked muscle: a flat tier-colour veil for full, even coverage, plus a
                    multiply pass so the muscle's own detail still reads through the colour.
                    Unranked: invisible but tappable (faint white when selected). */}
                {r.p.map((pts, i) => {
                  const s = ptsStr(pts)
                  if (!ranked) return <polygon key={i} points={s} fill="#ffffff" fillOpacity={sel ? 0.16 : 0.001} />
                  return (
                    <g key={i}>
                      <polygon points={s} fill={bp.color} fillOpacity={sel ? 0.52 : 0.44} />
                      <polygon points={s} fill={bp.color} fillOpacity={0.55} style={{ mixBlendMode: 'multiply' }} />
                    </g>
                  )
                })}
                {/* Crisp outline on the selected muscle (normal blend so it always shows). */}
                {sel && r.p.map((pts, i) => (
                  <polygon key={`s${i}`} points={ptsStr(pts)} fill="none"
                    stroke="#f7f4ea" strokeWidth={6} strokeLinejoin="round" />
                ))}
              </g>
            )
          })}
        </svg>
      </div>
      <div className="row" style={{ justifyContent: 'space-around', marginTop: '0.25rem' }}>
        <span className="muted" style={{ fontSize: '0.72rem' }}>Front</span>
        <span className="muted" style={{ fontSize: '0.72rem' }}>Back</span>
      </div>
    </div>
  )
}

function TierBadge({ color, tier, division, lp }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.25rem 0.6rem',
      borderRadius: 999, background: `${color}22`, border: `1px solid ${color}`, color,
      fontSize: '0.8rem', fontWeight: 600,
    }}>
      {tier} {division}{lp != null && <span style={{ opacity: 0.85, fontWeight: 400 }}>· {lp} LP</span>}
    </span>
  )
}

export default function Ranks() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [openMuscle, setOpenMuscle] = useState(null)

  function load() {
    setLoading(true)
    apiFetch('/api/ranks')
      .then(d => {
        setData(d)
        // Fire the rank-up cue if the ladder climbed since we last looked.
        let prev = null
        try {
          const stored = localStorage.getItem(RANK_SIG_KEY)
          prev = stored == null ? null : Number(stored)
        } catch { /* storage blocked — treat as first load */ }
        const { rankedUp, signature } = detectRankUp(d, prev)
        if (rankedUp) playRankUp()
        try { localStorage.setItem(RANK_SIG_KEY, String(signature)) } catch { /* ignore */ }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  const byMuscle = useMemo(
    () => Object.fromEntries((data?.body_parts || []).map(b => [b.muscle, b])),
    [data],
  )

  const sel = selected && byMuscle[selected]

  return (
    <div className="page">
      <h1>Your <em>ranks</em></h1>
      <p className="muted" style={{ marginBottom: '1.25rem' }}>
        Where your strength sits on the ladder — per body part, from your logged 1RM and bodyweight.
      </p>
      <ErrorBox error={error} />
      {loading && <Loading />}

      {data && (
        <>
          {data.note && <p className="muted" style={{ marginBottom: '1rem' }}>{data.note}</p>}

          {/* Body map + selection detail */}
          <div className="card">
            <div className="row" style={{ marginBottom: '0.25rem' }}>
              <h3 style={{ margin: 0, flex: 1 }}>Body map</h3>
              <WidgetLabel>tap a muscle</WidgetLabel>
            </div>
            <BodyMap byMuscle={byMuscle} selected={selected} onSelect={setSelected} />

            <div style={{ marginTop: '0.5rem', paddingTop: '0.75rem', borderTop: '1px solid var(--color-border)' }}>
              {!sel ? (
                <p className="muted" style={{ fontSize: '0.85rem' }}>Select a muscle to see its rank.</p>
              ) : sel.ranked ? (
                <div className="row" style={{ alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                  <strong style={{ fontSize: '1rem' }}>{sel.muscle}</strong>
                  <TierBadge color={sel.color} tier={sel.tier} division={sel.division} lp={sel.lp} />
                  <span className="muted" style={{ fontSize: '0.8rem' }}>
                    avg across {sel.n_exercises} {sel.n_exercises === 1 ? 'lift' : 'lifts'}
                  </span>
                </div>
              ) : (
                <p className="muted" style={{ fontSize: '0.85rem' }}>
                  <strong>{sel.muscle}</strong>{sel.tracked === false
                    ? ' — shown on the map, but not tracked for ranking yet.'
                    : ' — unranked · log a lift for this muscle to rank it.'}
                </p>
              )}
            </div>
          </div>

          {/* Tier legend */}
          <div className="card">
            <WidgetLabel>tiers</WidgetLabel>
            <div className="row" style={{ flexWrap: 'wrap', gap: '0.45rem', marginTop: '0.5rem' }}>
              {data.tiers.map(t => (
                <span key={t} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.74rem' }}>
                  <span style={{ width: 12, height: 12, borderRadius: 3, background: data.tier_colors[t] }} />
                  {t}
                </span>
              ))}
            </div>
          </div>

          {/* Per-muscle-group cards — rank = average of the muscle's exercise PRs */}
          <div className="row" style={{ marginTop: '0.5rem', marginBottom: '0.5rem' }}>
            <h3 style={{ margin: 0, flex: 1 }}>Muscle groups</h3>
            <WidgetLabel>all-time PRs</WidgetLabel>
          </div>
          {data.body_parts.map(bp => {
            const open = openMuscle === bp.muscle
            return (
              <div key={bp.muscle} className="card"
                style={{ borderLeft: `4px solid ${bp.ranked ? bp.color : 'var(--color-border-str)'}`, cursor: 'pointer' }}
                onClick={() => { setSelected(bp.muscle); setOpenMuscle(open ? null : bp.muscle) }}>
                <div className="row" style={{ alignItems: 'center', gap: '0.6rem' }}>
                  <strong style={{ flex: 1 }}>{bp.muscle}</strong>
                  {bp.ranked
                    ? <TierBadge color={bp.color} tier={bp.tier} division={bp.division} lp={bp.lp} />
                    : <span className="muted" style={{ fontSize: '0.78rem' }}>{bp.tracked === false ? 'not tracked' : 'unranked'}</span>}
                  <span className="muted" style={{ fontSize: '0.75rem', minWidth: 62, textAlign: 'right' }}>
                    {bp.n_exercises ? `${bp.n_exercises} ${bp.n_exercises === 1 ? 'lift' : 'lifts'}` : '—'} {open ? '▾' : '▸'}
                  </span>
                </div>
                {open && (
                  bp.exercises.length === 0 ? (
                    <p className="muted" style={{ fontSize: '0.8rem', margin: '0.6rem 0 0' }}>
                      {bp.tracked === false
                        ? 'Shown on the body map for anatomy, but no exercises are tagged to it yet — it can\'t rank.'
                        : 'No logged lifts for this muscle yet — its rank is the average of every exercise you train it with.'}
                    </p>
                  ) : (
                    <div style={{ marginTop: '0.6rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {bp.exercises.map(ex => (
                        <div key={ex.exercise_name} className="row" style={{ alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                          <span style={{ flex: 1, fontSize: '0.85rem' }}>{ex.exercise_name}</span>
                          <span className="muted tnum" style={{ fontSize: '0.75rem' }}>{ex.best_1rm} kg 1RM · {ex.best_set}</span>
                          <TierBadge color={ex.color} tier={ex.tier} division={ex.division} lp={ex.lp} />
                        </div>
                      ))}
                    </div>
                  )
                )}
              </div>
            )
          })}
        </>
      )}
    </div>
  )
}

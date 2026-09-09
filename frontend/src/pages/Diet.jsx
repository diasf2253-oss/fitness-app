/**
 * Diet — adaptive calorie target (anchored weekly-trend step model), macro
 * targets, activity log, and the micronutrient RDA analysis. One GET /api/diet
 * drives everything; goal changes go through PUT /api/settings, activities
 * through /api/activities.
 */
import React, { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { Loading, ErrorBox, EmptyNote } from '../components/States'
import PageHero from '../components/PageHero'
import WidgetLabel from '../components/WidgetLabel'
import NutrientBreakdown from '../components/NutrientBreakdown'

function todayIso() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}
function fmtShort(iso) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
// Goal is signed: negative = cut, 0 = maintain, positive = bulk (H1a slider)
function goalText(rate) {
  if (rate < 0) return `Aiming to lose ${Math.abs(rate)} kg / week`
  if (rate > 0) return `Aiming to gain ${rate} kg / week`
  return 'Maintaining weight'
}
const cap = s => s.charAt(0).toUpperCase() + s.slice(1)

const ACTIVITY_TYPES = ['football', 'judo', 'padel']

function Metric({ label, value }) {
  return (
    <div style={{ flex: 1, minWidth: 70 }}>
      <div className="stat-num" style={{ fontSize: '1.5rem' }}>{value}</div>
      <WidgetLabel>{label}</WidgetLabel>
    </div>
  )
}

export default function Diet() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [goalOpen, setGoalOpen] = useState(false)
  const [goal, setGoal] = useState(-0.5)
  const [protein, setProtein] = useState(180)
  const [fat, setFat] = useState(100)
  const [savingGoal, setSavingGoal] = useState(false)

  const [actType, setActType] = useState('football')
  const [actDate, setActDate] = useState(todayIso())
  const [actDur, setActDur] = useState(60)
  const [addingAct, setAddingAct] = useState(false)

  function load() {
    setLoading(true)
    apiFetch('/api/diet')
      .then(d => {
        setData(d)
        setGoal(d.energy.goal_kg_per_week)
        setProtein(d.energy.protein_target_g)
        setFat(d.energy.fat_target_g)
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  async function saveGoal() {
    setSavingGoal(true)
    try {
      await apiFetch('/api/settings', {
        method: 'PUT',
        body: JSON.stringify({
          goal_kg_per_week: Number(goal),
          protein_target_g: Number(protein),
          fat_max_g: Number(fat),
        }),
      })
      setGoalOpen(false)
      load()
    } catch (err) { setError(err.message) } finally { setSavingGoal(false) }
  }

  async function addActivity(ev) {
    ev.preventDefault()
    setAddingAct(true)
    try {
      await apiFetch('/api/activities', {
        method: 'POST',
        body: JSON.stringify({ date: actDate, type: actType, duration_min: Number(actDur) }),
      })
      setActDur(60)
      load()
    } catch (err) { setError(err.message) } finally { setAddingAct(false) }
  }

  async function delActivity(id) {
    try { await apiFetch(`/api/activities/${id}`, { method: 'DELETE' }); load() }
    catch (err) { setError(err.message) }
  }

  const e = data?.energy
  const change = e?.weekly_change_kg

  return (
    <div className="page">
      <PageHero
        meta="Diet"
        live={e?.adaptive_ready}
        aside={e ? `floor ${e.floor.toLocaleString()}${e.ceiling ? ` · ceiling ${e.ceiling.toLocaleString()}` : ''}` : null}
        title={<>Your <em>diet</em></>}
        lede="An adaptive calorie target that nudges itself each week from your weight trend, and how your micronutrients stack up."
      />

      <ErrorBox error={error} />
      {loading && <Loading />}

      {data && (
        <>
          {/* ---- Energy ---- */}
          <div className="card">
            <div className="row" style={{ alignItems: 'baseline', gap: '0.5rem' }}>
              <div className="stat-num" style={{ fontSize: '2.6rem' }}>{e.calorie_target.toLocaleString()}</div>
              <span className="muted">kcal · daily target</span>
            </div>
            <div className="inst" style={{ marginTop: 2 }}>{goalText(e.goal_kg_per_week)}</div>

            <hr className="rule" style={{ margin: '1rem 0' }} />

            <div className="row" style={{ gap: '0.75rem' }}>
              <Metric
                label="weekly change"
                value={change != null ? `${change > 0 ? '+' : ''}${change} kg` : '—'}
              />
              <Metric label="trend weight" value={e.weight_trend_kg != null ? `${e.weight_trend_kg} kg` : '—'} />
              <Metric label="7-day intake" value={e.avg_intake_7d ? e.avg_intake_7d.toLocaleString() : '—'} />
            </div>

            <hr className="rule" style={{ margin: '1rem 0' }} />

            <div className="row" style={{ justifyContent: 'space-between', gap: '0.5rem' }}>
              <div>
                <div className="muted" style={{ fontSize: '0.78rem' }}>
                  {e.adaptive_ready
                    ? <>Adapts Mondays · next {e.next_adapt ? fmtShort(e.next_adapt) : '—'}</>
                    : 'Adaptive target · gathering data'}
                </div>
                {e.adaptive_ready && e.entries_last_week != null && (
                  <div className="muted" style={{ fontSize: '0.74rem', marginTop: 2 }}>
                    {e.entries_last_week} weigh-in{e.entries_last_week === 1 ? '' : 's'} last completed week
                  </div>
                )}
              </div>
              <button className="secondary" onClick={() => setGoalOpen(o => !o)}>Change goal</button>
            </div>

            {e.note && <p className="muted" style={{ fontSize: '0.8rem', marginTop: '0.75rem' }}>{e.note}</p>}

            {goalOpen && (
              <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--color-border)' }}>
                <WidgetLabel>weekly goal</WidgetLabel>
                <div style={{ margin: '0.5rem 0 0.25rem' }}>
                  <input
                    type="range" min="-0.5" max="0.5" step="0.01"
                    value={goal}
                    onChange={ev => setGoal(Number(ev.target.value))}
                    aria-label="Weekly bodyweight goal (kg per week)"
                    style={{ width: '100%', margin: 0 }}
                  />
                  <div className="row" style={{ justifyContent: 'space-between', marginTop: 4 }}>
                    {[['Cut −0.5', -0.5], ['Maintain 0', 0], ['Bulk +0.5', 0.5]].map(([label, v]) => (
                      <button
                        key={label}
                        className="secondary"
                        onClick={() => setGoal(v)}
                        style={{
                          background: 'transparent', border: 'none', boxShadow: 'none',
                          minHeight: 0, padding: '0.15rem 0', fontSize: '0.72rem',
                          color: 'var(--color-muted)',
                        }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="tnum" style={{ textAlign: 'center', margin: '0.35rem 0 1rem', fontSize: '0.95rem' }}>
                  {goal > 0 ? '+' : ''}{Number(goal).toFixed(2)} kg / week · {goal < 0 ? 'cut' : goal > 0 ? 'bulk' : 'maintain'}
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Protein (g)</label>
                    <input type="number" inputMode="numeric" min="0" value={protein} onChange={ev => setProtein(ev.target.value)} />
                  </div>
                  <div className="form-group">
                    <label>Fat (g)</label>
                    <input type="number" inputMode="numeric" min="0" value={fat} onChange={ev => setFat(ev.target.value)} />
                  </div>
                </div>
                <p className="muted" style={{ fontSize: '0.74rem', margin: '0 0 0.75rem' }}>
                  The target moves ±100 kcal per week toward this goal — it never drops below the {e.floor.toLocaleString()} kcal floor.
                </p>
                <div className="row" style={{ justifyContent: 'flex-end', gap: '0.5rem' }}>
                  <button className="secondary" onClick={() => setGoalOpen(false)}>Cancel</button>
                  <button onClick={saveGoal} disabled={savingGoal}>{savingGoal ? 'Saving…' : 'Save goal'}</button>
                </div>
              </div>
            )}
          </div>

          {/* ---- Macro targets ---- */}
          <div className="card">
            <div className="row" style={{ marginBottom: '0.75rem' }}>
              <h3 style={{ margin: 0, flex: 1 }}>Macro targets</h3>
              <WidgetLabel>per day</WidgetLabel>
            </div>
            <div className="row" style={{ gap: '0.75rem' }}>
              <Metric label="protein" value={`${e.protein_target_g} g`} />
              <Metric label="fat" value={`${e.fat_target_g} g`} />
              <Metric label="carbs" value={e.carb_target_g != null ? `${e.carb_target_g} g` : '—'} />
            </div>
            <p className="muted" style={{ fontSize: '0.76rem', marginTop: '0.75rem' }}>
              Protein and fat stay fixed; carbs flex to fill the remaining calories as the target adapts. Edit them under “Change goal”.
            </p>
          </div>

          {/* ---- Activity ---- */}
          <div className="card">
            <div className="row" style={{ marginBottom: '0.6rem' }}>
              <h3 style={{ margin: 0, flex: 1 }}>Activity</h3>
              <WidgetLabel>14 days</WidgetLabel>
            </div>
            <form onSubmit={addActivity} className="row" style={{ gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.85rem' }}>
              <select value={actType} onChange={ev => setActType(ev.target.value)} style={{ width: 'auto', flex: '1 1 110px' }}>
                {ACTIVITY_TYPES.map(t => <option key={t} value={t}>{cap(t)}</option>)}
              </select>
              <input type="date" value={actDate} onChange={ev => setActDate(ev.target.value)} style={{ width: 'auto', flex: '1 1 130px' }} />
              <input type="number" inputMode="numeric" min="1" value={actDur} onChange={ev => setActDur(ev.target.value)} aria-label="Duration in minutes" style={{ width: 'auto', flex: '1 1 70px' }} />
              <button type="submit" disabled={addingAct} style={{ flex: '0 0 auto' }}>{addingAct ? '…' : 'Add'}</button>
            </form>
            {data.activities.length === 0 ? (
              <EmptyNote>No sessions logged in the last 14 days.</EmptyNote>
            ) : (
              data.activities.map(a => (
                <div key={a.id} className="row" style={{ padding: '0.4rem 0', borderBottom: '1px solid var(--color-border)' }}>
                  <div style={{ flex: 1 }}>
                    <span style={{ fontSize: '0.9rem' }}>{cap(a.type)}</span>
                    <span className="muted" style={{ fontSize: '0.76rem', marginLeft: 8 }}>{fmtShort(a.date)} · {a.duration_min} min</span>
                  </div>
                  <span className="tnum muted" style={{ fontSize: '0.82rem', marginRight: 10 }}>~{a.calories_est} kcal</span>
                  <button className="secondary" onClick={() => delActivity(a.id)} aria-label="Delete session"
                    style={{ minWidth: 32, minHeight: 32, padding: 0, borderRadius: '50%', fontSize: '1rem' }}>×</button>
                </div>
              ))
            )}
            <p className="muted" style={{ fontSize: '0.74rem', marginTop: '0.75rem' }}>
              Burn is an estimate (METs). It doesn’t move your target directly — the weekly trend already
              captures it, so adding it on top would double-count.
            </p>
          </div>

          {/* ---- Micronutrients ---- */}
          <NutrientBreakdown nutrients={data.nutrients} days={data.nutrient_days} />
        </>
      )}
    </div>
  )
}

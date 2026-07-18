/**
 * Weekly / biweekly report — an in-app review screen for the chosen period,
 * with a markdown export and (when the AI coach is configured) an optional
 * narrative plan. Every section renders independently and shows
 * "No data for this period" rather than breaking when data is missing.
 */
import React, { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { Loading, ErrorBox } from '../components/States'
import PageHero from '../components/PageHero'
import WidgetLabel from '../components/WidgetLabel'
import { reportMarkdown } from '../local/api/report'

function Section({ title, aside, children }) {
  return (
    <div className="card">
      <div className="row" style={{ marginBottom: '0.6rem' }}>
        <h3 style={{ margin: 0, flex: 1 }}>{title}</h3>
        {aside && <WidgetLabel>{aside}</WidgetLabel>}
      </div>
      {children}
    </div>
  )
}

const NoData = () => <p className="muted" style={{ fontSize: '0.85rem' }}>No data for this period.</p>

export default function Report() {
  const [period, setPeriod] = useState('weekly')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [narrative, setNarrative] = useState(null)
  const [planLoading, setPlanLoading] = useState(false)
  const [planError, setPlanError] = useState(null)

  useEffect(() => {
    setLoading(true); setNarrative(null); setPlanError(null)
    apiFetch(`/api/report?period=${period}`)
      .then(setReport)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [period])

  function downloadMarkdown() {
    // Rendered from the already-loaded report via the shared pure builder, so
    // the export works identically offline (local-first) and online.
    const text = reportMarkdown(report)
    const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `${period}-report-${report.end}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function generatePlan() {
    setPlanLoading(true); setPlanError(null)
    try {
      const r = await apiFetch(`/api/report/coach-plan?period=${period}`, { method: 'POST' })
      setNarrative(r.narrative)
    } catch (e) { setPlanError(e.message) } finally { setPlanLoading(false) }
  }

  const r = report

  return (
    <div className="page">
      <PageHero
        meta="Review"
        title={<>Your <em>report</em></>}
        lede="A snapshot of training, bodyweight, diet, and sleep — with a plan for next week."
      />

      <div className="row" style={{ gap: '0.5rem', marginBottom: '1rem' }}>
        {['weekly', 'biweekly'].map(p => (
          <button key={p} className={period === p ? '' : 'secondary'} onClick={() => setPeriod(p)}
            style={{ textTransform: 'capitalize' }}>{p}</button>
        ))}
        <span className="spacer" style={{ flex: 1 }} />
        {r && <button className="secondary" onClick={downloadMarkdown}>↓ Export .md</button>}
      </div>

      <ErrorBox error={error} />
      {loading && <Loading />}

      {r && (
        <>
          <p className="muted" style={{ fontSize: '0.8rem', marginBottom: '0.75rem' }}>{r.start} → {r.end}</p>

          {/* New PRs */}
          <Section title="New PRs" aside={`${r.prs.count} this period`}>
            {r.prs.items.length === 0 ? <p className="muted" style={{ fontSize: '0.85rem' }}>No new PRs this period.</p> : (
              r.prs.items.map((p, i) => (
                <div key={i} className="row" style={{ padding: '0.35rem 0', borderBottom: '1px solid var(--color-border)' }}>
                  <span style={{ flex: 1, fontSize: '0.9rem' }}>{p.exercise}
                    <span className="muted" style={{ fontSize: '0.74rem', marginLeft: 6 }}>{p.best_set}</span>
                  </span>
                  <span className="tnum text-success" style={{ fontSize: '0.9rem' }}>{p.estimated_1rm} kg 1RM</span>
                  {p.previous_best != null && <span className="tnum muted" style={{ fontSize: '0.74rem', marginLeft: 8 }}>was {p.previous_best}</span>}
                </div>
              ))
            )}
          </Section>

          {/* Streak */}
          <Section title="Streak">
            <div className="row" style={{ gap: '1.5rem' }}>
              <div><div className="stat-num" style={{ fontSize: '1.8rem' }}>{r.streak.current}</div><WidgetLabel>current</WidgetLabel></div>
              <div><div className="stat-num" style={{ fontSize: '1.8rem' }}>{r.streak.longest}</div><WidgetLabel>longest</WidgetLabel></div>
              {r.streak.at_risk && <span className="muted" style={{ alignSelf: 'center', color: 'var(--color-danger)', fontSize: '0.82rem' }}>⚠️ at risk</span>}
            </div>
          </Section>

          {/* Bodyweight */}
          <Section title="Bodyweight trend" aside="weekly avg">
            {!r.bodyweight ? <NoData /> : (
              <div className="row" style={{ alignItems: 'baseline', gap: '0.5rem' }}>
                <span className="tnum">{r.bodyweight.start_avg} kg</span>
                <span className="muted">→</span>
                <span className="tnum">{r.bodyweight.end_avg} kg</span>
                <span className="tnum" style={{ marginLeft: 8, color: r.bodyweight.direction === 'down' ? 'var(--color-accent)' : 'var(--color-text)' }}>
                  {r.bodyweight.direction === 'down' ? '▼' : r.bodyweight.direction === 'up' ? '▲' : '→'} {Math.abs(r.bodyweight.change_kg)} kg
                </span>
              </div>
            )}
          </Section>

          {/* Diet adherence */}
          <Section title="Diet adherence" aside={r.diet ? `${r.diet.logged_days} logged days` : null}>
            {!r.diet ? <NoData /> : (
              <div className="row" style={{ gap: '1.5rem' }}>
                <div><div className="stat-num" style={{ fontSize: '1.8rem' }}>{r.diet.calorie_pct}%</div><WidgetLabel>calories on target</WidgetLabel></div>
                <div><div className="stat-num" style={{ fontSize: '1.8rem' }}>{r.diet.protein_pct}%</div><WidgetLabel>protein on target</WidgetLabel></div>
              </div>
            )}
          </Section>

          {/* Sleep */}
          <Section title="Sleep" aside={r.sleep ? `${r.sleep.nights} nights` : null}>
            {!r.sleep ? <NoData /> : (
              <div className="row" style={{ alignItems: 'baseline', gap: '0.5rem' }}>
                <span className="stat-num" style={{ fontSize: '1.8rem' }}>{r.sleep.avg_hours} h</span>
                {r.sleep.change_h != null && (
                  <span className="muted tnum" style={{ fontSize: '0.8rem' }}>
                    {r.sleep.change_h >= 0 ? '▲' : '▼'} {Math.abs(r.sleep.change_h)} h vs prior
                  </span>
                )}
              </div>
            )}
          </Section>

          {/* Plan for next week */}
          <Section title="Plan for next week">
            <p style={{ fontSize: '0.9rem', margin: '0 0 0.5rem' }}>
              Calorie target <strong>{r.plan.calorie_target.toLocaleString()} kcal</strong>
              <span className="muted"> · goal {r.plan.goal_kg_per_week > 0 ? '+' : ''}{r.plan.goal_kg_per_week} kg/wk · next adapt {r.plan.next_adapt}</span>
            </p>
            {r.plan.volume_flags.length === 0 ? (
              <p className="muted" style={{ fontSize: '0.82rem' }}>Volume on track across all muscle groups this week.</p>
            ) : (
              r.plan.volume_flags.map(f => (
                <div key={f.muscle} className="row" style={{ padding: '0.25rem 0', fontSize: '0.85rem' }}>
                  <span style={{ flex: 1 }}>{f.muscle}</span>
                  <span style={{ color: f.status === 'over' ? 'var(--color-danger)' : 'var(--color-muted)' }}>
                    {f.count} sets · {f.status} ({f.low}–{f.high})
                  </span>
                </div>
              ))
            )}

            {r.coach_available && (
              <div style={{ marginTop: '0.85rem', paddingTop: '0.85rem', borderTop: '1px solid var(--color-border)' }}>
                {narrative ? (
                  <p style={{ fontSize: '0.9rem', whiteSpace: 'pre-wrap', margin: 0 }}>{narrative}</p>
                ) : (
                  <button className="secondary" onClick={generatePlan} disabled={planLoading}>
                    {planLoading ? 'Thinking…' : '✦ Generate AI plan'}
                  </button>
                )}
                <ErrorBox error={planError} />
              </div>
            )}
          </Section>
        </>
      )}
    </div>
  )
}

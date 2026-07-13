/**
 * NutrientBreakdown — the micronutrient analysis: a labelled bar per nutrient,
 * coloured by how the average intake compares to the RDA, grouped into
 * Vitamins and Minerals. Mirrors the four-band design (Low / Slightly low /
 * Meets / Above RDA).
 */
import React from 'react'
import WidgetLabel from './WidgetLabel'

// Calm-palette mapping of the four RDA bands.
const STATUS = {
  low:          { legend: 'Low (under 70%)',        color: '#cf8772' },
  slightly_low: { legend: 'Slightly low (70–99%)',  color: '#d9b06b' },
  meets:        { legend: 'Meets RDA',              color: '#8fb573' },
  above:        { legend: 'Above RDA',              color: '#7aa6cf' },
}

function fmtAmount(v) {
  if (v >= 100) return Math.round(v / 10) * 10
  if (v >= 10) return Math.round(v)
  return Math.round(v * 10) / 10
}

function NutrientRow({ n }) {
  const s = STATUS[n.status] || STATUS.meets
  const pctText = n.pct > 400 ? '>400%' : `${n.pct}%`
  return (
    <div style={{ marginBottom: '0.7rem' }}>
      <div className="row" style={{ justifyContent: 'space-between', gap: '0.6rem', marginBottom: 5 }}>
        <span style={{ fontSize: '0.9rem' }}>{n.label}</span>
        <span className="row" style={{ gap: 8, flexShrink: 0 }}>
          <span className="tnum muted" style={{ fontSize: '0.8rem' }}>~{fmtAmount(n.amount)} {n.unit}</span>
          <span
            className="nutri-pill tnum"
            style={{ color: s.color, background: `${s.color}22`, borderColor: `${s.color}55` }}
          >
            {pctText}
          </span>
        </span>
      </div>
      <div className="nutri-track">
        <div className="nutri-fill" style={{ width: `${Math.min(n.pct, 100)}%`, background: s.color }} />
      </div>
    </div>
  )
}

export default function NutrientBreakdown({ nutrients, days }) {
  if (!nutrients || nutrients.length === 0) {
    return (
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Micronutrients</h3>
        <p className="muted" style={{ fontSize: '0.85rem' }}>
          No micronutrient data yet — log a few days of food (Apple Health or the manual log)
          and the breakdown appears here.
        </p>
      </div>
    )
  }

  const vitamins = nutrients.filter(n => n.category === 'vitamin')
  const minerals = nutrients.filter(n => n.category === 'mineral')

  return (
    <div className="card">
      <div className="row" style={{ marginBottom: '0.7rem' }}>
        <h3 style={{ margin: 0, flex: 1 }}>Micronutrients</h3>
        <WidgetLabel>{days}-day avg</WidgetLabel>
      </div>

      <div className="row" style={{ gap: '0.9rem 1.1rem', flexWrap: 'wrap', marginBottom: '1.15rem' }}>
        {Object.entries(STATUS).map(([k, s]) => (
          <span key={k} className="row" style={{ gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: s.color, flexShrink: 0 }} />
            <span className="muted" style={{ fontSize: '0.72rem' }}>{s.legend}</span>
          </span>
        ))}
      </div>

      {vitamins.length > 0 && (
        <div style={{ marginBottom: '1.1rem' }}>
          <div className="inst" style={{ marginBottom: '0.7rem' }}>Vitamins</div>
          {vitamins.map(n => <NutrientRow key={n.name} n={n} />)}
        </div>
      )}
      {minerals.length > 0 && (
        <div>
          <div className="inst" style={{ marginBottom: '0.7rem' }}>Minerals</div>
          {minerals.map(n => <NutrientRow key={n.name} n={n} />)}
        </div>
      )}
    </div>
  )
}

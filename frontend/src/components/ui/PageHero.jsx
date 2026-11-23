import React from 'react'

/**
 * PageHero — a lightweight editorial header shared across the primary screens.
 * A small instrumentation readout, the display title (JSX, may include <em>),
 * and a muted lede. Styled with inline rules + existing utility classes so it
 * works on the local-first line's theme without a bespoke stylesheet.
 *
 *   meta   left-hand readout (uppercased)
 *   live   adds a small accent tick before meta
 *   aside  optional right-aligned readout (status, count…)
 *   title  display heading (JSX, may include <em>)
 *   lede   muted supporting line
 */
export default function PageHero({ meta, live = false, aside, title, lede }) {
  return (
    <header style={{ marginBottom: '1.4rem' }}>
      {(meta || aside) && (
        <div
          className="row"
          style={{
            fontSize: '0.68rem', letterSpacing: '0.12em', textTransform: 'uppercase',
            color: 'var(--color-muted)', borderBottom: '1px solid var(--color-border)',
            paddingBottom: '0.45rem', marginBottom: '0.6rem',
          }}
        >
          {meta && (
            <span>
              {live && (
                <span style={{
                  display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                  background: 'var(--color-accent)', marginRight: 6, verticalAlign: 'middle',
                }} />
              )}
              {meta}
            </span>
          )}
          {aside && <span style={{ marginLeft: 'auto' }}>{aside}</span>}
        </div>
      )}
      <h1 style={{ margin: 0 }}>{title}</h1>
      {lede && (
        <p className="muted" style={{ marginTop: '0.4rem', maxWidth: '52ch' }}>{lede}</p>
      )}
    </header>
  )
}

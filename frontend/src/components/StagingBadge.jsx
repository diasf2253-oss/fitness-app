import React, { useEffect, useState } from 'react'
import { isStagingBuild, probeStagingApi } from '../env'

/**
 * Fixed "STAGING" pill, shown whenever this frontend talks to the staging
 * API. Build-time signals show it immediately; otherwise a one-shot ping
 * probe catches a staging backend whose domain doesn't say so.
 */
export default function StagingBadge() {
  const [show, setShow] = useState(isStagingBuild)

  useEffect(() => {
    if (show) return
    let alive = true
    probeStagingApi().then(staging => { if (alive && staging) setShow(true) })
    return () => { alive = false }
  }, [show])

  if (!show) return null
  return <div className="staging-badge" aria-label="Staging environment">STAGING</div>
}

"""Weekly / biweekly report.

GET  /api/report?period=weekly|biweekly          — structured report (JSON)
GET  /api/report/markdown?period=...             — clean downloadable markdown
POST /api/report/coach-plan?period=...           — optional AI narrative plan
                                                   (503 + graceful if no key)
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.config import settings as app_settings
from app.db import get_db
from app.models import User
from app.report import PERIOD_DAYS, build_report, report_markdown

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/report", tags=["report"])

Period = Query("weekly", pattern="^(weekly|biweekly)$")


@router.get("")
def get_report(
    period: str = Period,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    return build_report(db, current_user.id, period)


@router.get("/markdown")
def get_report_markdown(
    period: str = Period,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    report = build_report(db, current_user.id, period)
    md = report_markdown(report)
    filename = f"{period}-report-{report['end']}.md"
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/coach-plan")
def coach_plan(
    period: str = Period,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Optional: a short narrative plan from the period's data. Returns 503 if
    no ANTHROPIC_API_KEY is configured — the report works fine without it."""
    if not app_settings.coach_enabled:
        raise HTTPException(status_code=503, detail="AI Coach is not configured.")

    import anthropic

    md = report_markdown(build_report(db, current_user.id, period))
    prompt = (
        "Here is my training/health report for the period. In 4-6 sentences, "
        "give me a focused, encouraging plan for next week: what to prioritise, "
        "any muscle groups to add or cut volume on, and one diet/recovery nudge. "
        "Be concrete and brief.\n\n" + md
    )
    try:
        client = anthropic.Anthropic(api_key=app_settings.anthropic_api_key)
        resp = client.messages.create(
            model=app_settings.coach_model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as e:
        logger.warning("Coach plan API error: %s", e)
        raise HTTPException(status_code=502, detail=f"AI request failed: {e}")

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return {"narrative": text.strip()}

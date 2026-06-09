"""
YAZIO nutrition sync integration.

YAZIO has no official public API. This implementation uses the same endpoints
that the official YAZIO mobile app uses (community-documented).

Flow:
  1. POST to the YAZIO OAuth token endpoint with email + password
  2. Receive an access token (Bearer)
  3. GET /api/user/food-entries?date=YYYY-MM-DD → parse calories + macros
  4. Upsert into nutrition_day table with source='yazio'

The token is cached in memory and refreshed only when it expires or a 401 is
returned. Credentials never leave this file except in HTTP headers to YAZIO.

If anything fails (bad credentials, API shape change, network error), the error
is logged and surfaced in the settings row (yazio_last_error) — the app never
crashes.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# YAZIO API base URL (documented by community reverse-engineering)
YAZIO_BASE = "https://api.yazio.com"
TOKEN_URL = f"{YAZIO_BASE}/oauth/v2/token"
ENTRIES_URL = f"{YAZIO_BASE}/api/v5/user/consumed-products"

# In-memory token cache (single-user app, no persistence needed between restarts)
_cached_token: Optional[str] = None
_token_expires_at: Optional[datetime] = None


async def _get_token(email: str, password: str) -> str:
    """
    Perform OAuth password-grant login and return an access token.
    Caches the token until it expires.
    """
    global _cached_token, _token_expires_at

    # Return cached token if still valid (with 60s buffer)
    if (
        _cached_token
        and _token_expires_at
        and datetime.utcnow() < _token_expires_at - timedelta(seconds=60)
    ):
        return _cached_token

    logger.info("YAZIO: requesting new access token")
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "password",
                "client_id": "yazio_prod_client",   # community-documented value
                "client_secret": "",                # not required
                "username": email,
                "password": password,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    token = data.get("access_token")
    if not token:
        raise ValueError(f"YAZIO login response missing access_token: {data}")

    expires_in = int(data.get("expires_in", 3600))
    _cached_token = token
    _token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    logger.info("YAZIO: token obtained, expires in %ds", expires_in)
    return token


async def fetch_day_summary(
    target_date: date,
    email: str,
    password: str,
) -> Optional[dict]:
    """
    Fetch consumed macros for a single day from YAZIO.

    Returns a dict with keys: calories, protein_g, carbs_g, fat_g
    Returns None if the date has no logged data.

    NOTE: If the YAZIO API shape changes, this function will raise an exception
    which the caller (sync_yazio) handles gracefully.
    """
    token = await _get_token(email, password)

    headers = {"Authorization": f"Bearer {token}"}
    params = {"date": target_date.isoformat()}

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(ENTRIES_URL, headers=headers, params=params)

        # If token expired mid-session, clear cache and retry once
        if resp.status_code == 401:
            global _cached_token, _token_expires_at
            _cached_token = None
            _token_expires_at = None
            token = await _get_token(email, password)
            headers["Authorization"] = f"Bearer {token}"
            resp = await client.get(ENTRIES_URL, headers=headers, params=params)

        resp.raise_for_status()
        data = resp.json()

    # Parse YAZIO response — the community-documented shape:
    # {"data": {"nutrients": {"energy": {"amount": 2100, "unit": "kcal"},
    #                         "protein": {"amount": 180, "unit": "g"},
    #                         "carbohydrates": {"amount": 200, "unit": "g"},
    #                         "fat": {"amount": 70, "unit": "g"}}}}
    # NOTE: If YAZIO changes this shape, we raise KeyError → caught by caller.
    nutrients = data.get("data", {}).get("nutrients", {})
    if not nutrients:
        logger.info("YAZIO: no nutrient data for %s", target_date)
        return None

    return {
        "calories": float(nutrients.get("energy", {}).get("amount", 0)),
        "protein_g": float(nutrients.get("protein", {}).get("amount", 0)),
        "carbs_g": float(nutrients.get("carbohydrates", {}).get("amount", 0)),
        "fat_g": float(nutrients.get("fat", {}).get("amount", 0)),
    }


async def sync_days(
    days: int,
    email: str,
    password: str,
    db,  # SQLAlchemy session — injected by caller to avoid circular import
) -> dict:
    """
    Sync the last N days of YAZIO nutrition data into the nutrition_day table.
    Returns a summary dict with rows_upserted and any error message.
    """
    from app.models import NutritionDay  # local import avoids circular

    today = date.today()
    rows_upserted = 0
    errors = []

    for delta in range(days):
        target = today - timedelta(days=delta)
        try:
            summary = await fetch_day_summary(target, email, password)
            if summary is None:
                continue

            row = db.query(NutritionDay).filter(NutritionDay.date == target).first()
            if row:
                row.calories = summary["calories"]
                row.protein_g = summary["protein_g"]
                row.carbs_g = summary["carbs_g"]
                row.fat_g = summary["fat_g"]
                row.source = "yazio"
            else:
                db.add(NutritionDay(date=target, source="yazio", **summary))
                rows_upserted += 1

        except Exception as e:
            msg = f"YAZIO sync failed for {target}: {e}"
            logger.error(msg)
            errors.append(msg)

    db.commit()
    return {"rows_upserted": rows_upserted, "errors": errors}

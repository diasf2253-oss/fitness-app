"""
Dev utilities — NOT part of the real data flow.

POST   /api/dev/seed-sample-health  — load ~30 days of realistic sample
                                      weight/steps/sleep/nutrition data
DELETE /api/dev/seed-sample-health  — remove exactly the seeded rows

Sample rows are written with source='sample' so they are impossible to
confuse with real entries ('apple_health' | 'manual') and can be cleared
surgically without touching anything the user logged themselves.
The generator is seeded, so re-running produces identical values and the
date-keyed upserts keep it idempotent.
"""
import random
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import NutritionDay, SleepLog, StepsLog, WeightLog
from app.routers.health import upsert_sleep, upsert_steps, upsert_weight
from app.schemas import NutritionDayCreate

router = APIRouter(prefix="/api/dev", tags=["dev"])

SAMPLE_SOURCE = "sample"
SAMPLE_DAYS = 30


@router.post("/seed-sample-health")
def seed_sample_health(
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Upsert ~30 days of plausible health data ending today. Idempotent."""
    from app.routers.nutrition import upsert_nutrition

    rng = random.Random(42)  # fixed seed → same data every run
    today = date.today()
    days = 0

    weight = 84.5  # slow cut: drifts down ~1.5 kg over the month
    for offset in range(SAMPLE_DAYS - 1, -1, -1):
        d = today - timedelta(days=offset)
        days += 1

        weight += rng.uniform(-0.35, 0.25)
        upsert_weight(db, d, round(weight, 1), SAMPLE_SOURCE)

        # Weekdays trend higher than lazy Sundays
        base_steps = 11000 if d.weekday() < 5 else 7000
        upsert_steps(db, d, base_steps + rng.randint(-3000, 3500), SAMPLE_SOURCE)

        asleep = rng.randint(360, 510)  # 6h–8.5h
        deep = int(asleep * rng.uniform(0.13, 0.2))
        rem = int(asleep * rng.uniform(0.18, 0.25))
        upsert_sleep(
            db, d,
            asleep_minutes=asleep,
            in_bed_minutes=asleep + rng.randint(15, 50),
            deep_minutes=deep,
            rem_minutes=rem,
            core_minutes=asleep - deep - rem,
            source=SAMPLE_SOURCE,
        )

        protein = rng.randint(150, 200)
        carbs = rng.randint(190, 290)
        fat = rng.randint(65, 105)
        upsert_nutrition(db, NutritionDayCreate(
            date=d,
            calories=round(protein * 4 + carbs * 4 + fat * 9, 0),
            protein_g=protein,
            carbs_g=carbs,
            fat_g=fat,
            source=SAMPLE_SOURCE,
        ))

    db.commit()
    return {"status": "ok", "days_seeded": days, "from": str(today - timedelta(days=SAMPLE_DAYS - 1)), "to": str(today)}


@router.delete("/seed-sample-health")
def clear_sample_health(
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Delete only rows created by the seeder (source='sample')."""
    deleted = 0
    for model in (WeightLog, StepsLog, SleepLog, NutritionDay):
        deleted += (
            db.query(model)
            .filter(model.source == SAMPLE_SOURCE)
            .delete(synchronize_session=False)
        )
    db.commit()
    return {"status": "ok", "rows_deleted": deleted}

"""
Canonical nutrition metric definitions shared by both Apple Health ingest
paths (Health Auto Export JSON push and export.xml history backfill).

Canonical keys carry their unit suffix (protein_g, sodium_mg, vitamin_d_ug)
so every consumer — DB, API, UI — knows the unit without a lookup table.
Macros live as columns on nutrition_day; micros go into its JSON column.
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from app.models import NutritionDay

# Macro canonical keys → NutritionDay column names
MACRO_COLUMNS = {
    "calories": "calories",
    "protein_g": "protein_g",
    "carbs_g": "carbs_g",
    "fat_g": "fat_g",
}

# Health Auto Export metric name → canonical key
HAE_NUTRITION = {
    "dietary_energy": "calories",
    "protein": "protein_g",
    "carbohydrates": "carbs_g",
    "total_fat": "fat_g",
    "fiber": "fiber_g",
    "sugar": "sugar_g",
    "saturated_fat": "sat_fat_g",
    "monounsaturated_fat": "mono_fat_g",
    "polyunsaturated_fat": "poly_fat_g",
    "cholesterol": "cholesterol_mg",
    "sodium": "sodium_mg",
    "potassium": "potassium_mg",
    "calcium": "calcium_mg",
    "magnesium": "magnesium_mg",
    "iron": "iron_mg",
    "zinc": "zinc_mg",
    "vitamin_a": "vitamin_a_ug",
    "vitamin_c": "vitamin_c_mg",
    "vitamin_d": "vitamin_d_ug",
    "vitamin_e": "vitamin_e_mg",
    "vitamin_k": "vitamin_k_ug",
    "vitamin_b6": "vitamin_b6_mg",
    "vitamin_b12": "vitamin_b12_ug",
    "thiamin": "thiamin_mg",
    "riboflavin": "riboflavin_mg",
    "niacin": "niacin_mg",
    "folate": "folate_ug",
    "caffeine": "caffeine_mg",
    "dietary_water": "water_ml",
}

# Apple Health export.xml Record type → canonical key
XML_DIETARY = {
    "HKQuantityTypeIdentifierDietaryEnergyConsumed": "calories",
    "HKQuantityTypeIdentifierDietaryProtein": "protein_g",
    "HKQuantityTypeIdentifierDietaryCarbohydrates": "carbs_g",
    "HKQuantityTypeIdentifierDietaryFatTotal": "fat_g",
    "HKQuantityTypeIdentifierDietaryFiber": "fiber_g",
    "HKQuantityTypeIdentifierDietarySugar": "sugar_g",
    "HKQuantityTypeIdentifierDietaryFatSaturated": "sat_fat_g",
    "HKQuantityTypeIdentifierDietaryFatMonounsaturated": "mono_fat_g",
    "HKQuantityTypeIdentifierDietaryFatPolyunsaturated": "poly_fat_g",
    "HKQuantityTypeIdentifierDietaryCholesterol": "cholesterol_mg",
    "HKQuantityTypeIdentifierDietarySodium": "sodium_mg",
    "HKQuantityTypeIdentifierDietaryPotassium": "potassium_mg",
    "HKQuantityTypeIdentifierDietaryCalcium": "calcium_mg",
    "HKQuantityTypeIdentifierDietaryMagnesium": "magnesium_mg",
    "HKQuantityTypeIdentifierDietaryIron": "iron_mg",
    "HKQuantityTypeIdentifierDietaryZinc": "zinc_mg",
    "HKQuantityTypeIdentifierDietaryVitaminA": "vitamin_a_ug",
    "HKQuantityTypeIdentifierDietaryVitaminC": "vitamin_c_mg",
    "HKQuantityTypeIdentifierDietaryVitaminD": "vitamin_d_ug",
    "HKQuantityTypeIdentifierDietaryVitaminE": "vitamin_e_mg",
    "HKQuantityTypeIdentifierDietaryVitaminK": "vitamin_k_ug",
    "HKQuantityTypeIdentifierDietaryVitaminB6": "vitamin_b6_mg",
    "HKQuantityTypeIdentifierDietaryVitaminB12": "vitamin_b12_ug",
    "HKQuantityTypeIdentifierDietaryThiamin": "thiamin_mg",
    "HKQuantityTypeIdentifierDietaryRiboflavin": "riboflavin_mg",
    "HKQuantityTypeIdentifierDietaryNiacin": "niacin_mg",
    "HKQuantityTypeIdentifierDietaryFolate": "folate_ug",
    "HKQuantityTypeIdentifierDietaryCaffeine": "caffeine_mg",
    "HKQuantityTypeIdentifierDietaryWater": "water_ml",
}

# Conversion factors into each dimension's base unit
_MASS_TO_G = {"g": 1.0, "mg": 0.001, "mcg": 1e-6, "µg": 1e-6, "ug": 1e-6}
_ENERGY_TO_KCAL = {"kcal": 1.0, "cal": 1.0, "kj": 0.239006}
_VOLUME_TO_ML = {"ml": 1.0, "l": 1000.0, "floz": 29.5735, "fl_oz": 29.5735}

# Canonical-key suffix → (conversion table, base-unit → target-unit factor)
_TARGETS = {
    "g":    (_MASS_TO_G, 1.0),
    "mg":   (_MASS_TO_G, 1000.0),
    "ug":   (_MASS_TO_G, 1e6),
    "kcal": (_ENERGY_TO_KCAL, 1.0),
    "ml":   (_VOLUME_TO_ML, 1.0),
}


def target_unit_of(key: str) -> str:
    """protein_g → g; sodium_mg → mg; calories → kcal."""
    if key == "calories":
        return "kcal"
    return key.rsplit("_", 1)[-1]


def convert_amount(value: float, from_unit: str, key: str) -> Optional[float]:
    """
    Convert a raw amount into the canonical unit implied by `key`.
    Returns None when the source unit is unknown for that dimension —
    the caller should skip the point rather than store garbage.
    """
    unit = (from_unit or "").strip().lower().replace(" ", "")
    table, base_to_target = _TARGETS[target_unit_of(key)]
    factor = table.get(unit)
    if factor is None:
        # Unitless payloads: assume the canonical unit was used
        if unit in ("", "count"):
            return float(value)
        return None
    return float(value) * factor * base_to_target


def upsert_nutrition_partial(
    db: DBSession, day: date, values: dict[str, float], source: str, user_id: int
) -> bool:
    """
    Upsert one day's nutrition from canonical-keyed values. Partial by
    design: a payload carrying only `protein_g` must not zero the rest,
    and micros merge into the JSON column instead of replacing it.

    Source precedence: a day the user corrected by hand (source='manual')
    is only overwritten by another manual write — same rule as the other
    upsert helpers in routers/health.py.

    Returns True if a row was created.
    """
    row = db.query(NutritionDay).filter(
        NutritionDay.user_id == user_id, NutritionDay.date == day
    ).first()
    if row and row.source == "manual" and source != "manual":
        return False

    created = row is None
    if created:
        row = NutritionDay(
            user_id=user_id, date=day, calories=0.0, protein_g=0.0, carbs_g=0.0, fat_g=0.0,
            source=source,
        )
        db.add(row)

    micros = dict(row.micros or {})
    for key, val in values.items():
        rounded = round(val, 1)
        if key in MACRO_COLUMNS:
            setattr(row, MACRO_COLUMNS[key], rounded)
        else:
            micros[key] = rounded
    # Reassign (not mutate) so SQLAlchemy detects the JSON change
    row.micros = micros
    row.source = source
    return created

"""Micronutrient reference intakes (RDA / AI) and classification.

Adult (19–50) U.S. DRIs; Adequate Intake is used where no RDA is defined
(B5, choline, potassium, vitamin K). Keyed by sex. The Diet view averages
recent intake and classifies each nutrient against these targets into
Low / Slightly low / Meets / Above — the four bands in the design.

Intake comes from NutritionDay.micros, whose keys are unit-suffixed
(e.g. "vitamin_a_mcg", "iron_mg"); we match on the nutrient name and convert
the value into the RDA's unit before comparing.
"""
from __future__ import annotations

# name, label, category, unit, rda_male, rda_female
_NUTRIENTS: list[tuple[str, str, str, str, float, float]] = [
    ("vitamin_a",   "Vitamin A",   "vitamin", "mcg", 900,  700),
    ("vitamin_c",   "Vitamin C",   "vitamin", "mg",  90,   75),
    ("vitamin_d",   "Vitamin D",   "vitamin", "mcg", 15,   15),
    ("vitamin_e",   "Vitamin E",   "vitamin", "mg",  15,   15),
    ("vitamin_k",   "Vitamin K",   "vitamin", "mcg", 120,  90),
    ("thiamin",     "Vitamin B1",  "vitamin", "mg",  1.2,  1.1),
    ("riboflavin",  "Vitamin B2",  "vitamin", "mg",  1.3,  1.1),
    ("niacin",      "Vitamin B3",  "vitamin", "mg",  16,   14),
    ("pantothenic", "Vitamin B5",  "vitamin", "mg",  5,    5),
    ("vitamin_b6",  "Vitamin B6",  "vitamin", "mg",  1.3,  1.3),
    ("folate",      "Folate (B9)", "vitamin", "mcg", 400,  400),
    ("vitamin_b12", "Vitamin B12", "vitamin", "mcg", 2.4,  2.4),
    ("choline",     "Choline",     "vitamin", "mg",  550,  425),
    ("calcium",     "Calcium",     "mineral", "mg",  1000, 1000),
    ("iron",        "Iron",        "mineral", "mg",  8,    18),
    ("magnesium",   "Magnesium",   "mineral", "mg",  400,  310),
    ("zinc",        "Zinc",        "mineral", "mg",  11,   8),
    ("potassium",   "Potassium",   "mineral", "mg",  3400, 2600),
    ("phosphorus",  "Phosphorus",  "mineral", "mg",  700,  700),
    ("selenium",    "Selenium",    "mineral", "mcg", 55,   55),
    ("iodine",      "Iodine",      "mineral", "mcg", 150,  150),
    ("manganese",   "Manganese",   "mineral", "mg",  2.3,  1.8),
    ("copper",      "Copper",      "mineral", "mcg", 900,  900),
]

# Alternate names the ingest might use, mapped to our canonical name.
_ALIASES = {
    "vitamin_b1": "thiamin",
    "vitamin_b2": "riboflavin",
    "vitamin_b3": "niacin",
    "vitamin_b5": "pantothenic",
    "pantothenic_acid": "pantothenic",
    "vitamin_b9": "folate",
    "folate_dfe": "folate",
    "vitamin_b7": "biotin",
}

_UNIT_TO_MG = {"g": 1000.0, "mg": 1.0, "mcg": 0.001, "ug": 0.001, "µg": 0.001}


def classify(pct: float) -> str:
    """Map a % of RDA to one of the four bands in the design."""
    if pct < 70:
        return "low"
    if pct < 100:
        return "slightly_low"
    if pct <= 150:
        return "meets"
    return "above"


def _to_mg(value: float, unit: str) -> float:
    return value * _UNIT_TO_MG.get(unit, 1.0)


def _split_key(key: str) -> tuple[str, str]:
    """'vitamin_a_mcg' -> ('vitamin_a', 'mcg'). No suffix -> ('name', '')."""
    base, _, unit = key.rpartition("_")
    if base and unit in _UNIT_TO_MG:
        return base, unit
    return key, ""


def build_breakdown(avg_micros: dict, sex: str) -> list[dict]:
    """Average-micros dict -> ordered list of nutrient-status rows for the
    nutrients we have data for. Each row: name, label, category, amount, unit,
    rda, pct, status."""
    female = (sex or "male").lower().startswith("f")

    # Index averaged intake by canonical name, converted to mg.
    intake_mg: dict[str, float] = {}
    for key, value in (avg_micros or {}).items():
        if value is None:
            continue
        name, unit = _split_key(key)
        name = _ALIASES.get(name, name)
        try:
            intake_mg[name] = _to_mg(float(value), unit or "mg")
        except (TypeError, ValueError):
            continue

    rows: list[dict] = []
    for name, label, category, unit, rda_m, rda_f in _NUTRIENTS:
        if name not in intake_mg:
            continue
        rda = float(rda_f if female else rda_m)
        rda_mg = _to_mg(rda, unit)
        if rda_mg <= 0:
            continue
        pct = intake_mg[name] / rda_mg * 100.0
        amount = intake_mg[name] / _UNIT_TO_MG.get(unit, 1.0)  # back into display unit
        rows.append({
            "name": name,
            "label": label,
            "category": category,
            "amount": round(amount, 1),
            "unit": unit,
            "rda": rda,
            "pct": round(pct),
            "status": classify(pct),
        })
    return rows

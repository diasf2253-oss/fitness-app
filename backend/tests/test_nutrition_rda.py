"""Micronutrient RDA classification — pure-function unit tests."""
from app import nutrition_rda as rda


def test_classify_bands():
    assert rda.classify(50) == "low"
    assert rda.classify(69.9) == "low"
    assert rda.classify(70) == "slightly_low"
    assert rda.classify(99) == "slightly_low"
    assert rda.classify(100) == "meets"
    assert rda.classify(150) == "meets"
    assert rda.classify(151) == "above"


def test_build_breakdown_male():
    micros = {"vitamin_c_mg": 180, "iron_mg": 12, "vitamin_d_mcg": 7.5}
    by = {r["name"]: r for r in rda.build_breakdown(micros, "male")}
    assert by["vitamin_c"]["pct"] == 200 and by["vitamin_c"]["status"] == "above"
    assert by["iron"]["pct"] == 150 and by["iron"]["status"] == "meets"   # 12 / 8
    assert by["vitamin_d"]["status"] == "low"                              # 7.5 / 15 = 50%


def test_build_breakdown_female_iron_differs():
    rows = rda.build_breakdown({"iron_mg": 12}, "female")
    iron = next(r for r in rows if r["name"] == "iron")
    assert iron["pct"] == 67 and iron["status"] == "low"                   # 12 / 18


def test_alias_and_units():
    # 'vitamin_b1_mg' aliases to thiamin; 1.2 mg / 1.2 mg RDA = 100%
    rows = rda.build_breakdown({"vitamin_b1_mg": 1.2}, "male")
    b1 = next(r for r in rows if r["name"] == "thiamin")
    assert b1["pct"] == 100 and b1["label"] == "Vitamin B1"


def test_grams_convert_to_mg():
    # calcium given in grams should convert (1.0 g = 1000 mg = 100% of 1000 mg)
    rows = rda.build_breakdown({"calcium_g": 1.0}, "male")
    ca = next(r for r in rows if r["name"] == "calcium")
    assert ca["pct"] == 100


def test_unknown_nutrient_skipped():
    rows = rda.build_breakdown({"sodium_mg": 2300, "made_up_mg": 5}, "male")
    names = {r["name"] for r in rows}
    assert "made_up" not in names

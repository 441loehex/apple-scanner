"""Caliber class boundary tests — all 8 class edges."""

from apple_caliber_scan.services.estimation import CALIBER_CLASS_LABELS, classify_diameter


def test_class_0_60_low():
    assert classify_diameter(0.0) == "0-60"


def test_class_0_60_high():
    assert classify_diameter(59.9) == "0-60"


def test_class_60_65_lower():
    assert classify_diameter(60.0) == "60-65"


def test_class_60_65_upper():
    assert classify_diameter(64.9) == "60-65"


def test_class_65_70():
    assert classify_diameter(65.0) == "65-70"


def test_class_70_75():
    assert classify_diameter(70.0) == "70-75"


def test_class_75_80():
    assert classify_diameter(75.0) == "75-80"


def test_class_80_85():
    assert classify_diameter(80.0) == "80-85"


def test_class_85_90():
    assert classify_diameter(85.0) == "85-90"


def test_class_90_plus():
    assert classify_diameter(90.0) == "90+"


def test_class_90_plus_large():
    assert classify_diameter(150.0) == "90+"


def test_class_74_9_is_70_75():
    assert classify_diameter(74.9) == "70-75"


def test_class_75_is_75_80():
    assert classify_diameter(75.0) == "75-80"


def test_exact_class_labels():
    assert CALIBER_CLASS_LABELS == [
        "0-60", "60-65", "65-70", "70-75", "75-80", "80-85", "85-90", "90+"
    ]

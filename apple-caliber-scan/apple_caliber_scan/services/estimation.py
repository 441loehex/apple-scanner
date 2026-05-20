"""Caliber classification, 75+ share, weight heuristics, and confidence model."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

CALIBER_CLASSES: list[tuple[float, float, str]] = [
    (0.0, 60.0, "0-60"),
    (60.0, 65.0, "60-65"),
    (65.0, 70.0, "65-70"),
    (70.0, 75.0, "70-75"),
    (75.0, 80.0, "75-80"),
    (80.0, 85.0, "80-85"),
    (85.0, 90.0, "85-90"),
    (90.0, float("inf"), "90+"),
]

CALIBER_CLASS_LABELS = [label for _, _, label in CALIBER_CLASSES]

ABOVE_75_CLASSES = {"75-80", "80-85", "85-90", "90+"}


class ConfidenceLevel(str, Enum):  # noqa: UP042
    HIGH = "wysoka"
    MEDIUM = "średnia"
    LOW = "niska"
    UNCALIBRATED = "brak kalibracji"


def classify_diameter(diameter_mm: float) -> str:
    """Map diameter in mm to caliber class label. Lower bound inclusive, upper exclusive."""
    for low, high, label in CALIBER_CLASSES:
        if low <= diameter_mm < high:
            return label
    return "90+"


@dataclass
class CaliberDistribution:
    counts: dict[str, int] = field(
        default_factory=lambda: {lb: 0 for _, _, lb in CALIBER_CLASSES}
    )
    total: int = 0

    def add(self, label: str) -> None:
        self.counts[label] = self.counts.get(label, 0) + 1
        self.total += 1

    def fraction(self, label: str) -> float:
        if self.total == 0:
            return 0.0
        return self.counts.get(label, 0) / self.total

    def pct(self, label: str) -> float:
        return self.fraction(label) * 100.0

    @property
    def above_75_share(self) -> float:
        if self.total == 0:
            return 0.0
        count_75plus = sum(self.counts.get(c, 0) for c in ABOVE_75_CLASSES)
        return count_75plus / self.total * 100.0


def diameter_to_mass_g(diameter_mm: float) -> float:
    """
    Geometric heuristic: mass ≈ volume × density × shape correction.
    NOT a weighed measurement — geometric estimate only.
    """
    radius_cm = (diameter_mm / 2.0) / 10.0
    volume_cm3 = (4.0 / 3.0) * math.pi * (radius_cm**3)
    return volume_cm3 * 0.85 * 0.85


def compute_distribution(diameters_mm: list[float]) -> CaliberDistribution:
    dist = CaliberDistribution()
    for d in diameters_mm:
        dist.add(classify_diameter(d))
    return dist


def batch_projection_confidence(
    has_ground_truth: bool, calibration_ok: bool
) -> ConfidenceLevel:
    if not calibration_ok:
        return ConfidenceLevel.UNCALIBRATED
    if not has_ground_truth:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.HIGH


@dataclass
class ClassEstimate:
    label: str
    count: int
    pct: float
    weight_kg: float
    weight_pct: float


def estimate_batch(
    distribution: CaliberDistribution,
    total_weight_kg: float,
) -> list[ClassEstimate]:
    """
    Project top-layer distribution across full batch weight.
    Returns per-class weight estimates (Szacunkowa masa — heurystyczna).
    Always labeled as estimate (SZACUNEK).
    """
    if distribution.total == 0:
        return [
            ClassEstimate(label=lb, count=0, pct=0.0, weight_kg=0.0, weight_pct=0.0)
            for _, _, lb in CALIBER_CLASSES
        ]

    result = []
    total_weight_assigned = 0.0
    estimates: list[tuple[str, int, float, float]] = []

    for _, _, label in CALIBER_CLASSES:
        count = distribution.counts.get(label, 0)
        frac = count / distribution.total
        weight_kg = frac * total_weight_kg
        estimates.append((label, count, frac * 100.0, weight_kg))
        total_weight_assigned += weight_kg

    total_w = sum(e[3] for e in estimates) or 1.0
    for label, count, pct, weight_kg in estimates:
        result.append(ClassEstimate(
            label=label,
            count=count,
            pct=pct,
            weight_kg=round(weight_kg, 1),
            weight_pct=round(weight_kg / total_w * 100.0, 1),
        ))

    return result

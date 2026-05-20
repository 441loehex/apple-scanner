"""Ring-based scale factor computation and calibration confidence."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from apple_caliber_scan.scan.detector import Circle

logger = logging.getLogger(__name__)

MIN_PLAUSIBLE_APPLE_MM = 40.0
MAX_PLAUSIBLE_APPLE_MM = 120.0
MIN_RING_RADIUS_PX = 5.0


@dataclass
class CalibrationResult:
    scale_factor_mm_per_px: float
    confidence: str  # 'ok' | 'low'
    warning: str | None


def compute_scale_factor(
    ring_circle: Circle,
    ring_mm: float = 75.0,
    apple_circles: list[Circle] | None = None,
) -> CalibrationResult:
    """
    Compute scale factor from ring circle.
    scale_factor = ring_mm / (ring_circle.radius_px * 2)
    Validates plausibility against apple circle diameters.
    """
    ring_diameter_px = ring_circle.caliber_diameter_px

    if ring_diameter_px < MIN_RING_RADIUS_PX * 2:
        return CalibrationResult(
            scale_factor_mm_per_px=ring_mm / max(ring_diameter_px, 1.0),
            confidence="low",
            warning=(
                f"Pierścień wykryty jako bardzo mały ({ring_diameter_px:.1f} px) — "
                "możliwy błąd detekcji. Sprawdź adnotację."
            ),
        )

    scale = ring_mm / ring_diameter_px

    # Sanity check: apply scale to apple circles
    if apple_circles:
        apple_diameters = [c.caliber_diameter_px * scale for c in apple_circles]
        mean_d = sum(apple_diameters) / len(apple_diameters)

        if mean_d < MIN_PLAUSIBLE_APPLE_MM:
            return CalibrationResult(
                scale_factor_mm_per_px=scale,
                confidence="low",
                warning=(
                    f"Średnica jabłek po kalibracji ({mean_d:.1f} mm) jest podejrzanie mała. "
                    "Sprawdź, czy zaznaczono właściwy pierścień."
                ),
            )
        if mean_d > MAX_PLAUSIBLE_APPLE_MM:
            return CalibrationResult(
                scale_factor_mm_per_px=scale,
                confidence="low",
                warning=(
                    f"Średnica jabłek po kalibracji ({mean_d:.1f} mm) jest podejrzanie duża. "
                    "Sprawdź, czy zaznaczono właściwy pierścień."
                ),
            )

    return CalibrationResult(
        scale_factor_mm_per_px=scale,
        confidence="ok",
        warning=None,
    )

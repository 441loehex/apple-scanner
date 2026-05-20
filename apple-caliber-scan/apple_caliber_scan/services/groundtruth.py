"""Ground truth import stub and comparison logic."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, cast

from apple_caliber_scan.database.crud import get_ground_truth, insert_ground_truth
from apple_caliber_scan.services.estimation import CALIBER_CLASS_LABELS


def import_ground_truth(
    conn: sqlite3.Connection,
    batch_id: int,
    grader_results: dict[str, int],
    source: str = "manual",
    weight_kg: float | None = None,
    graded_at: str | None = None,
    notes: str | None = None,
) -> int:
    """Import grader ground truth counts per caliber class."""
    # Validate keys
    for key in grader_results:
        if key not in CALIBER_CLASS_LABELS:
            raise ValueError(f"Unknown caliber class in ground truth: {key!r}")

    return insert_ground_truth(
        conn,
        batch_id=batch_id,
        grader_results=grader_results,
        source=source,
        weight_kg=weight_kg,
        graded_at=graded_at,
        notes=notes,
    )


def compare_with_ground_truth(
    scan_distribution: dict[str, int],
    grader_results: dict[str, int],
) -> list[dict[str, Any]]:
    """
    Compare scan top-layer distribution against grader ground truth.
    Returns list of {label, scan_pct, grader_pct, deviation_pp} dicts.
    """
    scan_total = sum(scan_distribution.values()) or 1
    gt_total = sum(grader_results.values()) or 1

    rows = []
    for label in CALIBER_CLASS_LABELS:
        scan_pct = scan_distribution.get(label, 0) / scan_total * 100
        gt_pct = grader_results.get(label, 0) / gt_total * 100
        rows.append({
            "label": label,
            "scan_pct": round(scan_pct, 1),
            "grader_pct": round(gt_pct, 1),
            "deviation_pp": round(scan_pct - gt_pct, 1),
        })
    return rows


def get_latest_ground_truth(
    conn: sqlite3.Connection, batch_id: int
) -> dict[str, int] | None:
    rows = get_ground_truth(conn, batch_id)
    if not rows:
        return None
    latest = rows[0]
    return cast("dict[str, int]", json.loads(latest["grader_results"]))

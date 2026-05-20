# Testing Guide — Apple Caliber Scan

**Freshora Sp. Z. o. o.**

---

## Running Tests

```bash
make test
# OR
PYTHONPATH=. .venv/bin/pytest tests/ -v
```

Expected result: **65 passed, 0 failed.**

All tests are deterministic — no network calls, no random seeds, no external services.

---

## Test Modules

### `tests/test_caliber.py` — Caliber boundary classification

Tests all 8 caliber class boundaries:
- Exact boundary values (e.g., 60.0 mm → "60-65", not "0-60")
- Values just inside each class
- Values just outside (boundary exclusivity)
- The 90+ class has no upper bound

Priority: **high** — boundary errors cause systematic miscounting of the 75+ share.

### `tests/test_calibration.py` — Scale factor computation

Tests:
- Basic scale factor arithmetic (`ring_mm / ring_diameter_px`)
- Small ring diameter → LOW confidence warning
- Apple diameters outside plausible range → LOW confidence warning
- Scale correctly applied to apple pixel diameters
- Normal inputs → no warning

### `tests/test_drive.py` — Google Drive URL parsing

Tests all 3 Google Drive URL formats:
- `/file/d/<id>/view` format
- `id=<id>` query parameter format
- `/open?id=<id>` format
- Non-Drive URLs → returns None
- Complex file IDs (hyphens, underscores)

### `tests/test_estimation.py` — Distribution computation

Tests:
- 75+ share math (sum of 75-80, 80-85, 85-90, 90+ counts / total)
- Confidence guardrail: HIGH requires ground truth
- `estimate_batch()` returns all 8 caliber classes
- Totals are internally consistent (sum == total apple count)

### `tests/test_ingest.py` — Scan pipeline

Tests using synthetic crate fixture:
- Synthetic crate is non-empty (N > 0)
- Shape is (N, 3)
- Deterministic at fixed seed
- Different seeds produce different point clouds
- XY coordinates normalized to [0, 1]
- Preview PNG is created at expected path
- Circles are detected (at least 1)
- Detected objects are `Circle` instances with required fields

### `tests/test_reporting.py` — Report generation

Tests on synthetic data with known distribution:
- Count totals match across report context
- Percentage values sum to ~100%
- Legal clause is present in HTML output
- Company name "Freshora" appears in report
- Report title is in Polish
- 75mm share section is rendered
- All 8 caliber class labels appear in output
- Low confidence warning shown when confidence is LOW
- Seller name appears in report context

### `tests/test_web.py` — Web UI routes

Tests using FastAPI TestClient:
- Login page loads (GET /login → 200)
- Correct credentials → 303 redirect
- Wrong password → 200 with error message
- Unauthenticated GET / → 302 redirect to /login
- Authenticated GET / → 200 with batch list
- POST /batches → creates batch → 303 redirect
- GET /batches/{id} → shows batch detail
- GET /api/varieties → returns JSON list
- Pre-seeded variety names present in variety list
- POST /logout → clears session

---

## Test Fixtures (`tests/conftest.py`)

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `set_required_env` | session, autouse | Patches config with test env vars |
| `tmp_db` | function | Creates temporary SQLite DB, returns path |
| `synthetic_points` | function | Returns (N,3) float32 point cloud |
| `test_client` | function | Unauthenticated FastAPI TestClient |
| `auth_client` | function | TestClient with active session cookie |

The `set_required_env` fixture patches `apple_caliber_scan.config` directly rather than
using `monkeypatch.setenv` to avoid order-of-import issues with `os.environ`.

---

## Writing New Tests

Follow these rules:
1. **No network calls.** Mock gdown or skip Drive tests if needed.
2. **Fixed seeds.** Use `seed=42` for all synthetic data.
3. **No temp file leaks.** Use `tmp_path` (pytest built-in) for file output.
4. **No real DB.** Use `tmp_db` fixture (creates in-memory or temp-file DB).
5. **Test the boundary, not the middle.** Caliber class tests should hit exact boundaries.

### Example: adding a calibration test

```python
def test_very_large_ring_accepted():
    """Ring with 300px diameter should not trigger low confidence by itself."""
    ring = Circle(cx=0.5, cy=0.5, radius=150)
    result = compute_scale_factor(ring, ring_mm=75.0)
    assert result.scale_factor_mm_per_px == pytest.approx(75.0 / 300, rel=1e-4)
    assert "diameter" not in (result.warning or "")
```

---

## Continuous Integration

Tests are intended to run in CI on every push. The Makefile target:

```bash
make test
```

exits with code 0 on success, non-zero on any failure. Add this as the CI gate.

Lint must also pass:

```bash
make lint
```

Both must pass before merging any PR.

---

## Known Test Gaps

These areas are not yet covered by automated tests and are tracked for future sprints:

- Full end-to-end web flow (scan attach → annotate → report download)
- Telegram FSM state transitions
- PDF generation (WeasyPrint output validation)
- OBJ/GLB file loading (only PLY is tested via synthetic fixture)
- Edge cases in point cloud normalization with degenerate inputs

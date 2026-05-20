---
name: diagnose-before-ship
description: Forces reproduction, log inspection, and failing-test capture before any bug fix.
---

Procedure (must follow in order):

1. State the observed failure with exact error message or symptom.
2. Identify the smallest command/test that reproduces it (`pytest tests/specific_test.py::test_name`).
3. Capture exact logs without secrets.
4. Add or identify a failing test that encodes the expected correct behavior.
5. Explain root cause in one paragraph.
6. Patch only after steps 1-5 are complete.
7. Re-run the failing test: `PYTHONPATH=. .venv/bin/pytest tests/target_test.py -v`.
8. Run full gate: `make test && make lint && make typecheck && make smoke`.

Never patch and then write the test. Test first, patch second.

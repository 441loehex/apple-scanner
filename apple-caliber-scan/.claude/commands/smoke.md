Run in order:
1. .venv/bin/python -c "import apple_caliber_scan; print('Import OK')"
2. PYTHONPATH=. .venv/bin/python -m apple_caliber_scan init-db
3. PYTHONPATH=. .venv/bin/python -m apple_caliber_scan sample-report --output-dir /tmp/acs-smoke
Report pass/fail for each step.

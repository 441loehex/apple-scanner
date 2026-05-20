.PHONY: all setup install-system-deps install-python-deps init-db test lint typecheck \
        smoke sample-report run-web run-bot clean help

help:
	@echo "apple-caliber-scan — available commands:"
	@echo "  make setup              — install all deps (system + python)"
	@echo "  make init-db            — initialize SQLite database"
	@echo "  make sample-report      — generate Polish sample report"
	@echo "  make test               — run all tests"
	@echo "  make lint               — run ruff linter"
	@echo "  make typecheck          — run mypy"
	@echo "  make smoke              — quick smoke test (import + init-db + sample-report)"
	@echo "  make run-web            — start FastAPI web app on :8000"
	@echo "  make run-bot            — start Telegram bot"
	@echo "  make clean              — remove generated artifacts"

setup: install-system-deps install-python-deps

install-system-deps:
	sudo apt-get update -qq
	sudo apt-get install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
	  libgdk-pixbuf2.0-0 libffi-dev shared-mime-info libgirepository1.0-dev \
	  python3-dev python3-pip python3-venv

install-python-deps:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

init-db:
	PYTHONPATH=. .venv/bin/python -m apple_caliber_scan init-db

sample-report:
	mkdir -p sample-output
	PYTHONPATH=. .venv/bin/python -m apple_caliber_scan sample-report --output-dir sample-output

test:
	PYTHONPATH=. .venv/bin/pytest tests/ -v

lint:
	.venv/bin/ruff check apple_caliber_scan tests

typecheck:
	.venv/bin/mypy apple_caliber_scan --ignore-missing-imports

smoke:
	PYTHONPATH=. .venv/bin/python -c "import apple_caliber_scan; print('Import OK')"
	$(MAKE) init-db
	$(MAKE) sample-report
	@echo "Smoke test passed."

run-web:
	PYTHONPATH=. .venv/bin/uvicorn apple_caliber_scan.web.app:create_app --factory \
	  --host 0.0.0.0 --port 8000 --reload

run-bot:
	PYTHONPATH=. .venv/bin/python -m apple_caliber_scan run-bot

clean:
	rm -rf sample-output/ data/generated/ __pycache__/ .mypy_cache/ .pytest_cache/ \
	       apple_caliber_scan/__pycache__/ tests/__pycache__/

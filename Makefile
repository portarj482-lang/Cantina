# Makefile - Development & CI Automation
.PHONY: help install dev-install test test-unit lint typecheck clean audit db-up db-down

help:
	@echo "Cantina Repository Steward Automation"
	@echo "Targets:"
	@echo "  install        Install runtime dependencies"
	@echo "  dev-install    Install dev dependencies & package in editable mode"
	@echo "  test           Run all unit tests"
	@echo "  lint           Run code linter"
	@echo "  typecheck      Run mypy static type check"
	@echo "  clean          Dry-run local artifact cleanup (scripts/clean-local.sh)"
	@echo "  clean-confirm  Execute local artifact cleanup"
	@echo "  audit          Run repository hygiene and secret checks"

install:
	pip install -r requirements.txt

dev-install:
	pip install -r requirements.txt
	pip install -e ".[dev]"

test: test-unit

test-unit:
	python3 -m unittest discover -s tests/universal_adaptive -v

lint:
	python3 -m ruff check universal_adaptive_engine tests

typecheck:
	python3 -m mypy universal_adaptive_engine

clean:
	./scripts/clean-local.sh --dry-run

clean-confirm:
	./scripts/clean-local.sh --confirm

audit:
	@echo "Checking for tracked secret or transient runtime artifacts..."
	@TRACKED=$$(git ls-files | grep -E '(\.env($$|\.local)|node_modules/|__pycache__/|\.pytest_cache/|\.log$$|\.pid$$|\.so$$|\.dylib$$)' || true); \
	if [ -n "$$TRACKED" ]; then \
		echo "ERROR: Tracked transient or secret artifacts detected:"; \
		echo "$$TRACKED"; \
		exit 1; \
	fi
	@echo "Audit OK: Zero tracked transient runtime artifacts."

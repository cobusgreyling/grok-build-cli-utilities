.PHONY: help install dev-install lint format typecheck test cov build clean pre-commit

PYTHON ?= python3

help:
	@echo "grok-build-cli-utilities development tasks"
	@echo ""
	@echo "  make install       Install the package (non-editable)"
	@echo "  make dev-install   Install editable with dev deps (recommended)"
	@echo "  make lint          Run ruff check"
	@echo "  make format        Run ruff format (writes files)"
	@echo "  make typecheck     Run mypy"
	@echo "  make test          Run pytest"
	@echo "  make cov           Run pytest with coverage report"
	@echo "  make build         Build sdist + wheel"
	@echo "  make clean         Remove build artifacts, caches, egg-info"
	@echo "  make pre-commit    Install and run pre-commit hooks on all files"
	@echo ""

install:
	$(PYTHON) -m pip install .

dev-install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

typecheck:
	$(PYTHON) -m mypy src/grok_build_cli_utilities --ignore-missing-imports

test:
	$(PYTHON) -m pytest -q

cov:
	$(PYTHON) -m pytest -q --cov=src/grok_build_cli_utilities --cov-report=term-missing

build:
	$(PYTHON) -m build

clean:
	rm -rf build/ dist/ *.egg-info src/grok_build_cli_utilities.egg-info .coverage coverage.xml .pytest_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

pre-commit:
	$(PYTHON) -m pre_commit install
	$(PYTHON) -m pre_commit run --all-files

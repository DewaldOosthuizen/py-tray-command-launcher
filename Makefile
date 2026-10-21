SHELL := /usr/bin/env bash

PYTHON ?= $(shell if command -v python3.12 >/dev/null 2>&1; then command -v python3.12; else command -v python3; fi)
PIP ?= pip
PYTEST ?= pytest
RUFF ?= ruff
PIP_MIN_SAFE ?= 26.1.2
WHEEL_MIN_SAFE ?= 0.46.2
PYINSTALLER ?= pyinstaller
CI_VENV ?= .venv
CI_VENV_PIP = $(CI_VENV)/bin/pip
CI_VENV_PIP_AUDIT = $(CI_VENV)/bin/pip-audit
CI_VENV_PYINSTALLER = $(CI_VENV)/bin/pyinstaller
VERSION ?= local
LOG_DIR ?= .ci-logs

.DEFAULT_GOAL := help

.PHONY: help install-dev lint test audit build ci
help: ## List all Make targets and their descriptions
	@awk 'BEGIN {FS = ":.*##"} /^[^#[:space:]][^:]*:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: start
start: ## Start the application
	source venv/bin/activate && python src/main.py



.PHONY: install-dev
install-dev: ## Install the project and development dependencies
	$(PYTHON) -m venv $(CI_VENV) && $(CI_VENV_PIP) install -e ".[dev]"

.PHONY: lint test audit build
lint: ## Run Ruff lint and formatting checks
	$(RUFF) check src/ tests/ --config pyproject.toml && $(RUFF) format --check src/ tests/ --config pyproject.toml

test: ## Run tests with Qt in offscreen mode
	QT_QPA_PLATFORM=offscreen $(PYTEST)

audit: ## Install audit tooling and scan project dependencies in an isolated environment
	$(PYTHON) -m venv $(CI_VENV)
	$(CI_VENV_PIP) install --upgrade "pip>=$(PIP_MIN_SAFE)" "wheel>=$(WHEEL_MIN_SAFE)" "setuptools>=83.0.0"
	$(CI_VENV_PIP) install pip-audit
	$(CI_VENV_PIP) install -e ".[dev]"
	@mkdir -p $(LOG_DIR)
	@echo "[audit] Auditing declared project dependencies..."
	@set -o pipefail; $(CI_VENV_PIP_AUDIT) -r requirements.txt 2>&1 | tee "$(LOG_DIR)/pip-audit.log"; status=$${PIPESTATUS[0]}; if [[ $$status -ne 0 ]]; then \
		echo "[FAIL] audit: pip-audit found vulnerabilities"; \
		echo "[DETAIL] This failure is dependency vulnerabilities, not source file linting."; \
		echo "[DETAIL] Vulnerable packages:"; \
		awk 'BEGIN{in_table=0} /^Name[[:space:]]+Version[[:space:]]+ID[[:space:]]+Fix Versions/{in_table=1; next} in_table && /^-/{next} in_table && /^$$/{in_table=0} in_table && NF>=4 {printf "  - %s %s (%s) -> fix: %s\n", $$1, $$2, $$3, $$4}' "$(LOG_DIR)/pip-audit.log" || true; \
		echo "[DETAIL] Full log: $(LOG_DIR)/pip-audit.log"; \
		exit 1; \
	fi
	@echo "[OK] audit passed"

build: ## Build and verify the application executable with PyInstaller
	$(PYTHON) -m venv $(CI_VENV) && $(CI_VENV_PIP) install -r requirements.txt && $(CI_VENV_PIP) install -r requirements-build.txt && $(CI_VENV_PYINSTALLER) py-tray-command-launcher.spec && test -f dist/py-tray-command-launcher

.PHONY: install-system-deps
install-system-deps: ## Install Linux system libraries required by the application
	sudo apt-get update -qq
	sudo apt-get install -y \
		libegl1 \
		libxcb-cursor0 \
		libxcb-icccm4 \
		libxcb-image0 \
		libxcb-keysyms1 \
		libxcb-randr0 \
		libxcb-render-util0 \
		libxcb-shape0 \
		libxcb-xinerama0 \
		libxcb-xkb1 \
		libxkbcommon-x11-0 \
		libdbus-1-3 \
		libglib2.0-0 \
		libgl1 \
		fuse \
		libfuse2

.PHONY: ci-workflow
ci-workflow: ## Install development dependencies and run the test suite
	$(PIP) install --break-system-packages -e ".[dev]"
	$(PYTEST) tests/

.PHONY: tests-workflow
tests-workflow: ## Install Qt system dependencies and run tests offscreen
	sudo apt-get update
	sudo apt-get install -y libegl1 libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0
	$(PIP) install --break-system-packages -e ".[dev]"
	QT_QPA_PLATFORM=offscreen $(PYTEST) --tb=short

.PHONY: lint-ruff
lint-ruff: ## Run Ruff lint and formatting checks with CI logs
	@mkdir -p $(LOG_DIR)
	@echo "[lint-ruff] Running ruff check..."
	@set -o pipefail; $(RUFF) check src/ tests/ --config pyproject.toml 2>&1 | tee "$(LOG_DIR)/ruff-check.log"; status=$${PIPESTATUS[0]}; if [[ $$status -ne 0 ]]; then \
		echo "[FAIL] lint-ruff: ruff check failed (rule violations found)"; \
		echo "[DETAIL] Offending locations:"; \
		grep -E '^[^:]+:[0-9]+:[0-9]+:' "$(LOG_DIR)/ruff-check.log" | head -n 20 || true; \
		echo "[DETAIL] Full log: $(LOG_DIR)/ruff-check.log"; \
		exit 1; \
	fi
	@echo "[lint-ruff] Running ruff format --check..."
	@set -o pipefail; $(RUFF) format --check src/ tests/ --config pyproject.toml 2>&1 | tee "$(LOG_DIR)/ruff-format-check.log"; status=$${PIPESTATUS[0]}; if [[ $$status -ne 0 ]]; then \
		echo "[FAIL] lint-ruff: ruff format --check failed (formatting changes needed)"; \
		echo "[DETAIL] Files requiring formatting:"; \
		grep -E 'Would reformat ' "$(LOG_DIR)/ruff-format-check.log" | sed 's/^/  - /' || true; \
		echo "Hint: run 'ruff format src/ tests/' to auto-format."; \
		echo "[DETAIL] Full log: $(LOG_DIR)/ruff-format-check.log"; \
		exit 1; \
	fi
	@echo "[OK] lint-ruff passed"

.PHONY: lint-test
lint-test: ## Install test dependencies and run the offscreen test suite with CI logs
	@mkdir -p $(LOG_DIR)
	@echo "[lint-test] Installing dev dependencies..."
	@$(PIP) install --break-system-packages -e ".[dev]" || { \
		echo "[FAIL] lint-test: failed to install dev dependencies"; \
		exit 1; \
	}
	@echo "[lint-test] Installing system dependencies..."
	@sudo apt-get update -qq
	@sudo apt-get install -y \
		libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
		libxcb-randr0 libxcb-render-util0 libxcb-xkb1 libxkbcommon-x11-0 libgl1
	@echo "[lint-test] Running pytest..."
	@set -o pipefail; QT_QPA_PLATFORM=offscreen $(PYTEST) 2>&1 | tee "$(LOG_DIR)/lint-pytest.log"; status=$${PIPESTATUS[0]}; if [[ $$status -ne 0 ]]; then \
		echo "[FAIL] lint-test: pytest failed"; \
		echo "[DETAIL] Full log: $(LOG_DIR)/lint-pytest.log"; \
		exit 1; \
	fi
	@echo "[OK] lint-test passed"

.PHONY: lint-audit
lint-audit: ## Run the isolated dependency vulnerability audit
	$(MAKE) audit

.PHONY: lint-workflow
lint-workflow: ## Run Ruff, pytest, and dependency-audit checks
	@echo "[lint-workflow] Running lint-ruff..."
	@$(MAKE) lint-ruff || { echo "[FAIL] lint-workflow stopped at lint-ruff"; exit 1; }
	@echo "[lint-workflow] Running lint-test..."
	@$(MAKE) lint-test || { echo "[FAIL] lint-workflow stopped at lint-test"; exit 1; }
	@echo "[lint-workflow] Running lint-audit..."
	@$(MAKE) lint-audit || { echo "[FAIL] lint-workflow stopped at lint-audit"; exit 1; }
	@echo "[OK] lint-workflow passed"

.PHONY: release-workflow
release-workflow: ## Build and package the release AppImage (VERSION defaults to local)
	sudo apt-get update -qq
	sudo apt-get install -y --no-install-recommends \
		libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
		libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
		libxcb-xkb1 libxkbcommon-x11-0 libegl1 \
		libdbus-1-3 libglib2.0-0 \
		fuse libfuse2
	$(PIP) install --break-system-packages --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-build.txt
	$(PYINSTALLER) py-tray-command-launcher.spec
	test -f dist/py-tray-command-launcher
	@echo "Executable size: $$(du -h dist/py-tray-command-launcher | cut -f1)"
	mkdir -p tools
	if [[ ! -f tools/appimagetool ]]; then \
		wget -q -O tools/appimagetool https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage; \
		chmod +x tools/appimagetool; \
	fi
	rm -rf AppDir
	mkdir -p AppDir/usr/bin AppDir/usr/share/applications AppDir/usr/share/pixmaps
	cp dist/py-tray-command-launcher AppDir/usr/bin/
	cp packaging/py-tray-command-launcher.desktop AppDir/
	cp resources/icons/branding/icon.png AppDir/py-tray-command-launcher.png
	cp resources/icons/branding/icon.png AppDir/usr/share/pixmaps/py-tray-command-launcher.png
	mkdir -p AppDir/usr/bin/resources/themes
	cp -r resources/themes/. AppDir/usr/bin/resources/themes/
	printf '%s\n' '#!/bin/bash' \
		'APPDIR="$$(dirname "$$(readlink -f "$$0")")"' \
		'export PATH="$$APPDIR/usr/bin:$$PATH"' \
		'export XDG_DATA_DIRS="$$APPDIR/usr/share:$${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"' \
		'exec "$$APPDIR/usr/bin/py-tray-command-launcher" "$$@"' > AppDir/AppRun
	chmod +x AppDir/AppRun
	ARCH=x86_64 ./tools/appimagetool --appimage-extract-and-run AppDir "py-tray-command-launcher-$(VERSION)-x86_64.AppImage"
	test -f "py-tray-command-launcher-$(VERSION)-x86_64.AppImage"
	@echo "AppImage size: $$(du -h py-tray-command-launcher-$(VERSION)-x86_64.AppImage | cut -f1)"

.PHONY: ci
ci: ## Run install, lint, tests, audit, and executable build sequentially
	$(MAKE) install-dev && $(MAKE) lint && $(MAKE) test && $(MAKE) audit && $(MAKE) build

.PHONY: ci-workflow-parity ci-full
ci-workflow-parity: ## Verify both CI workflows use the same Qt test dependencies
	@echo "[ci-workflow-parity] Verifying release.yml test-job qt deps == pr_gate.yml test-job qt deps..."
	@test "$$(sed -n '75,77p' .github/workflows/release.yml | sha256sum)" = "$$(sed -n '64,66p' .github/workflows/pr_gate.yml | sha256sum)" || { echo "[FAIL] ci-workflow-parity: workflow Qt dependency lists diverged"; exit 1; }
	@echo "[OK] ci-workflow-parity: release.yml and pr_gate.yml test jobs share identical Qt system-dependency lists"

.PHONY: ci-full
ci-full: ## Run the local CI gate
	@echo "[ci-full] Running ci..."
	@$(MAKE) ci || { echo "[FAIL] ci-full stopped at ci"; exit 1; }
# 	@echo "[ci-full] Running release-workflow..."
# 	@$(MAKE) release-workflow || { echo "[FAIL] ci-full stopped at release-workflow"; exit 1; }
# 	@echo "[OK] ci-full passed"

SHELL := /usr/bin/env bash

PYTHON ?= python3
PIP ?= pip
PYTEST ?= pytest
RUFF ?= ruff
PIP_AUDIT ?= pip-audit
PYINSTALLER ?= pyinstaller
VERSION ?= local
LOG_DIR ?= .ci-logs

.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "Local CI validation targets"
	@echo ""
	@echo "Core workflows:"
	@echo "  make ci-workflow        # Mirrors .github/workflows/ci.yml"
	@echo "  make tests-workflow     # Mirrors .github/workflows/tests.yml"
	@echo "  make lint-workflow      # Mirrors .github/workflows/lint.yml"
	@echo "  make release-workflow   # Mirrors build/verify steps in .github/workflows/release.yml"
	@echo ""
	@echo "Aggregates:"
	@echo "  make ci 				 # Run ci + tests + lint flows"
	@echo "  make ci-full            # Run all flows, including release build"
	@echo ""
	@echo "Helpers:"
	@echo "  make install-dev        # pip install -e .[dev]"
	@echo "  make install-system-deps"
	@echo ""
	@echo "Optional:"
	@echo "  make release-workflow VERSION=v1.2.3"

.PHONY: install-dev
install-dev:
	$(PIP) install -e ".[dev]"

.PHONY: install-system-deps
install-system-deps:
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
ci-workflow:
	$(PIP) install ".[dev]"
	$(PYTEST) tests/

.PHONY: tests-workflow
tests-workflow:
	sudo apt-get update
	sudo apt-get install -y libegl1 libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0
	$(PIP) install -e ".[dev]"
	QT_QPA_PLATFORM=offscreen $(PYTEST) --tb=short

.PHONY: lint-ruff
lint-ruff:
	@mkdir -p $(LOG_DIR)
	@echo "[lint-ruff] Installing ruff..."
	@$(PIP) install ruff || { \
		echo "[FAIL] lint-ruff: failed to install ruff"; \
		exit 1; \
	}
	@echo "[lint-ruff] Running ruff check..."
	@set -o pipefail; $(RUFF) check src/ tests/ 2>&1 | tee "$(LOG_DIR)/ruff-check.log"; status=$${PIPESTATUS[0]}; if [[ $$status -ne 0 ]]; then \
		echo "[FAIL] lint-ruff: ruff check failed (rule violations found)"; \
		echo "[DETAIL] Offending locations:"; \
		grep -E '^[^:]+:[0-9]+:[0-9]+:' "$(LOG_DIR)/ruff-check.log" | head -n 20 || true; \
		echo "[DETAIL] Full log: $(LOG_DIR)/ruff-check.log"; \
		exit 1; \
	fi
	@echo "[lint-ruff] Running ruff format --check..."
	@set -o pipefail; $(RUFF) format --check src/ tests/ 2>&1 | tee "$(LOG_DIR)/ruff-format-check.log"; status=$${PIPESTATUS[0]}; if [[ $$status -ne 0 ]]; then \
		echo "[FAIL] lint-ruff: ruff format --check failed (formatting changes needed)"; \
		echo "[DETAIL] Files requiring formatting:"; \
		grep -E 'Would reformat ' "$(LOG_DIR)/ruff-format-check.log" | sed 's/^/  - /' || true; \
		echo "Hint: run 'ruff format src/ tests/' to auto-format."; \
		echo "[DETAIL] Full log: $(LOG_DIR)/ruff-format-check.log"; \
		exit 1; \
	fi
	@echo "[OK] lint-ruff passed"

.PHONY: lint-test
lint-test:
	@mkdir -p $(LOG_DIR)
	@echo "[lint-test] Installing dev dependencies..."
	@$(PIP) install -e ".[dev]" || { \
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
lint-audit:
	@mkdir -p $(LOG_DIR)
	@echo "[lint-audit] Installing pip-audit..."
	@$(PIP) install pip-audit || { \
		echo "[FAIL] lint-audit: failed to install pip-audit"; \
		exit 1; \
	}
	@echo "[lint-audit] Installing project dependencies..."
	@$(PIP) install -e ".[dev]" || { \
		echo "[FAIL] lint-audit: failed to install project dependencies"; \
		exit 1; \
	}
	@echo "[lint-audit] Running vulnerability scan..."
	@set -o pipefail; $(PIP_AUDIT) 2>&1 | tee "$(LOG_DIR)/pip-audit.log"; status=$${PIPESTATUS[0]}; if [[ $$status -ne 0 ]]; then \
		echo "[FAIL] lint-audit: pip-audit found vulnerabilities"; \
		echo "[DETAIL] This failure is dependency vulnerabilities, not source file linting."; \
		echo "[DETAIL] Vulnerable packages:"; \
		awk 'BEGIN{in_table=0} /^Name[[:space:]]+Version[[:space:]]+ID[[:space:]]+Fix Versions/{in_table=1; next} in_table && /^-/{next} in_table && /^$$/{in_table=0} in_table && NF>=4 {printf "  - %s %s (%s) -> fix: %s\n", $$1, $$2, $$3, $$4}' "$(LOG_DIR)/pip-audit.log" || true; \
		echo "[DETAIL] Full log: $(LOG_DIR)/pip-audit.log"; \
		exit 1; \
	fi
	@echo "[OK] lint-audit passed"

.PHONY: lint-workflow
lint-workflow:
	@echo "[lint-workflow] Running lint-ruff..."
	@$(MAKE) lint-ruff || { echo "[FAIL] lint-workflow stopped at lint-ruff"; exit 1; }
	@echo "[lint-workflow] Running lint-test..."
	@$(MAKE) lint-test || { echo "[FAIL] lint-workflow stopped at lint-test"; exit 1; }
	@echo "[lint-workflow] Running lint-audit..."
	@$(MAKE) lint-audit || { echo "[FAIL] lint-workflow stopped at lint-audit"; exit 1; }
	@echo "[OK] lint-workflow passed"

.PHONY: release-workflow
release-workflow:
	sudo apt-get update -qq
	sudo apt-get install -y --no-install-recommends \
		libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
		libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
		libxcb-xkb1 libxkbcommon-x11-0 libegl1 \
		libdbus-1-3 libglib2.0-0 \
		fuse libfuse2
	$(PIP) install --upgrade pip
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
	cp resources/icons/icon.png AppDir/py-tray-command-launcher.png
	cp resources/icons/icon.png AppDir/usr/share/pixmaps/py-tray-command-launcher.png
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
ci:
	@echo "[ci] Running ci-workflow..."
	@$(MAKE) ci-workflow || { echo "[FAIL] ci stopped at ci-workflow"; exit 1; }
	@echo "[ci] Running tests-workflow..."
	@$(MAKE) tests-workflow || { echo "[FAIL] ci stopped at tests-workflow"; exit 1; }
	@echo "[ci] Running lint-workflow..."
	@$(MAKE) lint-workflow || { echo "[FAIL] ci stopped at lint-workflow"; exit 1; }
	@echo "[OK] ci passed"

.PHONY: ci-full
ci-full:
	@echo "[ci-full] Running ci..."
	@$(MAKE) ci || { echo "[FAIL] ci-full stopped at ci"; exit 1; }
# 	@echo "[ci-full] Running release-workflow..."
# 	@$(MAKE) release-workflow || { echo "[FAIL] ci-full stopped at release-workflow"; exit 1; }
# 	@echo "[OK] ci-full passed"

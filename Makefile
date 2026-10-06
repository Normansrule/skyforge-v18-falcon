# SKYFORGE Falcon workbench - common tasks. `make` lists them.
SHELL := /bin/bash
PY    ?= $(if $(wildcard .venv/bin/python3),.venv/bin/python3,python3)
PORT  ?= 8080

.PHONY: help setup setup-desktop serve open check test budget v18 v19 web models shots desktop desktop-build publish bundle clean

help: ## list the targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

setup: ## Python venv + Node packages + vendored browser libraries (Ubuntu: scripts/setup_ubuntu.sh does this and more)
	./scripts/setup_ubuntu.sh --no-apt

setup-desktop: ## also install Rust and the Tauri system libraries for the desktop app
	./scripts/setup_ubuntu.sh --desktop

serve: ## web app at http://localhost:8080 (PORT=... to change)
	@echo "Open http://localhost:$(PORT) (Ctrl+C to stop)"
	$(PY) -m http.server $(PORT) --directory site

open: ## serve and open the browser (WSL opens the Windows browser)
	@( sleep 1; (command -v wslview >/dev/null && wslview http://localhost:$(PORT)) || (command -v explorer.exe >/dev/null && explorer.exe http://localhost:$(PORT)) || xdg-open http://localhost:$(PORT) ) >/dev/null 2>&1 &
	$(PY) -m http.server $(PORT) --directory site

check: ## repo consistency + web/Python parity + vortex-lattice self-test
	$(PY) tools/check_repo.py
	npm test
	$(PY) tools/aero_vlm.py --selftest

test: check

budget: ## regenerate docs/BOM.md and docs/BUDGET.md after editing the BOM or measurements
	$(PY) tools/budget.py
	$(PY) tools/export_web.py && $(PY) tools/export_web.py --sw-only

v18: ## full V18 analysis from the 3MF (extract, mass, aero, checks, harness, balance, interface parts)
	$(PY) tools/v18_extract.py
	$(PY) tools/mass_cg.py
	$(PY) tools/aero_vlm.py
	$(PY) tools/geom_checks.py
	$(PY) tools/harness.py
	$(PY) tools/balance_study.py
	$(PY) cad/interface/src/build.py
	$(PY) tools/budget.py

v19: ## V19 search, geometry, document and web data (about 10 minutes)
	$(PY) tools/v19/search.py
	$(PY) tools/v19/geometry.py
	$(MAKE) web
	$(PY) tools/v19/report.py
	$(MAKE) web

web: ## site data, compressed models and the offline cache list
	$(PY) tools/export_web.py
	npm run models
	$(PY) tools/export_web.py --sw-only

shots: ## re-render the doc images from the web app (needs Python Playwright + Chromium)
	@$(PY) -m http.server 8765 --directory site >/dev/null 2>&1 & echo $$! > .serve.pid; sleep 1; \
	$(PY) tools/web/screenshots.py --url http://localhost:8765/; status=$$?; kill $$(cat .serve.pid); rm -f .serve.pid; exit $$status

desktop: ## run the desktop app in development mode
	cd desktop && npm install && npx tauri dev

desktop-build: ## build desktop installers for this OS (desktop/src-tauri/target/release/bundle)
	cd desktop && npm install && npx tauri build

publish: ## create/push the GitHub repo, enable Pages; TAG=v0.6.0 also builds the desktop release
	./scripts/publish_github.sh $(if $(TAG),--tag $(TAG),)

bundle: ## one-file git bundle of the whole history (for moving the repo without GitHub)
	git bundle create ../skyforge-v18-falcon.bundle --all && ls -lh ../skyforge-v18-falcon.bundle

clean: ## remove caches and build outputs that are not committed
	rm -rf .cache site/models/raw desktop/src-tauri/target __pycache__ tools/__pycache__ tools/v19/__pycache__

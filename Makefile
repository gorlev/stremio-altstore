# Stremio Unofficial AltStore Source — Makefile
#
# Shortcut commands:
#   make help        — show this help message
#   make dry-run     — run the updater in dry-run mode (no writes)
#   make update      — perform a real update (also refreshes README tables)
#   make verify      — update with Info.plist verification (slower)
#   make readme      — regenerate the README "Available versions" tables
#   make hashes      — backfill sha256 integrity hashes (budgeted downloads)
#   make mirror      — mirror IPAs into GitHub Releases (budgeted, needs gh)
#   make canary      — CDN health check (newest IPAs still reachable?)
#   make prune       — report versions whose IPA is gone (add APPLY=1 to remove)
#   make audit       — full weekly audit: prune report + metadata verification
#   make notes       — capture real release notes from Stremio's own source
#                      (ARCHIVE=1 also mines Internet Archive captures)
#   make shots       — capture App Store screenshots from Stremio's source
#   make news        — rebuild the in-app news feed from captured changelogs
#   make legacy      — mirror newest build into legacy app-level fields
#   make trim        — report versions the retention policy would drop
#   make validate    — check the JSON sources are valid and safe to publish
#   make test        — run the test suite
#   make lint        — Python code quality checks
#   make format      — format Python code
#   make clean       — remove temporary files
#   make set-urls    — set sourceURL fields interactively

SHELL := /bin/bash
PYTHON ?= python3
SCRIPT := stremio-updater.py

# Colors (when terminal supports them)
BOLD := \033[1m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

.PHONY: help dry-run update verify readme hashes mirror canary prune audit notes shots news legacy trim validate test lint format clean set-urls ios tvos stats

help:  ## Show this help message
	@echo ""
	@echo "$(BOLD)Stremio Unofficial AltStore Source$(RESET) — Makefile targets"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make dry-run         — show new versions only, don't write"
	@echo "  make update          — find new versions and write to JSON"
	@echo "  make verify          — update with Info.plist verification"
	@echo "  make ios dry-run     — iOS only, dry run"
	@echo ""

dry-run:  ## Run the updater in dry-run mode (does not write files)
	@echo "$(YELLOW)→ Dry run — scan only$(RESET)"
	$(PYTHON) $(SCRIPT) --dry-run --verbose

update:  ## Real update — write new versions to JSON (refreshes README too)
	@echo "$(YELLOW)→ Real update$(RESET)"
	$(PYTHON) $(SCRIPT)
	@$(MAKE) --no-print-directory readme

verify:  ## Update with Info.plist verification (slower, ~100KB/IPA)
	@echo "$(YELLOW)→ Update with Info.plist verification$(RESET)"
	$(PYTHON) $(SCRIPT) --info-plist --verbose
	@$(MAKE) --no-print-directory readme

readme:  ## Regenerate the README "Available versions" tables from the JSON
	@echo "$(YELLOW)→ Regenerate README version tables$(RESET)"
	$(PYTHON) scripts/render_readme.py

hashes:  ## Backfill sha256 integrity hashes (set BUDGET=N to override per-run cap)
	@echo "$(YELLOW)→ Backfill sha256 hashes$(RESET)"
	$(PYTHON) scripts/add_hashes.py $(if $(BUDGET),--budget $(BUDGET),)

mirror:  ## Mirror IPAs into GitHub Releases (BUDGET=N, DRY=1, VERSION=2.1.3b28)
	@echo "$(YELLOW)→ Mirror IPAs to releases$(RESET)"
	$(PYTHON) scripts/mirror_release.py $(if $(BUDGET),--budget $(BUDGET),) $(if $(DRY),--dry-run,) $(if $(VERSION),--version $(VERSION),)

canary:  ## CDN health check — are the newest known IPAs still reachable?
	@echo "$(YELLOW)→ CDN health canary$(RESET)"
	$(PYTHON) scripts/check_cdn.py

prune:  ## Report versions whose IPA is gone (APPLY=1 removes the safe ones)
	@echo "$(YELLOW)→ Dead version check$(RESET)"
	@# '-' so make doesn't print "Error 1/2" over the script's own report;
	@# CI calls the script directly and does act on the exit code.
	-@$(PYTHON) scripts/prune_dead.py $(if $(APPLY),--apply,)

notes:  ## Capture real release notes from Stremio's source (DRY=1 to preview)
	@echo "$(YELLOW)→ Capture release notes$(RESET)"
	$(PYTHON) scripts/fetch_release_notes.py $(if $(DRY),--dry-run,) $(if $(ARCHIVE),--include-archive,)

shots:  ## Capture App Store screenshots from Stremio's source (DRY=1 to preview)
	@echo "$(YELLOW)→ Capture screenshots$(RESET)"
	$(PYTHON) scripts/fetch_screenshots.py $(if $(DRY),--dry-run,)

news:  ## Rebuild the in-app news feed from captured changelogs (DRY=1 to preview)
	@echo "$(YELLOW)→ Rebuild news feed$(RESET)"
	-@$(PYTHON) scripts/build_news.py $(if $(DRY),--dry-run,)

legacy:  ## Mirror the newest build into legacy app-level fields (DRY=1 to preview)
	@echo "$(YELLOW)→ Sync legacy fields$(RESET)"
	$(PYTHON) scripts/sync_legacy_fields.py $(if $(DRY),--dry-run,)

trim:  ## Report versions the retention policy would drop (APPLY=1 removes them)
	@echo "$(YELLOW)→ Retention policy$(RESET)"
	-@$(PYTHON) scripts/trim_versions.py $(if $(APPLY),--apply,) $(if $(KEEP),--keep $(KEEP),)

validate:  ## Check the JSON sources are valid and safe to publish (STRICT=1 fails on warnings)
	@echo "$(YELLOW)→ Validate sources$(RESET)"
	$(PYTHON) scripts/validate_source.py $(if $(STRICT),--strict,)

test:  ## Run the test suite
	@echo "$(YELLOW)→ Tests$(RESET)"
	$(PYTHON) -m unittest discover -s scripts -p 'test_*.py' -v

audit:  ## Weekly audit: dead-version report + Info.plist metadata verification
	@echo "$(YELLOW)→ Dead version check$(RESET)"
	-$(PYTHON) scripts/prune_dead.py
	@echo "$(YELLOW)→ Verify bundle IDs against the real IPAs$(RESET)"
	-$(PYTHON) scripts/verify_bundle_ids.py

ios:  ## Update only the iOS source (pass DRY/UPDATE/VERIFY via ARGS)
	@echo "$(YELLOW)→ iOS only$(RESET)"
	$(PYTHON) $(SCRIPT) --platform ios $(ARGS)

tvos:  ## Update only the tvOS source
	@echo "$(YELLOW)→ tvOS only$(RESET)"
	$(PYTHON) $(SCRIPT) --platform tvos $(ARGS)

set-urls:  ## Set sourceURL fields interactively
	@echo "$(YELLOW)→ Set sourceURL$(RESET)"
	@read -p "iOS source URL (e.g. https://USER.github.io/stremio-altstore/stremio-ios.json): " IOS_URL; \
	 read -p "tvOS source URL: " TVOS_URL; \
	 $(PYTHON) $(SCRIPT) --source-url-ios "$$IOS_URL" --source-url-tvos "$$TVOS_URL"

lint:  ## Python code quality checks (ruff + mypy)
	@echo "$(YELLOW)→ Lint checks$(RESET)"
	@command -v ruff >/dev/null && ruff check $(SCRIPT) scripts/ || echo "  (ruff not installed, skipping)"
	@command -v mypy >/dev/null && mypy $(SCRIPT) || echo "  (mypy not installed, skipping)"

format:  ## Format Python code (ruff format, black-compatible)
	@echo "$(YELLOW)→ Format$(RESET)"
	@command -v ruff >/dev/null && ruff format $(SCRIPT) scripts/ || echo "  (ruff not installed, skipping)"

stats:  ## Show version counts in the JSON sources
	@echo "$(BOLD)Statistics:$(RESET)"
	@for f in stremio-ios.json stremio-tvos.json; do \
	  if [ -f "$$f" ]; then \
	    echo "  $$f:"; \
	    $(PYTHON) -c "import json; d=json.load(open('$$f')); print(f'    source: {d[\"name\"]}'); [print(f'    - {a[\"name\"]} ({a[\"bundleIdentifier\"]}): {len(a[\"versions\"])} version(s)') for a in d['apps']]"; \
	  fi; \
	done

clean:  ## Remove temporary files
	@echo "$(YELLOW)→ Cleaning$(RESET)"
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@rm -f dry-run.log *.tmp *.bak
	@echo "$(GREEN)✓ Cleaned$(RESET)"

.DEFAULT_GOAL := help

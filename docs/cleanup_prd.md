# Simple DFS Cleanup PRD

## Background
Simple DFS began as a collection of ad-hoc scripts for scraping projections, generating FanDuel lineup pools, and selecting final entries. Over time the repository collected duplicated logic (`generate_fd_lineups.py`, `generate_nfl_lineups.py`, `fdnhl_picker.py`, `mme150_picker.py`), inconsistent configuration files (`inputs.py`, `fd_inputs.py`, inline constants), temporary analysis tools, downloaded data, and execution artifacts. The current structure hampers maintainability, testing, and reuse across sports.

This PRD proposes a deliberate cleanup that turns the codebase into a maintainable Python package with clearly separated CLIs, shared libraries, and documented workflows.

## Goals
- Establish a predictable project layout (`src/`, `scripts/`, `tests/`, `docs/`, `data/`).
- Reduce duplicated code by consolidating lineup generation and picker logic into reusable modules.
- Centralize configuration management and environment variables.
- Ensure deterministic, testable workflows with clear entry points and logging.
- Protect source control from generated files, large CSVs, and third-party code copies.
- Provide documentation and automation that make it easy to run, extend, and deploy tools.

## Current Issues
- **Repository layout:** Python modules, scripts, logs, notebooks, outputs, and vendor code all live at repo root. External dependency `pydfs-lineup-optimizer` is checked in, complicating upgrades.
- **Configuration sprawl:** Multiple `*_inputs.py` modules with overlapping constants; scripts rely on implicit defaults and global state rather than a consistent settings system.
- **Code duplication:** Lineup generator scripts copy/paste queue logic, logging setup, and optimizer configuration. Picker scripts (NFL vs NHL) duplicate data parsing, pool pruning, and scoring heuristics.
- **Outputs & artifacts:** Generated CSVs/logs under `autoNHL/`, `autoMME/`, `lineups/`, and root-level logs mix with committed code. `.gitignore` currently blocks all CSVs, which prevents checking in sample fixtures for testing.
- **Testing gaps:** Existing tests cover CSV sanitization but nothing around lineup selection logic or configuration. No CI workflow runs tests or linting.
- **Dependencies & environments:** Virtualenv is committed but there is no locked requirements file or Makefile/`tox`/`nox` automation. Some scripts assume `venv` activation manually.
- **Documentation:** Scattered markdown files do not cover end-to-end usage, configuration, or developer onboarding.

## Success Metrics
- Single command (`python -m simple_dfs.cli`) can regenerate lineup pools or run pickers with structured logging.
- ≥80% of shared lineup logic lives in `src/simple_dfs/` modules without duplication between sports.
- Repository root contains only source, config, docs, and tests. Outputs land in `outputs/` (gitignored) and data in `data/`.
- Automated test suite passes locally and via CI; at least smoke tests for lineup generation and picker scoring exist.
- README (or docs site) describes setup, configuration, and workflow.

## Proposed Architecture & Workstreams

### 1. Repository Layout & Packaging
- Create `src/simple_dfs/` package with submodules:
  - `data/` (projection + lineup loaders, ID utilities).
  - `optimizers/` (wrappers around `pydfs-lineup-optimizer`).
  - `selection/` (picker heuristics, scoring, constraints).
  - `configs/` (pydantic models, environment defaults).
- Move CLI entry points to `scripts/` (e.g. `scripts/generate_lineups.py`, `scripts/select_lineups.py`) and register console scripts in `pyproject.toml`.
- Remove vendored `pydfs-lineup-optimizer/` folder; depend on released package via `requirements.txt`/`pyproject`.
- Introduce `pyproject.toml` (or update `setup.cfg`) for packaging metadata, dependencies, and tool configuration (black/ruff/pytest).

### 2. Configuration System
- Replace `inputs.py` / `fd_inputs.py` with typed configuration objects (pydantic or dataclass) loaded from YAML/JSON/TOML per sport + slate.
- Support environment variable overrides for sensitive paths or API keys.
- Provide a `configs/` directory with sample templates: `configs/defaults.yaml`, `configs/fanduel/nhl.yaml`, etc.
- Update CLIs to accept `--config path/to/file.yaml` instead of module imports.

### 3. Shared Libraries & De-duplication
- Normalize lineup pool schemas (column names, roster slots) and create reusable parsing utilities.
- Extract scoring heuristics and selectors (e.g., pruning, uniqueness, stacking, logging) into common modules with sport-specific adapters.
- Consolidate queue-based lineup generation logic into a single orchestrator that accepts sport-specific constraints.
- Replace ad-hoc scripts (`mme150_picker.py`, `fdnhl_picker.py`) with CLI commands that choose sport-specific configuration but share code.

### 4. Data, Artifacts, and Logging
- Adopt directory structure:
  - `data/raw/` for downloaded projections.
  - `data/processed/` for normalized inputs.
  - `outputs/lineups/`, `outputs/reports/` for generated artifacts.
  - `logs/` for rotating log files.
- Update `.gitignore` to allow small fixture CSVs under `tests/fixtures/` while ignoring `data/` and `outputs/`.
- Standardize logging via Python `logging` config (JSON or dictConfig) to write to both console and file with consistent format.

### 5. Testing & Quality
- Add unit tests around:
  - Projection loader + ID resolution.
  - Picker scoring (projection normalization, correlation bonuses, cap enforcement).
  - End-to-end smoke test that generates a small subset of lineups using canned inputs.
- Introduce linting/formatting (ruff/black) and type checking (mypy or pyright) as pre-commit or CI steps.
- Provide CI workflow (GitHub Actions) running `pytest`, lints, and packaging sanity check.

### 6. Developer Experience & Automation
- Document workflows in `README` and `docs/` (setup, running scripts, adding new sports).
- Provide `Makefile` or `justfile` tasks (`make setup`, `make test`, `make generate-nhl`).
- Capture repeatable data ingestion steps (e.g., `apis/nflreadpy_probe.py`) into proper modules or CLI commands with caching.

## Phased Roadmap

### Phase 0 – Quick Wins (1–2 days)
1. Create `docs/` (this PRD) and `outputs/`/`data/` folders with `.gitkeep`.
2. Refresh `.gitignore` to allow test fixtures and ignore `outputs/`/`data/`.
3. Remove committed logs/cache directories; ensure `venv/` is ignored (already) and add note about using `python -m venv`.
4. Add `requirements.txt` pinning runtime dependencies (including `nflreadpy`, `pydfs-lineup-optimizer`).

### Phase 1 – Packaging & Structure (1 week)
1. Introduce `pyproject.toml` and move shared code into `src/simple_dfs/`.
2. Extract common utilities from generators/pickers into modules.
3. Update scripts to import from new package; maintain backward-compatible CLI wrappers where necessary.
4. Add basic unit tests and configure `pytest`.

### Phase 2 – Configuration & CLI Consolidation (1–2 weeks)
1. Implement configuration loader (YAML/TOML) and migrate existing `inputs.py` values.
2. Build unified CLI (`python -m simple_dfs.cli generate --sport nhl …`).
3. Harmonize logging and progress reporting across commands.
4. Introduce consistent output directories and metadata (timestamped run manifests).

### Phase 3 – Quality & Documentation (ongoing)
1. Expand test coverage (selector heuristics, data ingestion).
2. Add CI pipeline with linting + tests.
3. Document onboarding, architecture, and runbooks in `docs/`.
4. Evaluate opportunities for modular plugins (different optimizers, projection sources).

## Risks & Mitigations
- **Refactor regression risk:** Consolidating scripts could introduce bugs. Mitigate by creating fixture-based regression tests before moving logic.
- **Large CSV handling:** Restructuring data directories may require storage guidelines. Mitigate with documentation and `.gitignore` templates.
- **Dependency drift:** Removing bundled `pydfs-lineup-optimizer` means depending on external releases. Mitigate with pinned versions and optional fork instructions.
- **Time investment:** Packaging work may pause feature development. Mitigate by phasing (Phase 0 quick wins, incremental merges).

## Open Questions
- Should lineup generation support DraftKings or other sites in the same repo? (Impacts abstraction boundaries.)
- Do we need multi-user configuration (per developer) or will a shared default config suffice?
- Are there existing pipelines or notebooks outside this repo that depend on current script names/paths?
- What is the minimum Python version we must support?
- Should we archive historical outputs in cloud storage instead of local folders?

## Appendix – Current Script Inventory (non-exhaustive)
- `generate_fd_lineups.py`, `generate_nfl_lineups.py`: FanDuel pool generation with near-identical queue logic.
- `fdnhl_picker.py`, `mme150_picker.py`: Lineup selectors with divergent heuristics.
- `csv_processor.py`, `player_usage_analysis.py`, `analyze_data.py`, `debug_real_data.py`: One-off data utilities.
- `apis/nflreadpy_probe.py`: Data ingestion test harness (candidate for new data ingestion module).
- Logs and outputs: `autoNHL/`, `autoMME/`, `lineups/`, `projection-captures/`, etc.

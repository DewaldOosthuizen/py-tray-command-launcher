# py-tray-command-launcher — Copilot Instructions

Python/PyQt6 system tray app for launching shell commands from a hierarchical context menu.
Always reference these instructions first; fall back to search or bash only when something
does not match the info here.

---

## A. Orientation

- Project README: [README.md](README.md)
- Documentation index: [docs/index.md](docs/index.md)
- Architecture: [docs/architecture.md](docs/architecture.md)
- AI Agent Guide: [docs/ai-agent-guide.md](docs/ai-agent-guide.md)
- Contributing: [docs/contributing.md](docs/contributing.md)
- Architecture Design Decisions (ADD-001..016): [docs/add/](docs/add/) — [README](docs/add/README.md)

---

## B. Code Exploration

- graphify : `graphify query "<q>"` | `graphify path "<A>" "<B>"` | `graphify explain "<c>"` | `graphify update .`
- codegraph : `codegraph context "<task>" -p .` | `codegraph query "<symbol>" -p .` | `codegraph affected <files> -p .` | `codegraph sync .`
- understand : launch the dashboard at `~/.understand-anything-plugin/packages/dashboard`; skill `understand-chat`.

Rules:
- Query the graph tools before opening source files; read only the files that matter.
- Prefer targeted reads (line ranges, symbol lookups) over whole-file or whole-directory reads.
- Refresh the graphs after modifying code (only for tools whose artifacts are present).
- Do not paste large outputs, logs or files into responses; summarise and reference path:line.

---

## C. Engineering Standards

- Clean architecture: separation of concerns, dependency direction toward abstractions, single
  responsibility; reuse existing modules before adding new ones.
- Match the conventions of neighbouring code; do not refactor unrelated code unless it
  contributes to the clean architecture.
- Every public class, function and method gets a docstring or doc comment covering purpose,
  parameters, return value and raised errors.
- Every behaviour change ships with tests, including negative-path tests for validation and
  authorization; every bug fix ships with a regression test.
- No hacky workarounds, no silent error swallowing, no secrets in code or logs.

---

## D. Architecture Documentation

- ADRs: short, immutable once accepted, one decision each, capturing context, decision and
  consequences; add a timestamp (yyyy-mm-dd HH:MM) when created; a new ADR supersedes the old
  one — never edit an accepted ADR.
- ADDs: comprehensive living design documents (typically 5–15 pages); write one before building
  a non-trivial feature; follow the numbering and template in [docs/add/](docs/add/).
- Update the relevant ADD/ADR in the same change as the code; documentation drift is a defect.

---

## E. Verification and Review

- Before declaring work done, run the CI gate and confirm it passes: `make ci`.
- Review changes by running the CI gate as well; do not approve on reading the diff alone —
  report real command output, never assumed results.
- During review also check: tests cover new behaviour and failure paths, public APIs are
  documented, no duplicated logic, no dead code, docs and ADR/ADD updated, no secrets.
- Fix root causes, not symptoms; check sibling code paths for the same flaw.

---

## F. Repository-Specific Rules

- Tests may need PyQt6 stubs: the system may have PyQt5, not PyQt6. Stub PyQt6 at module level
  BEFORE importing any src modules.
- Patch `IconResolver.resource_roots()` on the class, not the instance.
- Runtime dependencies live in `pyproject.toml` (single source of truth); `requirements.txt` is
  a convenience dev-install shim — never add standalone version pins there.
- Lint: `flake8 src/ --select=E9,F63,F7,F82`, `black src/`, `py_compile` all files; `mypy`
  optional but encouraged.
- Set generous timeouts for installs and tests (60s+ and 30s) and never cancel long-running commands.

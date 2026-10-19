# py-tray-command-launcher

A Python/PyQt6 system tray application for launching custom commands and scripts from a
hierarchical menu. Supports file encryption, command scheduling, backup/restore, favorites,
fuzzy command search, a command palette, a quick-launch bar, and packaging for Linux and Windows.

This file instructs AI agents (Hermes, GitHub Copilot, Codex, etc.) on how
to orient themselves in this repository efficiently.

---

## Documentation

All project documentation lives in [docs/](docs/index.md). Key documents:

- [AI Agent Guide](docs/ai-agent-guide.md) — Code exploration, design decisions, and agent-specific guidance
- [Architecture](docs/architecture.md) — Module structure and data flow
- [Contributing](docs/contributing.md) — Development setup and PR process

<!-- graph-tools-start -->

## Code Exploration

### codegraph

`.codegraph/` is present. Use it FIRST for any symbol lookup, call tracing, or targeted context
gathering before opening source files.

```bash
codegraph context "<task description>" -p .   # focused file+symbol context
codegraph query "<ClassName or function>" -p . # where is X defined / used
codegraph affected <changed-files> -p .        # which tests are affected
codegraph sync .                               # after any code change
```

Decision order for code tasks:
  1. codegraph context     — which symbols matter?
  2. graphify query        — which files are involved?
  3. understand-anything   — where in the architecture does this live?
  4. Read raw source       — only the 1-2 files that actually matter.

### understand-anything

`.understand-anything/knowledge-graph.json` is present.
Use it for layered architecture questions (layers, communities, entry points).

```bash
# Launch the interactive dashboard
cd ~/.understand-anything-plugin/packages/dashboard
GRAPH_DIR=$(pwd) npx vite --host 127.0.0.1
```

For prose questions load the skill:

```
skill: understand-chat
```

### graphify

graphify-out/ not yet generated for this repo.

<!-- graph-tools-end -->

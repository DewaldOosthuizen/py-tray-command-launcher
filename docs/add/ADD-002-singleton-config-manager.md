# ADD-002 — Singleton ConfigManager — module-level instance

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | config, singleton, architecture |

---

## Context

The application has a single source of configuration truth: the JSON files
managed by `ConfigManager`.  Many components throughout `core/`, `modules/`,
and `ui/` need access to the config — commands, settings, history, favorites.
Without a clear ownership model, multiple instances could read stale caches or
race to write the same files.

---

## Decision

`ConfigManager` is instantiated exactly once at module level at the bottom of
`config_manager.py`:

```python
config_manager = ConfigManager()
```

Consumers import the singleton directly:

```python
from core.config_manager import config_manager
```

There is no `__new__`-based singleton guard.  The module system guarantees
that the module is evaluated once per Python process, so the assignment at
module level is sufficient.  Tests that need isolation can instantiate
`ConfigManager()` directly, passing an injected `config_dir` or patching
`_get_base_dir()`.

---

## Alternatives considered

**`__new__` singleton** — was used in an earlier revision.  Removed because it
made unit testing difficult: tests could not get a fresh instance without
monkey-patching the class-level `_instance` attribute.  The module-level
approach is simpler and equally safe.

**Passing a `ConfigManager` instance through every constructor** — rejected:
would require threading the config through `TrayApp`, all modules, and all UI
dialogs.  The `AppServices` dataclass (ADD-003) already handles dependency
injection for callable interfaces; adding the full `ConfigManager` object there
would expand coupling.

**Context variable / global registry** — rejected: unnecessary complexity when
a module-level name is both idiomatic Python and sufficient.

---

## Consequences

+ Simple, idiomatic — any module that needs config does a single import.
+ In-memory caches (`_settings_cache`, `_commands_cache`) are shared across all
  callers so repeated reads within the same tick cost nothing.
+ Tests can create isolated instances by direct instantiation with a temp dir.
- Callers that import `config_manager` before `configure_logging()` is called
  in `main.py` may get log records with the root logger's default format; this
  is an acceptable ordering constraint.
- Any mutable shared state in `ConfigManager` (e.g. override paths set via
  `--config`) affects the entire process; there is no per-call override scope.

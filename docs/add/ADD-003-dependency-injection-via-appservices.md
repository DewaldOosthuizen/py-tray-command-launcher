# ADD-003 — Dependency injection via AppServices dataclass

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | architecture, dependency-injection, coupling |

---

## Context

`TrayApp` is the central orchestrator of the application.  It owns the
`QSystemTrayIcon`, the tray menu, all feature modules, and all UI dialogs.
Before the refactor, feature modules (`Favorites`, `CommandHistory`,
`ScheduleCreator`, etc.) held a direct reference to the `TrayApp` instance,
giving them access to every private method and attribute on a 500+ line class.
This made individual modules hard to test in isolation and created high
coupling between unrelated features.

---

## Decision

A lightweight `AppServices` dataclass is defined in `core/services.py` and
passed to every feature module's constructor instead of `TrayApp`:

```python
@dataclass
class AppServices:
    config_manager: "ConfigManager"
    execute: Callable[[str, str, bool, bool, Optional[str]], None]
    reload_commands: Callable[..., None]
    show_output: Callable[[str, str], None]
    get_all_commands: Callable[[], list]
    save_commands: Callable[[dict], None]
    reload_history_commands: Callable[[], None]
    reload_favorites_commands: Callable[[], None]
    resolve_icon_path: Callable[[str], str]
```

`TrayApp.__init__` builds the dataclass and passes it to each module and UI
dialog.  Modules call only the callables they need — they never touch
`TrayApp` directly.

The `ConfigManager` is included in `AppServices` to give modules access to
config reads/writes without going through `TrayApp`.

---

## Alternatives considered

**Pass `TrayApp` directly** — the original approach.  Created a circular
dependency graph, made unit testing require a full Qt application, and
encouraged feature creep on `TrayApp`.

**Protocol / abstract base class** — would express the interface more formally
but adds boilerplate without meaningful benefit given Python's duck typing; a
dataclass of typed callables is sufficient and readable.

**Individual constructor arguments per dependency** — would work but is
verbose when a module needs five callables; `AppServices` bundles them
conveniently without hiding dependencies (each callable is named and typed).

---

## Consequences

+ Feature modules can be instantiated in tests by passing a `MagicMock()` as
  `AppServices`; no `QApplication` required.
+ The set of things a module can do is explicitly declared in its constructor
  signature rather than inferred from what it calls on a god object.
+ Adding a new cross-cutting operation requires adding one field to
  `AppServices` and wiring it in `TrayApp`, which is a contained change.
- `AppServices` still includes `config_manager` as a full object, not a set
  of typed callables; modules that use it are coupled to the `ConfigManager`
  API surface.
- If a module needs an operation not in `AppServices`, a developer may be
  tempted to bypass the interface; code review must guard against this.

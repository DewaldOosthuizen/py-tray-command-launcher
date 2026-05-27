# ADD-006 — MenuBuilder extraction from TrayApp

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | architecture, refactoring, menu, separation-of-concerns |

---

## Context

The original `TrayApp.__init__` was a monolithic method that constructed the
tray icon, wired all modules, built the entire context menu, registered hotkeys,
and set up the quick-launch bar inline.  The menu-building logic alone was
several hundred lines of recursive tree traversal.  This made the class hard to
read, hard to test, and hard to modify without unintended side effects.

---

## Decision

Menu construction was extracted into a dedicated `MenuBuilder` class in
`core/menu_builder.py`.  `TrayApp` holds an instance and delegates via
`self._menu_builder.build(menu, command_menu)`.

`MenuBuilder` responsibilities:

- Walk the command tree from `config_manager.get_commands()` and build the
  nested `QMenu` hierarchy.
- Attach icons to group submenus and individual actions using
  `services.resolve_icon_path`.
- Wire the `triggered` signal of each action to the appropriate executor
  callable (direct execute, show-output, or silent background execution).
- Attach the "Pin to Quick Launch" context menu to each command action via
  `_attach_pin_context_menu()`.

`TrayApp.__init__` was simultaneously decomposed into seven focused private
methods:

| Method | Responsibility |
|--------|---------------|
| `_setup_paths` | Resolve base dir, init `IconResolver`, apply TTL setting |
| `_setup_theme` | Initialise `ThemeManager`, apply theme from settings |
| `_setup_tray_icon` | Create `QSystemTrayIcon`, set icon, set tooltip |
| `_setup_modules` | Instantiate all feature modules with `AppServices` |
| `_setup_ui` | Instantiate all UI dialogs |
| `_build_menu` | Call `MenuBuilder.build()`, attach static menu items |
| `_setup_hotkeys` | Register global hotkeys via `CommandPalette` |

---

## Alternatives considered

**Leave everything in TrayApp** — the original state.  Rejected: the class was
already approaching 600 lines with significant cognitive load.

**Extract a separate `MenuFactory` that returns a built `QMenu`** — rejected:
the menu has live signal connections to `TrayApp` callables; a pure factory
would still need the app context passed in, giving the same coupling with more
indirection.

**Move menu logic into `ConfigManager`** — rejected: config management and UI
construction are separate concerns; mixing them would make `ConfigManager`
untestable without a Qt application.

---

## Consequences

+ `TrayApp.__init__` is now readable as a high-level sequence of setup steps.
+ `MenuBuilder` can be unit-tested with a mocked `TrayApp` stub without
  instantiating the full application.
+ Adding a new command rendering variant (e.g. a different action type) is a
  localised change to `MenuBuilder`.
- `MenuBuilder` still holds a reference to `TrayApp` rather than a narrow
  interface, so it can in principle call any `TrayApp` method; this is
  intentional (it needs `execute`, `show_command_output`, `_pin_to_quick_launch`)
  but should not be expanded further.
- The recursive menu walk in `MenuBuilder.build()` is deeply coupled to the
  two-level `commands.json` structure; a deeper hierarchy would require
  reworking the traversal.

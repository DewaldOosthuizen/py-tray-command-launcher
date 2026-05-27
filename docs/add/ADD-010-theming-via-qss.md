# ADD-010 — Theming via QSS stylesheets

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | ui, theming, qss, catppuccin |

---

## Context

The application needed a consistent visual style across all dialogs and
widgets.  Qt's default platform style renders acceptably on some desktop
environments but looks inconsistent across X11, Wayland, and Windows, and
provides no dark-mode support.

---

## Decision

Theming is handled by `ThemeManager` (`core/theme_manager.py`) using Qt Style
Sheets (QSS) — Qt's CSS-like styling system — applied globally via
`QApplication.setStyleSheet(qss_content)`.

Two hand-authored QSS themes are bundled under `resources/themes/`:

| Theme | File | Palette |
|-------|------|---------|
| `dark` | `dark.qss` | Catppuccin Mocha |
| `light` | `light.qss` | Catppuccin Latte |

A third option, `system`, applies no custom stylesheet and lets the platform
native theme render normally.

The active theme name is persisted in `settings.json → theme` and applied:

1. At startup via `TrayApp._setup_theme()`.
2. Immediately on change from the `SettingsDialog` — no restart required.
3. The `SettingsDialog` shows a live preview when the user changes the
   selection.

`ThemeManager.apply_theme(theme_name)` resolves the QSS file path using the
same `_get_base_dir()` chain described in ADD-001 (source, PyInstaller, AppImage),
reads the file, and calls `QApplication.instance().setStyleSheet(content)`.

If the QSS file is missing, `ThemeManager` falls back to `system` and logs a
warning rather than crashing.

---

## Alternatives considered

**Per-widget `setStyleSheet` calls** — fragmented; impossible to change
globally, and every new dialog would need its own styling code.

**Qt palette manipulation (`QPalette`)** — can apply colour schemes but does
not support the fine-grained widget-level rules (border radius, padding,
separator styling) that give the app its consistent look.

**Third-party Qt theming library (e.g. `qdarkstyle`)** — an extra dependency
with a fixed look; using bundled QSS gives full control and allows the palette
to match the Catppuccin brand that the wider user community recognises.

---

## Consequences

+ All widgets — including third-party `QDialog` subclasses — inherit the
  theme automatically.
+ Switching theme takes effect immediately without restarting the application.
+ Catppuccin Mocha/Latte themes provide good contrast ratios and are
  accessible to users with common forms of colour vision deficiency.
- QSS is not CSS — some selectors behave unexpectedly (e.g. pseudo-state
  specificity, inherited vs non-inherited properties).  Theme maintenance
  requires knowledge of Qt-specific QSS quirks.
- `QApplication.setStyleSheet` affects every widget globally; a widget that
  sets its own `styleSheet` property may partially override the global theme
  in non-obvious ways.
- The `system` option relies on the platform providing a coherent native theme;
  on some minimal desktop environments the result may look unstyled.

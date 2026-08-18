# ADD-015 — App discovery via .desktop file scanning

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | app-launcher, desktop-files, discovery |

---

## Context

The Command Palette (ADD-011) was extended with a second **Apps** tab that
turns the tray launcher into a lightweight application launcher — similar to
Rofi or GNOME Activities.  To populate this list the application needs to
discover installed applications on the host system.

---

## Decision

`AppDiscovery` (`modules/app_discovery.py`) scans XDG `.desktop` files at
startup in a background thread and caches the results.

### Scan locations

The scanner searches the standard XDG application directories in priority order:

```
$XDG_DATA_HOME/applications          (~/.local/share/applications)
$XDG_DATA_DIRS/applications          (/usr/local/share/applications,
                                       /usr/share/applications, ...)
```

System entries in `/usr/share/applications` are always included; user
overrides in `~/.local/share/applications` take precedence via deduplication
on the desktop file basename.

### Parsing

`.desktop` files are INI-format; `configparser` reads them.  Only entries with
`Type=Application` and without `NoDisplay=true` are included.  The `Exec`
field is cleaned of `%f`, `%u`, `%F`, `%U` and other field codes before
execution.  The `Icon` field is resolved through Qt's icon theme with
`QIcon.fromTheme(name)` and falls back to a generic application icon if the
theme does not provide it.

### Caching and search

Results are stored as a list of `AppEntry` dataclass instances:

```python
@dataclass
class AppEntry:
    name: str
    exec_cmd: str
    icon: QIcon
    comment: str = ""
    categories: list[str] = field(default_factory=list)
```

The module-level singleton `app_discovery` exposes:

- `get_all()` — the full list (blocks briefly until the background scan
  completes on first call).
- `search(query)` — returns a scored, filtered subset using
  `rapidfuzz.fuzz.WRatio` over `name` and `comment` fields.

### Thread safety — `_icon_path_index` locking (issue #87)

`_build_icon_index` runs on a daemon background thread and populates
`self._icon_path_index` (icon name → resolved absolute path) as a
supplementary fallback for icons that Qt's theme resolver misses.
`_find_pixmap`, invoked from the Qt main thread, reads that same dict.

`_icon_path_index` is only ever mutated by building a full local `dict` and
then performing a single atomic swap (`self._icon_path_index = index`) —
never incremental in-place mutation. An explicit `threading.Lock`
(`self._icon_index_lock`) guards both the swap in `_build_icon_index` and the
read in `_find_pixmap`, formalizing this invariant so a future edit cannot
silently reintroduce a `RuntimeError: dictionary changed size during
iteration` race by mutating the dict incrementally instead of swapping it.

`_pixmap_cache` (icon+size → resolved `QPixmap`) is intentionally left
unlocked: it is read and written exclusively from the Qt main thread. This
assumption is documented at its declaration and access sites and must be
revisited if cross-thread access to `_pixmap_cache` is ever introduced.

---

## Alternatives considered

**`gio` / `xdg-open` subprocess** — delegates parsing to the system but is
Linux-only and does not provide programmatic access to the icon or metadata
needed for the list UI.

**`pyxdg` library** — would handle XDG path resolution and `.desktop` parsing.
Rejected: adds a dependency for functionality that `configparser` + a small path
helper can cover; also not actively maintained.

**No app launcher** — the feature is additive.  Users who only want a command
launcher use the Commands tab exclusively.

---

## Consequences

+ The Apps tab populates from the real system application list without any
  configuration by the user.
+ Background scanning keeps the palette responsive at startup; the scan
  completes in well under a second on typical systems.
+ `QIcon.fromTheme` integrates with the active icon theme so app icons
  match the user's desktop environment.
- `.desktop` scanning is Linux/freedesktop-specific.  On Windows or macOS,
  `get_all()` returns an empty list and the Apps tab is effectively disabled;
  native equivalents (Windows registry, macOS `.app` bundles) are not
  implemented.
- `Exec` field code stripping is a best-effort implementation; unusual field
  codes or multi-part `TryExec` entries may not be handled correctly.
- Icons loaded via `QIcon.fromTheme` at scan time may not update if the user
  changes their icon theme while the application is running.

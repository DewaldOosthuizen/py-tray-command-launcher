# ADD-012 — Favorites command path encoding

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | favorites, data-model, encoding |

---

## Context

The favorites feature allows users to pin frequently used commands for quick
access from a dedicated "Favourites" submenu in the tray.  Each favourite must
identify a specific command within the two-level `commands.json` hierarchy
(group → label).

The original implementation encoded command paths as a single string using
` → ` (space-arrow-space) as a separator between group breadcrumbs and the
label, e.g.:

```
"System Tools → Terminal"
```

This separator was also used as the **display string** shown to users in the
Favourites submenu.  Using the same string as both display separator and storage
key created a latent bug: if a user named a command group or label containing
` → `, the parsing would produce the wrong split.

---

## Decision

A private helper `_build_command_path(group, label)` was introduced in
`modules/favorites.py`:

```python
def _build_command_path(group: str, label: str) -> str:
    parts = [p.strip() for p in group.split(" → ") if p.strip()]
    parts.append(label.strip())
    return ".".join(parts)
```

This encodes the path as a dot-separated string:

- The group string is split on ` → ` to flatten any display-breadcrumb nesting.
- Each part is stripped of surrounding whitespace.
- Empty parts (from leading/trailing separators) are filtered out.
- Parts are joined with `.` — a character unlikely to appear in command names.

Example:

| Group display string | Label | Stored path |
|---------------------|-------|-------------|
| `System` | `Terminal` | `System.Terminal` |
| `Dev → Python` | `Run Tests` | `Dev.Python.Run Tests` |
| ` → Network` | `Ping` | `Network.Ping` |

`favorites.json` stores an array of path strings:

```json
{
  "favorites": ["System.Terminal", "Dev.Python.Run Tests"]
}
```

When building the Favourites submenu, the stored paths are resolved back to
command objects by splitting on `.` and walking the `commands.json` tree.

---

## Alternatives considered

**Keep ` → ` separator** — simple but fragile for names containing ` → `.

**Store `{group, label}` objects** — storing `{"group": "System", "label": "Terminal"}`
would be unambiguous and match the `commands.json` structure directly.  This is
a better long-term approach and may replace the dot path in a future revision;
the current dot path was chosen for minimal migration impact on existing
`favorites.json` files.

**URL-encode the separator** — would survive most special characters but makes
the stored path unreadable for users who inspect `favorites.json` directly.

---

## Consequences

+ Commands whose group or label contains ` → ` are now handled correctly.
+ Dot-separated paths are readable and compact in `favorites.json`.
+ `_build_command_path` is a pure function and is fully covered by the
  test suite (`tests/test_favorites_path.py`).
- A dot (`.`) in a group name or label would still cause an incorrect split on
  path resolution; this is an accepted limitation documented for users.
- Existing `favorites.json` files written by earlier versions used ` → ` paths;
  they will fail to resolve until migrated.  A migration utility is not yet
  implemented.

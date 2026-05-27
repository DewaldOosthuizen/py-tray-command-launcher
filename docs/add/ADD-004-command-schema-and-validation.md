# ADD-004 — commands.json schema and soft validation

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | config, validation, schema, commands |

---

## Context

`commands.json` is the user-editable catalogue that drives the entire tray
menu.  Structural corruption — a mistyped key, a string where a dict is
expected — causes runtime exceptions deep inside `MenuBuilder` rather than a
clear error at load time.  The format also needed documentation so that users
and tools could author it reliably.

---

## Decision

### Format

`commands.json` uses a two-level nested structure:

```json
{
  "Group Name": {
    "Command Label": {
      "command": "shell command string",
      "icon": "optional icon path or HTTPS URL",
      "confirm": false,
      "showOutput": false,
      "runInBackground": false
    }
  }
}
```

Top-level keys are group names.  Second-level keys are command labels.  Values
are command objects.  The `command` field is the only required field on a
command object.

Optional prompt substitution: `{promptInput}` anywhere in the `command` string
causes the executor to show an input dialog before running; the user's text
replaces the placeholder.

### JSON Schema

A formal JSON Schema draft-07 document lives at `config/commands.schema.json`.
It documents all fields, their types, and their defaults.

### Two-layer validation

**Layer 1 — structural (`_validate_commands`)**: runs on every `get_commands()`
call.  Checks that the root is a dict, all groups are dicts, and all command
objects that have a `command` key contain a string.  Raises `ConfigurationError`
with a human-readable message on violation.

**Layer 2 — schema (`_validate_commands_schema`)**: runs once after Layer 1 if
`jsonschema` is installed.  Validates the full structure against
`config/commands.schema.json`.  On failure it **logs a warning** and continues
rather than raising, so that existing configs with minor schema deviations do
not break the application.  If `jsonschema` is not installed the step is
silently skipped.

---

## Alternatives considered

**Raise hard on schema failure** — would break configs that were valid under an
older schema.  The soft warning approach is preferred until the schema is
considered stable.

**Pydantic models** — would give typed, validated models throughout the
codebase.  Rejected because it adds a significant dependency for what is
essentially a user-edited JSON file; the two-layer approach is sufficient.

**No validation** — the original approach.  Structural errors surfaced as
confusing `KeyError` or `AttributeError` inside menu-building code; rejected.

---

## Consequences

+ Users get a clear `ConfigurationError` message when they mistype the
  structure rather than a stack trace from inside `MenuBuilder`.
+ `config/commands.schema.json` serves as living documentation — editors that
  support `$schema` provide auto-completion.
+ Missing `jsonschema` degrades gracefully rather than crashing.
- The two-layer split means some errors caught by the schema (e.g. extra
  unexpected fields) only appear as warnings, not errors.
- Schema validation is skipped entirely when `jsonschema` is absent; a future
  improvement would be to bundle a minimal validator.

---

## commands.json field reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `command` | string | **required** | Shell command to execute |
| `icon` | string | `""` | Icon: absolute path, HTTPS URL, or `data:image/...` base64 |
| `confirm` | boolean | `false` | Show confirmation dialog before running |
| `showOutput` | boolean | `false` | Open output window to display stdout/stderr |
| `runInBackground` | boolean | `false` | Fire-and-forget without a tracked QProcess |
| `group_icon` | string | `""` | Icon for the group submenu (set on the group level) |

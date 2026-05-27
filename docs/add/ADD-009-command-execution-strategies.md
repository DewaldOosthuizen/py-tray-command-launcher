# ADD-009 — Command execution strategies — subprocess vs QProcess

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | execution, subprocess, QProcess, output |

---

## Context

Commands in `commands.json` are arbitrary shell strings authored by the user.
The application needs to run them in three modes:

1. **Fire-and-forget** — run the command; do not capture or display output.
2. **Output window** — run the command and stream stdout/stderr into a live
   `RichOutputWindow` as the process produces it.
3. **Silent background** — run without an output window but also without
   blocking the UI event loop.

Each mode has different requirements around process lifecycle management,
output capture, and UI integration.

---

## Decision

`CommandExecutor` (in `modules/command_executor.py`) exposes three methods:

### `execute_command(command)` — fire-and-forget

Uses `subprocess.Popen(command, shell=True)` and returns immediately.  The
child process is not tracked after launch.  `shell=True` is intentional and
acknowledged in the docstring: these are user-authored commands in a personal
launcher; the security model is that the user controls both the command file
and the input.

### `execute_command_process(app, command)` — tracked QProcess

Creates `QProcess(app)`, sets program to `bash` and arguments to `["-c", command]`,
calls `.start()`, and returns the running `QProcess` handle to the caller.

The caller (`TrayApp.show_command_output`) connects `readyReadStandardOutput`,
`readyReadStandardError`, `finished`, and `errorOccurred` signals **before**
calling this method, waiting for the handle.  The QProcess parent is the
`QApplication` instance, ensuring it is garbage-collected with the application.

A `weakref` to the `RichOutputWindow` is used in the signal callbacks to
prevent the window from being kept alive by the signal closure if the user
closes it before the process finishes.

### `execute_command_process_silently(app, command)` — silent QProcess

Same as above but the caller does not connect stdout/stderr signals.
Used for the `runInBackground` flag — the command runs to completion without
any output UI.

### `{promptInput}` substitution

`TrayApp.execute()` intercepts the command before passing it to any executor.
If `{promptInput}` appears in the command string, a `QInputDialog` is shown,
and the user's text is substituted in.  The substitution happens on the Python
string before the shell sees it; the user's input reaches the shell as part of
the command string (i.e. it is not shell-escaped).  This is by design for a
personal launcher where the user controls the full command template.

---

## Alternatives considered

**Always use QProcess** — would remove the `subprocess` dependency but `QProcess`
requires a running `QApplication`, complicating use in any future headless or
testing context.

**asyncio subprocess** — would integrate well with an async UI framework but
PyQt6's event loop and Python's asyncio event loop require bridging (e.g.
`qasync`); adds complexity without a clear benefit for this use case.

**Shell=False with parsed arguments** — safer but breaks commands that use
pipes, redirects, environment variable expansion, or other shell features
that users commonly put in a launcher.

---

## Consequences

+ Output window commands stream output live as the process produces it;
  the user sees partial output for long-running commands.
+ Fire-and-forget commands do not hold a reference in the Qt object tree,
  keeping memory usage bounded.
+ The `{promptInput}` pattern covers the common case of parametric commands
  (e.g. `ssh {promptInput}`) without requiring a dedicated dialog per command.
- `shell=True` with unescaped `{promptInput}` substitution means a user who
  types `;rm -rf ~` would execute it.  The threat model accepts this because
  the user is both the author and the operator.
- Silent QProcess children accumulate as Qt objects until the parent
  `QApplication` is destroyed; this is acceptable for typical launcher usage
  (tens of commands per session) but could be a concern for very high-frequency
  automation use.

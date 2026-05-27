# ADD-014 — Command scheduling via cron / Task Scheduler

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | scheduling, cron, automation |

---

## Context

Users want to run specific commands from their catalogue on a schedule — for
example, running a backup script every night at 02:00, or triggering a sync
every hour.  The application already knows how to execute commands; it needed a
way to register them with the OS scheduling system.

---

## Decision

Scheduling is delegated entirely to the OS scheduler — cron on Linux/macOS and
Task Scheduler on Windows.  The application does not implement its own
scheduling loop.

### Linux/macOS — crontab

`ScheduleCreator` generates a crontab entry string from the user's selections
(command, time, frequency, days) and writes it by reading the current crontab
via `crontab -l`, appending the new entry, and writing back via
`crontab -` (piped to stdin of a `crontab` subprocess).

The entry format is standard cron:

```
# py-tray-launcher: <label>
<minute> <hour> * * <days>  /bin/bash -c "<command>"
```

`ScheduleViewer` reads the current crontab, filters entries tagged with
`# py-tray-launcher:`, and displays them in a list dialog.  Each entry can be
deleted from the viewer.

### Windows — Task Scheduler (schtasks)

On Windows, `ScheduleCreator` invokes `schtasks /Create` with appropriate
flags.  `ScheduleViewer` uses `schtasks /Query` to list and `schtasks /Delete`
to remove.

---

## Alternatives considered

**Built-in scheduler loop (APScheduler, asyncio)** — would allow scheduling
without any external dependency.  Rejected: the OS scheduler is more reliable
(survives application restarts), runs commands even when the tray app is not
running, and integrates with the user's existing crontab.

**systemd timer units** — would be the modern Linux approach.  Rejected: adds
significant complexity (unit file generation, `systemctl --user` integration);
cron is universally available and familiar.

---

## Consequences

+ Scheduled commands run even if the tray application is not currently running.
+ No in-process scheduling loop means no risk of drift, missed ticks, or
  resource usage from a running timer.
+ Users can inspect, edit, and remove entries directly in their crontab if
  they prefer.
- The application must have permission to write the user's crontab; in
  restricted environments (some corporate Linux installs) this may be blocked.
- Crontab parsing is fragile — the implementation relies on `# py-tray-launcher:`
  comment tags to identify its own entries; manually edited crontab formatting
  may confuse the parser.
- Windows Task Scheduler support is feature-incomplete compared to the
  Linux cron path; some scheduling frequencies available on Linux are not
  yet exposed on Windows.

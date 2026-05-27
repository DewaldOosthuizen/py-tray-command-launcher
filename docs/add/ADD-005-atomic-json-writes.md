# ADD-005 — Atomic JSON writes via temp-file rename

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | storage, reliability, data-integrity |

---

## Context

All persistent state — commands, settings, history, favorites — lives in JSON
files on disk.  A naive `open(path, "w") + json.dump()` leaves the file in a
half-written, corrupt state if the process is killed or a write error occurs
mid-operation.  For a tray application that runs continuously in the background
and may be killed without warning, partial writes would silently corrupt the
user's configuration.

---

## Decision

All JSON writes go through `ConfigManager._write_json_atomic(file_path, data)`:

1. Write the serialised JSON to a temporary file in the **same directory** as
   the target (critical: cross-device renames fail on some filesystems).
2. Flush and `fsync` the temp file to ensure the OS flushes kernel buffers to
   storage.
3. Rename the temp file to the target path (`os.replace` — atomic on POSIX,
   transactional on Windows NTFS).

```python
def _write_json_atomic(self, file_path: Path, data: Any) -> None:
    tmp = file_path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, file_path)
```

The target file is either complete and valid or entirely the previous version;
a partial write never reaches the live path.

---

## Alternatives considered

**Direct write** — simple but leaves partial files on crash; unacceptable for
user-facing persistent state.

**Write + verify (read-back check)** — adds latency and disk I/O for every
save; the rename approach is already sufficient to guarantee atomicity.

**SQLite** — would give ACID guarantees out of the box.  Rejected: JSON files
are human-readable, version-control-friendly, and directly editable; SQLite
would remove these properties without a clear benefit at this scale.

---

## Consequences

+ Corrupt configuration files from unexpected termination are eliminated.
+ The `.tmp` file is always in the same directory as the target, so it is
  visible to the user if an error occurs before the rename.
- On NFS or other remote filesystems, `os.fsync` may not guarantee durability
  depending on mount options; this is documented but not mitigated.
- A very large `history.json` causes a write of the full list on every
  `add_to_history()` call; history is capped at `history_limit` (default 50)
  to bound this cost.

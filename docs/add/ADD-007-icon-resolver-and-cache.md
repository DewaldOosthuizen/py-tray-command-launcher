# ADD-007 — IconResolver with TTL-aware local cache

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | icons, cache, networking, security |

---

## Context

Commands in `commands.json` can specify icons by:

- An absolute filesystem path (e.g. `/usr/share/icons/hicolor/48x48/apps/firefox.png`)
- A relative path resolved against the application's resource roots
- An HTTPS URL (e.g. a favicon from a web service)
- A `data:image/png;base64,...` inline URI

Downloading icons on every menu build would be slow and would fail offline.
Storing them in the user's config directory would pollute it with network
artefacts.  Some mechanism for caching downloaded icons was needed.

Additionally, the application ships with default icons under
`resources/icons/` and must find them across source runs, PyInstaller bundles,
and AppImage distributions (see ADD-001).

---

## Decision

`IconResolver` (in `core/icon_resolver.py`) handles all icon path resolution
through a single interface:

```python
resolver.resolve_icon_path(icon_path, fallback="")  # -> str
```

### Download cache

Downloaded icons are stored in a system temporary directory:
`/tmp/py-tray-launcher-icons/` (Linux/macOS) or equivalent on Windows.

The cache key is the MD5 hash of the URL (hex digest), giving a fixed-length
filename regardless of URL length.  The file extension is derived from the URL
suffix (`.png`, `.jpg`, etc.), defaulting to `.png`.

### TTL

The cache TTL is configurable via `settings.json → icon_cache_ttl_days`
(default: 7 days).  On each download request:

1. If the cached file does not exist → download.
2. If the cached file's mtime is older than the TTL → re-download.
3. Otherwise → return the cached path immediately.

A TTL of 0 disables expiry checks — the cache never re-downloads the same URL.

The TTL is applied at startup via `TrayApp._setup_paths`:

```python
self.icon_resolver.set_cache_ttl(
    settings.get("icon_cache_ttl_days", 7)
)
```

### Security

HTTP URLs are explicitly rejected with a warning log; only HTTPS is accepted.
This prevents passive network observation of the user's icon requests when
running on an untrusted network.

Base64 `data:image/...` URIs are decoded and written to the cache directory
with a size cap of ~5 MB to prevent memory exhaustion from malformed URIs.

### Resource root search order

For relative paths, the resolver searches in order:

1. `sys._MEIPASS/resources/icons/<name>` — PyInstaller bundle
2. `<exe_dir>/resources/icons/<name>` — AppImage / system install
3. `<base_dir>/resources/icons/<name>` — source run

---

## Alternatives considered

**Store cache in the user config dir** — would survive system `tmp` cleans but
would intermingle user-editable data with network artefacts.  The temp
directory is appropriate because losing the cache is harmless.

**No caching — re-download on every start** — unacceptably slow; would also
require a network connection to render the menu.

**Use the system icon theme** — would provide system-consistent icons but
wouldn't work for HTTPS URL icons or custom icons specified per-command.

---

## Consequences

+ The menu builds instantly on subsequent launches even when commands have HTTPS
  icon URLs.
+ Expired icons are refreshed automatically without user intervention.
+ HTTP URLs rejected at the resolver level; no plaintext icon fetches.
- `md5` is used as a cache key — not cryptographically critical (it's just a
  filename deduplicator) but worth noting.
- The temp directory may be cleaned by the OS during long uptime sessions;
  the application handles missing cache files by re-downloading transparently.
- Icons served from URLs without file extensions default to `.png` which may be
  wrong for SVG or WEBP icons; this is a known limitation.

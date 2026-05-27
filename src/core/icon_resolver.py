# SPDX-License-Identifier: GPL-3.0-or-later
"""
Icon resolution for py-tray-command-launcher.

Handles all icon path resolution logic across packaging modes
(source run, PyInstaller bundle, AppImage / system install):

  - Tray icon discovery against MEIPASS / exe_dir / base_dir roots
  - HTTPS URL download with SSL verification, size cap, Content-Type allow-list
  - Base64 data URI decoding with size cap and caching
  - Relative path resolution against resource roots
  - HTTP URL rejection (plain HTTP is not permitted)
"""

import base64
import hashlib
import logging
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


class IconResolver:
    """Resolves icon paths across packaging modes.

    Args:
        base_dir: The project base directory (used as the lowest-priority
                  resource root when resolving relative icon paths).
    """

    # Maximum bytes allowed for a downloaded icon (1 MB).
    _MAX_ICON_DOWNLOAD_BYTES = 1 * 1024 * 1024
    # Maximum decoded size for a base64 data URI icon (2 MB).
    _MAX_B64_DECODED_BYTES = 2 * 1024 * 1024
    # Default icon cache TTL in seconds (7 days).  Override via settings.
    _DEFAULT_CACHE_TTL_SECONDS = 7 * 24 * 3600
    # Content-Type values accepted for downloaded icons.
    _ALLOWED_ICON_CONTENT_TYPES = frozenset({
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/bmp",
        "image/x-icon",
        "image/vnd.microsoft.icon",
        "image/svg+xml",
    })

    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir
        self._cache_ttl_seconds: int = self._DEFAULT_CACHE_TTL_SECONDS

    def set_cache_ttl(self, days: int) -> None:
        """Set the icon cache TTL (in days).  0 or negative disables caching."""
        self._cache_ttl_seconds = max(0, int(days)) * 24 * 3600

    # ------------------------------------------------------------------ #
    # Resource roots                                                       #
    # ------------------------------------------------------------------ #

    def resource_roots(self) -> list[str]:
        """Return candidate root directories for icon lookups, most-preferred first.

        Covers all packaging modes: PyInstaller bundle, AppImage / system
        install (executable-relative), and direct source run (base_dir).
        """
        roots: list[str] = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(meipass)
        try:
            exe_dir = os.path.dirname(sys.executable)
            if exe_dir:
                roots.append(exe_dir)
        except Exception as exc:
            logger.debug("Could not resolve exe_dir for icon roots: %s", exc)
        if self.base_dir:
            roots.append(self.base_dir)
        return roots

    # ------------------------------------------------------------------ #
    # Tray icon                                                            #
    # ------------------------------------------------------------------ #

    def resolve_tray_icon(self) -> str:
        """Resolve the tray icon path robustly across source, PyInstaller, and AppImage.

        Returns:
            The first existing candidate path, or an empty string when none is found.
        """
        candidates: list[str] = []
        for root in self.resource_roots():
            candidates.append(os.path.join(root, "resources", "icons", "icon.png"))
            candidates.append(os.path.join(root, "resources", "icon.png"))

        # AppImage-specific placements (relative to exe dir).
        try:
            exe_dir = os.path.dirname(sys.executable)
            if exe_dir:
                candidates.append(
                    os.path.normpath(
                        os.path.join(exe_dir, "..", "..", "py-tray-command-launcher.png")
                    )
                )
                candidates.append(
                    os.path.normpath(
                        os.path.join(
                            exe_dir, "..", "share", "pixmaps",
                            "py-tray-command-launcher.png",
                        )
                    )
                )
        except Exception as exc:
            logger.debug("Could not resolve AppImage icon candidates: %s", exc)

        for path in candidates:
            if path and os.path.exists(path):
                return path
        return ""

    # ------------------------------------------------------------------ #
    # Remote icon download                                                 #
    # ------------------------------------------------------------------ #

    def download_icon(self, url: str) -> str | None:
        """Download an icon from an HTTPS URL and cache it locally.

        Security measures applied:
        - HTTPS-only: plain HTTP URLs are rejected up-front.
        - SSL context with certificate verification.
        - Response body capped at ``_MAX_ICON_DOWNLOAD_BYTES`` to prevent memory
          exhaustion.
        - Content-Type validated against an allow-list before writing to disk.

        Args:
            url: The HTTPS URL of the icon. HTTP URLs are rejected.

        Returns:
            Local path to the downloaded (or cached) icon, or ``None`` on failure.
        """
        import ssl

        if not url.lower().startswith("https://"):
            logger.warning("Rejecting icon download: non-HTTPS URL %s", url)
            return None

        try:
            cache_dir = os.path.join(tempfile.gettempdir(), "py-tray-launcher-icons")
            os.makedirs(cache_dir, exist_ok=True)

            url_hash = hashlib.md5(url.encode()).hexdigest()

            # Determine file extension from URL path (before query string).
            url_lower = url.lower().split("?")[0]
            extension = "png"
            for ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg"):
                if url_lower.endswith(ext):
                    extension = ext.lstrip(".")
                    break

            cached_file = os.path.join(cache_dir, f"{url_hash}.{extension}")

            if os.path.exists(cached_file):
                if self._cache_ttl_seconds > 0:
                    import time
                    age = time.time() - os.path.getmtime(cached_file)
                    if age < self._cache_ttl_seconds:
                        return cached_file
                    logger.debug("Icon cache expired for %s (age=%.0fs), re-downloading", url, age)
                else:
                    return cached_file

            ctx = ssl.create_default_context()
            with urllib.request.urlopen(url, timeout=10, context=ctx) as response:
                content_type = (
                    response.headers.get("Content-Type", "").split(";")[0].strip().lower()
                )
                if content_type and content_type not in self._ALLOWED_ICON_CONTENT_TYPES:
                    logger.warning(
                        "Rejecting icon download: unexpected Content-Type %r from %s",
                        content_type,
                        url,
                    )
                    return None

                data = response.read(self._MAX_ICON_DOWNLOAD_BYTES + 1)
                if len(data) > self._MAX_ICON_DOWNLOAD_BYTES:
                    logger.warning(
                        "Rejecting icon download: response exceeds %d bytes from %s",
                        self._MAX_ICON_DOWNLOAD_BYTES,
                        url,
                    )
                    return None

            with open(cached_file, "wb") as f:
                f.write(data)

            return cached_file

        except Exception as exc:
            logger.warning("Failed to download icon from %s: %s", url, exc)
            return None

    # ------------------------------------------------------------------ #
    # General icon path resolution                                         #
    # ------------------------------------------------------------------ #

    def resolve_icon_path(self, icon_path: str, fallback: str) -> str:
        """Resolve an icon path to an absolute local path.

        Handles the following input forms:
        - Empty string → ``fallback``
        - ``data:image/...;base64,...`` → decoded, cached, returns cache path
        - ``https://...`` → downloaded, cached, returns cache path
        - ``http://...`` → rejected, returns ``fallback``
        - Absolute path → returned unchanged when the file exists
        - Relative path → resolved against each resource root

        Args:
            icon_path: The raw icon value from configuration.
            fallback:  Path to return when resolution fails.

        Returns:
            An absolute path to an icon file.
        """
        if not icon_path:
            return fallback

        # ---- Base64 data URI ----
        if icon_path.startswith("data:image"):
            return self._resolve_base64_icon(icon_path, fallback)

        # ---- HTTPS URL ----
        if icon_path.startswith("https://"):
            downloaded = self.download_icon(icon_path)
            if downloaded and os.path.exists(downloaded):
                return downloaded
            return fallback

        # ---- Plain HTTP (rejected) ----
        if icon_path.startswith("http://"):
            logger.warning("Rejecting icon URL with non-HTTPS scheme: %s", icon_path)
            return fallback

        # ---- Filesystem path (absolute or relative) ----
        expanded = os.path.expanduser(icon_path)
        if os.path.isabs(expanded) and os.path.exists(expanded):
            return expanded

        for root in self.resource_roots():
            for candidate in (
                os.path.join(root, "resources", "icons", expanded),
                os.path.join(root, "resources", expanded),
            ):
                if os.path.exists(candidate):
                    return candidate

        return fallback

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _resolve_base64_icon(self, icon_path: str, fallback: str) -> str:
        """Decode a base64 data URI and return a path to the cached file."""
        try:
            match = re.match(
                r"data:image/(?P<ext>\w+);base64,(?P<data>.+)", icon_path
            )
            if not match:
                return fallback

            ext = match.group("ext")
            b64_data = match.group("data")

            estimated_decoded = len(b64_data) * 3 // 4
            if estimated_decoded > self._MAX_B64_DECODED_BYTES:
                logger.warning(
                    "Rejecting base64 icon: estimated decoded size %d bytes exceeds limit",
                    estimated_decoded,
                )
                return fallback

            cache_dir = os.path.join(tempfile.gettempdir(), "py-tray-launcher-icons")
            os.makedirs(cache_dir, exist_ok=True)
            url_hash = hashlib.md5(icon_path.encode()).hexdigest()
            cached_file = os.path.join(cache_dir, f"{url_hash}.{ext}")

            if not os.path.exists(cached_file):
                with open(cached_file, "wb") as f:
                    f.write(base64.b64decode(b64_data))

            return cached_file

        except Exception as exc:
            logger.warning("Failed to decode base64 icon: %s", exc)
            return fallback

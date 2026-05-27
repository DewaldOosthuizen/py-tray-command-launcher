# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for IconResolver.

Covers:
  - HTTPS URL accepted, HTTP URL rejected
  - data:image base64 path handled
  - Absolute path returned as-is when file exists
  - Relative path resolved against resource_roots
  - Cache TTL: expired entry triggers re-download; fresh entry skips download
  - resolve_tray_icon returns str or None
"""

import base64
import hashlib
import os
import sys
import tempfile
import time
import types
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.icon_resolver import IconResolver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolver(base_dir=None):
    if base_dir is None:
        base_dir = tempfile.mkdtemp()
    return IconResolver(base_dir)


def _cache_path_for(url: str) -> Path:
    """Mirror the cache path logic used by IconResolver.download_icon."""
    cache_dir = Path(tempfile.gettempdir()) / "py-tray-launcher-icons"
    url_hash = hashlib.md5(url.encode()).hexdigest()
    url_lower = url.lower().split("?")[0]
    ext = "png"
    for candidate in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg"):
        if url_lower.endswith(candidate):
            ext = candidate.lstrip(".")
            break
    return cache_dir / f"{url_hash}.{ext}"


# ---------------------------------------------------------------------------
# HTTP vs HTTPS gating
# ---------------------------------------------------------------------------

class TestUrlGating:
    def test_http_url_rejected(self):
        r = _resolver()
        result = r.download_icon("http://example.com/icon.png")
        assert result is None

    def test_https_url_accepted_calls_urlopen(self, tmp_path):
        r = IconResolver(str(tmp_path))
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        mock_response = MagicMock()
        mock_response.headers.get.return_value = "image/png"
        mock_response.read.return_value = fake_png
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.icon_resolver.urllib.request.urlopen",
                   return_value=mock_response):
            result = r.download_icon("https://example.com/icon.png")

        assert result is not None
        assert Path(result).exists()


# ---------------------------------------------------------------------------
# Base64 / data URI
# ---------------------------------------------------------------------------

class TestBase64Icon:
    def test_valid_base64_png_handled(self, tmp_path):
        r = IconResolver(str(tmp_path))
        raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        b64 = base64.b64encode(raw).decode()
        data_uri = f"data:image/png;base64,{b64}"

        # resolve_icon_path should return *something* (a path string) and not crash
        result = r.resolve_icon_path(data_uri, fallback=str(tmp_path / "fallback.png"))
        assert result is not None
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Absolute / relative path resolution
# ---------------------------------------------------------------------------

class TestPathResolution:
    def test_absolute_existing_path_returned_as_is(self, tmp_path):
        icon = tmp_path / "icon.png"
        icon.write_bytes(b"fake")
        r = _resolver(str(tmp_path))
        result = r.resolve_icon_path(str(icon), fallback="fallback.png")
        assert result == str(icon)

    def test_nonexistent_absolute_falls_back(self, tmp_path):
        fallback = tmp_path / "fallback.png"
        fallback.write_bytes(b"fb")
        r = _resolver(str(tmp_path))
        result = r.resolve_icon_path(
            str(tmp_path / "no_such.png"), fallback=str(fallback)
        )
        assert result == str(fallback)

    def test_relative_path_resolved_against_resource_roots(self, tmp_path):
        icons_dir = tmp_path / "resources" / "icons"
        icons_dir.mkdir(parents=True)
        icon = icons_dir / "myicon.png"
        icon.write_bytes(b"fake")

        r = IconResolver(str(tmp_path))
        # resource_roots must return tmp_path; the resolver then appends
        # "resources/icons/<name>" itself.
        with patch.object(IconResolver, "resource_roots", return_value=[str(tmp_path)]):
            result = r.resolve_icon_path("myicon.png", fallback="fallback.png")

        assert result == str(icon)


# ---------------------------------------------------------------------------
# Cache TTL
# ---------------------------------------------------------------------------

class TestCacheTTL:
    def test_expired_cache_triggers_redownload(self, tmp_path):
        r = IconResolver(str(tmp_path))
        # TTL = 1 day; we'll fake the mtime to be 2 days ago
        r.set_cache_ttl(1)

        url = "https://example.com/ttl_expired.png"
        cached = _cache_path_for(url)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"stale")
        # Age = 2 days old → should expire
        old_time = time.time() - 2 * 86400
        os.utime(str(cached), (old_time, old_time))

        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_response = MagicMock()
        mock_response.headers.get.return_value = "image/png"
        mock_response.read.return_value = fake_png
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.icon_resolver.urllib.request.urlopen",
                   return_value=mock_response) as mock_open:
            r.download_icon(url)

        mock_open.assert_called_once()

    def test_fresh_cache_skips_download(self, tmp_path):
        r = IconResolver(str(tmp_path))
        r.set_cache_ttl(7)

        url = "https://example.com/ttl_fresh.png"
        cached = _cache_path_for(url)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"fresh content")
        # mtime = now (fresh — well within 7-day TTL)
        os.utime(str(cached), None)

        with patch("core.icon_resolver.urllib.request.urlopen") as mock_open:
            result = r.download_icon(url)

        mock_open.assert_not_called()
        assert result == str(cached)


# ---------------------------------------------------------------------------
# resolve_tray_icon
# ---------------------------------------------------------------------------

class TestResolveTrayIcon:
    def test_returns_str_or_none(self, tmp_path):
        r = IconResolver(str(tmp_path))
        result = r.resolve_tray_icon()
        assert result is None or isinstance(result, str)

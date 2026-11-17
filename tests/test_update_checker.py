# SPDX-License-Identifier: GPL-3.0-or-later
"""Mocked HTTP tests for release lookup, selection, and verified downloads."""

import hashlib
import io
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from core.update_checker import (
    CancellationToken,
    check_for_update,
    download_release_asset,
    parse_calver,
    select_release_asset,
)


def _release_payload(**overrides):
    payload = {
        "tag_name": "2026.10.22",
        "name": "Release 2026.10.22",
        "html_url": "https://github.com/DewaldOosthuizen/py-tray-command-launcher/releases/tag/2026.10.22",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": "py-tray-command-launcher-2026.10.22-x86_64.AppImage",
                "size": 7,
                "browser_download_url": "https://github.com/releases/download/asset",
            },
            {
                "name": "SHA256SUMS",
                "size": 85,
                "browser_download_url": "https://github.com/releases/download/checksums",
            },
        ],
    }
    payload.update(overrides)
    return payload


class _Response(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def _http_response(monkeypatch, response):
    calls = []

    def open_request(request, timeout):
        calls.append((request, timeout))
        return response

    monkeypatch.setattr("core.update_checker.urlopen", open_request)
    return calls


def test_lookup_returns_only_new_stable_calver_and_sets_user_agent(monkeypatch):
    calls = _http_response(monkeypatch, _Response(json.dumps(_release_payload()).encode()))
    release = check_for_update("2026.10.21")

    assert release.version == "2026.10.22"
    assert release.html_url.endswith("/2026.10.22")
    assert calls[0][0].get_header("User-agent")
    assert calls[0][1] > 0


@pytest.mark.parametrize(
    "payload,local_version",
    [
        (_release_payload(tag_name="2026.10.21"), "2026.10.21"),
        (_release_payload(tag_name="2026.10.20"), "2026.10.21"),
        (_release_payload(draft=True), "2026.10.21"),
        (_release_payload(prerelease=True), "2026.10.21"),
        (_release_payload(tag_name="v2026.10.22"), "2026.10.21"),
    ],
)
def test_lookup_ignores_non_newer_unstable_or_invalid_releases(monkeypatch, payload, local_version):
    _http_response(monkeypatch, _Response(json.dumps(payload).encode()))
    assert check_for_update(local_version) is None


def test_lookup_does_not_compare_development_builds(monkeypatch):
    monkeypatch.fail("network lookup must not run for a non-CalVer build")
    assert check_for_update("1.0.0") is None


@pytest.mark.parametrize(
    "failure",
    [URLError("offline"), TimeoutError("timeout"), ValueError("bad JSON")],
)
def test_lookup_silently_returns_none_for_network_and_payload_failures(monkeypatch, failure):
    monkeypatch.setattr("core.update_checker.urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(failure))
    assert check_for_update("2026.10.21") is None


def test_lookup_handles_http_rate_limit(monkeypatch):
    error = HTTPError("https://api.github.com/releases/latest", 403, "rate limited", {}, None)
    monkeypatch.setattr("core.update_checker.urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(error))
    assert check_for_update("2026.10.21") is None


def test_lookup_handles_malformed_api_fields(monkeypatch):
    _http_response(monkeypatch, _Response(b'{"tag_name": 42}'))
    assert check_for_update("2026.10.21") is None


def test_asset_selection_requires_linux_x86_64_appimage():
    release = check_for_update  # keep selector independent of network models
    assets = _release_payload()["assets"]
    assert select_release_asset(assets, "linux", "x86_64").name.endswith("x86_64.AppImage")
    assert select_release_asset(assets, "windows", "AMD64") is None
    assert select_release_asset(assets, "linux", "aarch64") is None
    assert release is not None


def test_download_verifies_checksum_and_size_and_reports_progress(monkeypatch, tmp_path):
    data = b"payload"
    filename = "py-tray-command-launcher-2026.10.22-x86_64.AppImage"
    digest = hashlib.sha256(data).hexdigest()
    manifest = f"{digest}  {filename}\n".encode()
    responses = iter([_Response(manifest), _Response(data)])
    monkeypatch.setattr("core.update_checker.urlopen", lambda *_args, **_kwargs: next(responses))
    progress = []
    result = download_release_asset(
        {"name": filename, "size": len(data), "browser_download_url": "https://github.com/asset"},
        {"name": "SHA256SUMS", "browser_download_url": "https://github.com/checksums"},
        tmp_path,
        progress.append,
    )

    assert result.path.read_bytes() == data
    assert result.path.stat().st_mode & 0o111 == 0
    assert progress[-1] == len(data)


def test_download_rejects_bad_checksum_and_removes_file(monkeypatch, tmp_path):
    filename = "release.AppImage"
    manifest = f"{'0' * 64}  {filename}\n".encode()
    responses = iter([_Response(manifest), _Response(b"payload")])
    monkeypatch.setattr("core.update_checker.urlopen", lambda *_args, **_kwargs: next(responses))

    with pytest.raises(ValueError):
        download_release_asset(
            {"name": filename, "size": 7, "browser_download_url": "https://github.com/asset"},
            {"name": "SHA256SUMS", "browser_download_url": "https://github.com/checksums"},
            tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_size_mismatch_and_removes_partial(monkeypatch, tmp_path):
    responses = iter([_Response(b""), _Response(b"short")])
    monkeypatch.setattr("core.update_checker.urlopen", lambda *_args, **_kwargs: next(responses))
    with pytest.raises(ValueError):
        download_release_asset(
            {"name": "release.AppImage", "size": 99, "browser_download_url": "https://github.com/asset"},
            {"name": "SHA256SUMS", "browser_download_url": "https://github.com/checksums"},
            tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_unsafe_urls_before_request(monkeypatch, tmp_path):
    monkeypatch.fail("unsafe URLs must be rejected before opening a request")
    with pytest.raises(ValueError):
        download_release_asset(
            {"name": "release.AppImage", "size": 1, "browser_download_url": "http://evil.example/asset"},
            {"name": "SHA256SUMS", "browser_download_url": "https://github.com/checksums"},
            tmp_path,
        )


def test_cancellation_closes_active_response():
    token = CancellationToken()
    response = _Response(b"data")
    token.register_response(response)
    token.cancel()
    assert response.closed
    assert token.cancelled

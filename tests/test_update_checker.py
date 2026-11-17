# SPDX-License-Identifier: GPL-3.0-or-later
"""Mocked HTTP tests for release lookup, selection, and verified downloads."""

import hashlib
import io
import json
from urllib.error import HTTPError, URLError

import pytest

from core.update_checker import (
    CancellationToken,
    _open_response,
    check_for_update,
    download_release_asset,
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

    def open_request(url, allowed_hosts, cancellation=None):
        calls.append((url, allowed_hosts, cancellation))
        return response

    monkeypatch.setattr("core.update_checker._open_https_response", open_request)
    return calls


def test_lookup_returns_only_new_stable_calver_and_sets_user_agent(monkeypatch):
    calls = _http_response(monkeypatch, _Response(json.dumps(_release_payload()).encode()))
    release = check_for_update("2026.10.21")

    assert release is not None
    assert release.version == "2026.10.22"
    assert release.html_url.endswith("/2026.10.22")
    assert calls[0][0].endswith("/releases/latest")
    assert calls[0][1] == frozenset({"api.github.com"})


def test_https_transport_uses_user_agent_and_finite_timeout(monkeypatch):
    connections = []

    class FakeConnection:
        def __init__(self, host, port=None, timeout=None):
            self.host = host
            self.timeout = timeout
            self.request_args = None
            connections.append(self)

        def request(self, method, target, headers):
            self.request_args = (method, target, headers)

        def getresponse(self):
            return _Response(b"ok")

        def close(self):
            pass

    monkeypatch.setattr("core.update_checker.http.client.HTTPSConnection", FakeConnection)
    with _open_response("https://github.com/releases/file") as response:
        assert response.read() == b"ok"

    assert connections[0].timeout > 0
    assert connections[0].request_args[0:2] == ("GET", "/releases/file")
    assert connections[0].request_args[2]["User-Agent"]


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
    monkeypatch.setattr(
        "core.update_checker.fetch_latest_release",
        lambda: pytest.fail("network lookup must not run for a non-CalVer build"),
    )
    assert check_for_update("1.0.0") is None


@pytest.mark.parametrize(
    "failure",
    [URLError("offline"), TimeoutError("timeout"), ValueError("bad JSON")],
)
def test_lookup_silently_returns_none_for_network_and_payload_failures(monkeypatch, failure):
    monkeypatch.setattr(
        "core.update_checker._open_https_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
    )
    assert check_for_update("2026.10.21") is None


def test_lookup_handles_http_rate_limit(monkeypatch):
    error = HTTPError("https://api.github.com/releases/latest", 403, "rate limited", {}, None)
    monkeypatch.setattr(
        "core.update_checker._open_https_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )
    assert check_for_update("2026.10.21") is None


def test_lookup_handles_malformed_api_fields(monkeypatch):
    _http_response(monkeypatch, _Response(b'{"tag_name": 42}'))
    assert check_for_update("2026.10.21") is None


def test_asset_selection_requires_linux_x86_64_appimage():
    assets = _release_payload()["assets"]
    assert select_release_asset(assets, "linux", "x86_64").name.endswith("x86_64.AppImage")
    assert select_release_asset(assets, "windows", "AMD64") is None
    assert select_release_asset(assets, "linux", "aarch64") is None


def test_download_verifies_checksum_and_size_and_reports_progress(monkeypatch, tmp_path):
    data = b"payload"
    filename = "py-tray-command-launcher-2026.10.22-x86_64.AppImage"
    digest = hashlib.sha256(data).hexdigest()
    manifest = f"{digest}  {filename}\n".encode()
    responses = iter([_Response(manifest), _Response(data)])

    def open_response(_url, _hosts, cancellation=None):
        response = next(responses)
        if cancellation is not None:
            cancellation.register_response(response)
        return response

    monkeypatch.setattr("core.update_checker._open_https_response", open_response)
    progress = []
    result = download_release_asset(
        {"name": filename, "size": len(data), "browser_download_url": "https://github.com/asset"},
        {"name": "SHA256SUMS", "size": 0, "browser_download_url": "https://github.com/checksums"},
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

    def open_response(_url, _hosts, cancellation=None):
        response = next(responses)
        if cancellation is not None:
            cancellation.register_response(response)
        return response

    monkeypatch.setattr("core.update_checker._open_https_response", open_response)

    with pytest.raises(ValueError):
        download_release_asset(
            {"name": filename, "size": 7, "browser_download_url": "https://github.com/asset"},
            {
                "name": "SHA256SUMS",
                "size": 0,
                "browser_download_url": "https://github.com/checksums",
            },
            tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_size_mismatch_and_removes_partial(monkeypatch, tmp_path):
    responses = iter([_Response(b""), _Response(b"short")])

    def open_response(_url, _hosts, cancellation=None):
        response = next(responses)
        if cancellation is not None:
            cancellation.register_response(response)
        return response

    monkeypatch.setattr("core.update_checker._open_https_response", open_response)
    with pytest.raises(ValueError):
        download_release_asset(
            {
                "name": "release.AppImage",
                "size": 99,
                "browser_download_url": "https://github.com/asset",
            },
            {
                "name": "SHA256SUMS",
                "size": 0,
                "browser_download_url": "https://github.com/checksums",
            },
            tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_unsafe_urls_before_request(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "core.update_checker._open_https_response",
        lambda *_args: pytest.fail("unsafe URLs must be rejected before opening a request"),
    )
    with pytest.raises(ValueError):
        download_release_asset(
            {
                "name": "release.AppImage",
                "size": 1,
                "browser_download_url": "http://evil.example/asset",
            },
            {
                "name": "SHA256SUMS",
                "size": 0,
                "browser_download_url": "https://github.com/checksums",
            },
            tmp_path,
        )


def test_download_rejects_unsafe_redirect_target(monkeypatch):
    class FakeConnection:
        def __init__(self, host, port=None, timeout=None):
            pass

        def request(self, *_args, **_kwargs):
            pass

        def getresponse(self):
            return type(
                "Redirect",
                (),
                {
                    "status": 302,
                    "getheader": lambda _self, _name: "https://evil.example/asset",
                    "close": lambda _self: None,
                },
            )()

        def close(self):
            pass

    monkeypatch.setattr(
        "core.update_checker.http.client.HTTPSConnection",
        FakeConnection,
    )

    with pytest.raises(ValueError, match="approved GitHub host"):
        _open_response("https://github.com/asset")


def test_interrupted_download_removes_partial_asset(monkeypatch, tmp_path):
    data = b"payload"
    filename = "release.AppImage"
    manifest = f"{hashlib.sha256(data).hexdigest()}  {filename}\n".encode()
    asset_response = _Response(data)
    responses = iter([_Response(manifest), asset_response])
    token = CancellationToken()

    def open_response(_url, _hosts, cancellation=None):
        response = next(responses)
        if cancellation is not None:
            cancellation.register_response(response)
        return response

    monkeypatch.setattr("core.update_checker._open_https_response", open_response)

    with pytest.raises(InterruptedError):
        download_release_asset(
            {
                "name": filename,
                "size": len(data),
                "browser_download_url": "https://github.com/asset",
            },
            {
                "name": "SHA256SUMS",
                "size": len(manifest),
                "browser_download_url": "https://github.com/checksums",
            },
            tmp_path,
            lambda _count: token.cancel(),
            token,
        )

    assert list(tmp_path.iterdir()) == []
    assert asset_response.closed


def test_download_failure_does_not_remove_existing_destination_file(monkeypatch, tmp_path):
    data = b"verified"
    filename = "release.AppImage"
    final_path = tmp_path / filename
    final_path.write_bytes(b"user data")
    manifest = f"{hashlib.sha256(data).hexdigest()}  {filename}\n".encode()
    responses = iter([_Response(manifest), _Response(data)])

    def open_response(_url, _hosts, cancellation=None):
        response = next(responses)
        if cancellation is not None:
            cancellation.register_response(response)
        return response

    monkeypatch.setattr(
        "core.update_checker._open_https_response",
        open_response,
    )

    with pytest.raises(FileExistsError):
        download_release_asset(
            {
                "name": filename,
                "size": len(data),
                "browser_download_url": "https://github.com/asset",
            },
            {
                "name": "SHA256SUMS",
                "size": len(manifest),
                "browser_download_url": "https://github.com/checksums",
            },
            tmp_path,
        )
    assert final_path.read_bytes() == b"user data"


def test_cancellation_closes_active_response():
    token = CancellationToken()
    response = _Response(b"data")
    token.register_response(response)
    token.cancel()
    assert response.closed
    assert token.cancelled

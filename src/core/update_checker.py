# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt-independent GitHub release lookup and verified asset download helpers."""

from __future__ import annotations

import hashlib
import http.client
import json
import logging
import os
import platform
import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse

from core.version import parse_calver

logger = logging.getLogger(__name__)
LATEST_RELEASE_URL = (
    "https://api.github.com/repos/DewaldOosthuizen/py-tray-command-launcher/releases/latest"
)
REQUEST_TIMEOUT_SECONDS = 10
_API_RESPONSE_MAX_BYTES = 2 * 1024 * 1024
_ALLOWED_DOWNLOAD_HOSTS = frozenset(
    {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}
)
_USER_AGENT = "py-tray-command-launcher-updater"
_DOWNLOAD_CHUNK_SIZE = 64 * 1024
_MANIFEST_MAX_BYTES = 2 * 1024 * 1024
_MAX_REDIRECTS = 5


@dataclass(frozen=True)
class ReleaseAsset:
    """Validated GitHub release asset metadata."""

    name: str
    size: int
    url: str


@dataclass(frozen=True)
class ReleaseInfo:
    """Stable release data needed by the tray and downloader."""

    version: str
    name: str
    html_url: str
    assets: tuple[ReleaseAsset, ...]

    def asset(self, name: str) -> ReleaseAsset | None:
        """Return the uniquely named release asset, if present."""
        matching = [asset for asset in self.assets if asset.name == name]
        return matching[0] if len(matching) == 1 else None


@dataclass(frozen=True)
class DownloadResult:
    """Path and integrity metadata for a verified downloaded asset."""

    path: Path
    size: int
    sha256: str


class CancellationToken:
    """Cooperative cancellation state that closes the current HTTP response."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._response = None

    @property
    def cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        return self._event.is_set()

    def register_response(self, response) -> None:
        """Track a response so cancellation can interrupt a blocked stream."""
        with self._lock:
            if self.cancelled:
                response.close()
            else:
                self._response = response

    def clear_response(self, response) -> None:
        """Stop tracking a response after its request has completed."""
        with self._lock:
            if self._response is response:
                self._response = None

    def cancel(self) -> None:
        """Request cancellation and close any currently active response."""
        self._event.set()
        with self._lock:
            response = self._response
            self._response = None
        if response is not None:
            try:
                response.close()
            except OSError:
                logger.debug("Unable to close cancelled update response", exc_info=True)

    def raise_if_cancelled(self) -> None:
        """Raise ``InterruptedError`` when cancellation was requested."""
        if self.cancelled:
            raise InterruptedError("Update operation was cancelled")


class _HTTPSResponse:
    """Own an HTTPS connection and expose its response as a closeable stream."""

    def __init__(self, connection, response, url: str) -> None:
        self._connection = connection
        self._response = response
        self._url = url

    def read(self, size: int = -1) -> bytes:
        """Read response bytes from the active HTTPS stream."""
        return self._response.read(size)

    def geturl(self) -> str:
        """Return the final URL after any validated redirects."""
        return self._url

    def close(self) -> None:
        """Close both the response stream and its owning connection."""
        try:
            self._response.close()
        finally:
            self._connection.close()

    def __enter__(self) -> _HTTPSResponse:
        return self

    def __exit__(self, *_args) -> None:
        self.close()


def _validate_https_url(url: str, allowed_hosts: frozenset[str]) -> None:
    """Require HTTPS, an approved host, and no credentials or custom port."""
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Update asset URL has an invalid port") from exc
    host = parsed.hostname
    if (
        parsed.scheme != "https"
        or host is None
        or host not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise ValueError("Update asset URL must use HTTPS on an approved GitHub host")


def _validate_download_url(url: str) -> None:
    """Require an HTTPS URL hosted by a GitHub release-asset endpoint."""
    _validate_https_url(url, _ALLOWED_DOWNLOAD_HOSTS)


def _open_https_response(
    url: str,
    allowed_hosts: frozenset[str],
    cancellation: CancellationToken | None = None,
) -> _HTTPSResponse:
    """Perform a timeout-bounded HTTPS GET with validated redirects."""
    current_url = url
    for redirect_number in range(_MAX_REDIRECTS + 1):
        _validate_https_url(current_url, allowed_hosts)
        parsed = urlparse(current_url)
        host = parsed.hostname
        if host is None:
            raise ValueError("Update URL must include a host")
        connection = http.client.HTTPSConnection(
            host,
            port=parsed.port,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        request_target = parsed.path or "/"
        if parsed.query:
            request_target = f"{request_target}?{parsed.query}"
        try:
            connection.request(
                "GET",
                request_target,
                headers={"User-Agent": _USER_AGENT},
            )
            response = connection.getresponse()
        except Exception:
            connection.close()
            raise

        if response.status in {301, 302, 303, 307, 308}:
            location = response.getheader("Location")
            response.close()
            connection.close()
            if not location or redirect_number >= _MAX_REDIRECTS:
                raise URLError("Update request exceeded or lacked a valid redirect")
            current_url = urljoin(current_url, location)
            continue
        if not 200 <= response.status < 300:
            status, reason, headers = response.status, response.reason, response.headers
            response.close()
            connection.close()
            raise HTTPError(current_url, status, reason, headers, None)

        result = _HTTPSResponse(connection, response, current_url)
        if cancellation is not None:
            cancellation.register_response(result)
        return result
    raise URLError("Update request exceeded the redirect limit")


def _open_response(url: str, cancellation: CancellationToken | None = None):
    """Open a download response and enforce the approved GitHub asset hosts."""
    _validate_download_url(url)
    return _open_https_response(url, _ALLOWED_DOWNLOAD_HOSTS, cancellation)


def _release_from_payload(payload: object) -> ReleaseInfo | None:
    """Validate API fields and convert a latest-release object to typed data."""
    if not isinstance(payload, dict):
        return None
    version = payload.get("tag_name")
    name = payload.get("name") or version
    html_url = payload.get("html_url")
    if (
        not isinstance(version, str)
        or not version
        or not isinstance(name, str)
        or not name
        or not isinstance(html_url, str)
        or not html_url
        or not isinstance(payload.get("draft"), bool)
        or not isinstance(payload.get("prerelease"), bool)
    ):
        return None
    if not parse_calver(version) or not _is_github_release_page(html_url):
        return None
    raw_assets = payload.get("assets")
    if not isinstance(raw_assets, list):
        return None

    assets = []
    for item in raw_assets:
        if not isinstance(item, dict):
            continue
        asset_name = item.get("name")
        size = item.get("size")
        url = item.get("browser_download_url")
        if (
            isinstance(asset_name, str)
            and asset_name
            and isinstance(size, int)
            and not isinstance(size, bool)
            and size >= 0
            and isinstance(url, str)
        ):
            try:
                _validate_download_url(url)
            except ValueError:
                logger.warning("Ignoring release asset with unsafe URL: %s", asset_name)
                continue
            assets.append(ReleaseAsset(asset_name, size, url))
    return ReleaseInfo(version, name, html_url, tuple(assets))


def _is_github_release_page(url: str) -> bool:
    """Check that a release page URL is an HTTPS GitHub page."""
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
    )


def fetch_latest_release() -> ReleaseInfo | None:
    """Fetch and validate the latest stable release from GitHub.

    Returns:
        Validated release information, or ``None`` for unavailable or unusable
        API responses. Network and payload errors are logged and not propagated.
    """
    try:
        with _open_https_response(LATEST_RELEASE_URL, frozenset({"api.github.com"})) as response:
            content = response.read(_API_RESPONSE_MAX_BYTES + 1)
        if len(content) > _API_RESPONSE_MAX_BYTES:
            raise ValueError("GitHub latest-release response is too large")
        payload = json.loads(content.decode("utf-8"))
        release = _release_from_payload(payload)
        if release is None:
            logger.warning("GitHub latest-release response had invalid fields")
            return None
        if payload.get("draft") is True or payload.get("prerelease") is True:
            logger.info("Ignoring draft or prerelease response from GitHub")
            return None
        return release
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        http.client.HTTPException,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        logger.info("GitHub release check unavailable", exc_info=True)
    except (TypeError, ValueError, AttributeError):
        logger.warning("GitHub latest-release response was malformed", exc_info=True)
    return None


def check_for_update(current_version: str) -> ReleaseInfo | None:
    """Return the latest stable release only when newer than a valid CalVer.

    Args:
        current_version: Version string embedded in or installed with the app.

    Returns:
        A strictly newer release, or ``None`` when the local version is not a
        CalVer, no newer release exists, or the remote check fails.
    """
    local = parse_calver(current_version)
    if local is None:
        return None
    release = fetch_latest_release()
    remote = parse_calver(release.version) if release is not None else None
    return release if remote is not None and remote > local else None


def select_release_asset(
    assets: tuple[ReleaseAsset, ...] | list[dict], system: str, architecture: str
) -> ReleaseAsset | None:
    """Select an asset matching a supported OS and CPU architecture.

    Args:
        assets: Validated release assets or API asset dictionaries.
        system: Platform system name, such as ``Linux`` or ``Windows``.
        architecture: Machine architecture reported by the runtime.

    Returns:
        A uniquely matching asset, or ``None`` when this platform has no
        published compatible asset.
    """
    os_name = system.lower()
    arch = architecture.lower()
    supported = {
        ("linux", "x86_64"): ("x86_64.AppImage",),
        ("linux", "amd64"): ("x86_64.AppImage",),
        ("windows", "amd64"): ("x86_64.exe", "amd64.exe"),
        ("windows", "x86_64"): ("x86_64.exe", "amd64.exe"),
        ("darwin", "x86_64"): ("x86_64.dmg",),
        ("darwin", "arm64"): ("arm64.dmg", "aarch64.dmg"),
        ("macos", "x86_64"): ("x86_64.dmg",),
        ("macos", "arm64"): ("arm64.dmg", "aarch64.dmg"),
    }.get((os_name, arch))
    if supported is None:
        return None
    normalized_assets = []
    for asset in assets:
        if isinstance(asset, ReleaseAsset):
            normalized_assets.append(asset)
        elif isinstance(asset, dict):
            try:
                normalized_assets.append(
                    ReleaseAsset(asset["name"], asset["size"], asset["browser_download_url"])
                )
            except (KeyError, TypeError):
                continue
    matches = [
        asset
        for asset in normalized_assets
        if any(asset.name.endswith(suffix) for suffix in supported)
    ]
    return matches[0] if len(matches) == 1 else None


def _read_manifest_entry(
    asset: ReleaseAsset, filename: str, cancellation: CancellationToken
) -> str:
    """Fetch the checksum manifest and find the exact asset filename entry."""
    response = _open_response(asset.url, cancellation)
    try:
        with response:
            content = response.read(_MANIFEST_MAX_BYTES + 1)
    finally:
        cancellation.clear_response(response)
    if len(content) > _MANIFEST_MAX_BYTES:
        raise ValueError("SHA256SUMS manifest is too large")
    matches = []
    for line in content.decode("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line)
        if match and match.group(2) == filename:
            matches.append(match.group(1).lower())
    if len(matches) != 1:
        raise ValueError(f"SHA256SUMS must contain one checksum for {filename}")
    return matches[0]


def download_release_asset(
    asset: ReleaseAsset | dict,
    checksum_asset: ReleaseAsset | dict,
    destination: Path,
    progress_callback=None,
    cancellation: CancellationToken | None = None,
) -> DownloadResult:
    """Download an asset, verify size and manifest SHA256, then retain it.

    Args:
        asset: Selected release asset with expected size and download URL.
        checksum_asset: The release's ``SHA256SUMS`` manifest asset.
        destination: Target download directory.
        progress_callback: Optional callback receiving cumulative byte counts.
        cancellation: Optional cooperative token used to close active streams.

    Returns:
        Metadata for the verified, non-executable download.

    Raises:
        InterruptedError: If cancellation is requested during transfer.
        OSError, ValueError: If the transfer, URL, size, or checksum is invalid.
    """
    if isinstance(asset, dict):
        asset = ReleaseAsset(asset["name"], asset["size"], asset["browser_download_url"])
    if isinstance(checksum_asset, dict):
        checksum_asset = ReleaseAsset(
            checksum_asset["name"],
            checksum_asset["size"],
            checksum_asset["browser_download_url"],
        )
    if checksum_asset.name != "SHA256SUMS":
        raise ValueError("Release checksum asset must be named SHA256SUMS")
    if not isinstance(asset.size, int) or isinstance(asset.size, bool) or asset.size < 0:
        raise ValueError("Release asset size must be a non-negative integer")
    _validate_download_url(asset.url)
    _validate_download_url(checksum_asset.url)
    filename = asset.name
    if (
        Path(filename).name != filename
        or "/" in filename
        or "\\" in filename
        or filename in {"", ".", ".."}
    ):
        raise ValueError("Release asset filename is invalid")
    token = cancellation or CancellationToken()
    expected_digest = _read_manifest_entry(checksum_asset, filename, token)
    token.raise_if_cancelled()

    destination = Path(destination).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    final_path = destination / filename
    temporary_path = destination / f".{filename}.{uuid.uuid4().hex}.part"
    digest = hashlib.sha256()
    total = 0
    installed = False
    try:
        with _open_response(asset.url, token) as response:
            with temporary_path.open("xb") as output:
                while True:
                    token.raise_if_cancelled()
                    chunk = response.read(_DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
                    total += len(chunk)
                    if total > asset.size:
                        raise ValueError("Downloaded asset exceeds its published size")
                    if progress_callback is not None:
                        progress_callback(total)
                output.flush()
                os.fsync(output.fileno())
        token.clear_response(response)
        token.raise_if_cancelled()
        if total != asset.size:
            raise ValueError(f"Downloaded size mismatch: expected {asset.size}, received {total}")
        actual_digest = digest.hexdigest()
        if actual_digest != expected_digest:
            raise ValueError("Downloaded SHA256 does not match SHA256SUMS")
        os.chmod(temporary_path, 0o600)
        os.link(temporary_path, final_path)
        installed = True
        temporary_path.unlink()
        return DownloadResult(final_path, total, actual_digest)
    except Exception:
        token.clear_response(locals().get("response"))
        temporary_path.unlink(missing_ok=True)
        if installed:
            final_path.unlink(missing_ok=True)
        raise


def current_platform() -> tuple[str, str]:
    """Return normalized operating system and machine identifiers."""
    system = platform.system().lower()
    architecture = platform.machine().lower()
    if architecture == "x64":
        architecture = "x86_64"
    return system, architecture

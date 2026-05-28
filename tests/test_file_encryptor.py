"""Tests for EncryptionWorker in src/modules/file_encryptor.py — issue #38.

All PyQt6 symbols are stubbed at module level so tests run without a display.
"""
import sys
import struct
import os
import tempfile
from unittest.mock import MagicMock, patch

# ---------- stub PyQt6 before any src import ----------
_pyqt6 = MagicMock()
sys.modules.setdefault("PyQt6", _pyqt6)
sys.modules.setdefault("PyQt6.QtWidgets", _pyqt6.QtWidgets)
sys.modules.setdefault("PyQt6.QtCore", _pyqt6.QtCore)
sys.modules.setdefault("PyQt6.QtGui", _pyqt6.QtGui)

# Make pyqtSignal return a MagicMock so class body doesn't crash
_pyqt6.QtCore.QThread = object
_pyqt6.QtCore.pyqtSignal = MagicMock(return_value=MagicMock())
_pyqt6.QtCore.Qt = MagicMock()

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.file_encryptor import (
    EncryptionWorker,
    _PBKDF2_ITERATIONS,
    _LEGACY_ITERATIONS,
    SALT_FILE_SUFFIX,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_worker(operation="encrypt", file_path="/tmp/dummy", password="secret", is_folder=False):
    """Create an EncryptionWorker without starting it."""
    w = EncryptionWorker.__new__(EncryptionWorker)
    w.operation = operation
    w.file_path = file_path
    w.password = password
    w.is_folder = is_folder
    # Replace Qt signals with plain mocks so emit() works in tests
    w.finished_signal = MagicMock()
    w.progress_updated = MagicMock()
    w.status_updated = MagicMock()
    return w


# ---------------------------------------------------------------------------
# Constant value guard
# ---------------------------------------------------------------------------

def test_pbkdf2_iterations_constant_is_600000():
    """_PBKDF2_ITERATIONS must equal the OWASP 2023 minimum of 600 000."""
    assert _PBKDF2_ITERATIONS == 600_000


def test_legacy_iterations_constant_is_100000():
    """_LEGACY_ITERATIONS must record the old hard-coded value."""
    assert _LEGACY_ITERATIONS == 100_000


# ---------------------------------------------------------------------------
# _derive_key — determinism and sensitivity to iterations
# ---------------------------------------------------------------------------

def test_derive_key_is_deterministic():
    """Same password + salt + iterations must always return the same key."""
    worker = _make_worker()
    salt = os.urandom(16)
    key1 = worker._derive_key("password", salt, iterations=1000)
    key2 = worker._derive_key("password", salt, iterations=1000)
    assert key1 == key2


def test_derive_key_differs_with_different_iterations():
    """Different iteration counts must produce different keys."""
    worker = _make_worker()
    salt = os.urandom(16)
    key_new = worker._derive_key("password", salt, iterations=_PBKDF2_ITERATIONS)
    key_old = worker._derive_key("password", salt, iterations=_LEGACY_ITERATIONS)
    assert key_new != key_old


# ---------------------------------------------------------------------------
# Encrypt/decrypt round-trip — new 20-byte salt format
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip_new_format(tmp_path):
    """Encrypt a file, verify 20-byte .salt, decrypt and recover plaintext."""
    # Create a temp plaintext file
    plain = tmp_path / "secret.txt"
    plain.write_text("Hello OWASP 2023")

    # --- ENCRYPT ---
    worker_enc = _make_worker(operation="encrypt", file_path=str(plain))
    worker_enc.run()

    salt_file = str(plain) + SALT_FILE_SUFFIX
    enc_file = str(plain) + ".enc"

    assert os.path.exists(salt_file), ".salt file must be created on encrypt"
    assert os.path.getsize(salt_file) == 20, ".salt file must be 20 bytes (4-byte uint32 + 16-byte salt)"
    assert os.path.exists(enc_file), ".enc file must be created on encrypt"
    assert not plain.exists(), "original file must be removed after encrypt"

    # --- DECRYPT ---
    worker_dec = _make_worker(operation="decrypt", file_path=str(enc_file))
    worker_dec.run()

    assert plain.exists(), "original file must be restored after decrypt"
    assert plain.read_text() == "Hello OWASP 2023"


# ---------------------------------------------------------------------------
# Legacy fallback — 16-byte salt file
# ---------------------------------------------------------------------------

def test_decrypt_legacy_16byte_salt(tmp_path):
    """Decrypting with a legacy 16-byte .salt file must use _LEGACY_ITERATIONS."""
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.fernet import Fernet
    import base64

    # Build a file encrypted with the old iteration count manually
    password = "legacy-pass"
    salt = os.urandom(16)

    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=_LEGACY_ITERATIONS)
    key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
    plaintext = b"legacy content"
    encrypted = Fernet(key).encrypt(plaintext)

    # Write .enc file
    plain_path = tmp_path / "file.txt"
    enc_path = tmp_path / "file.txt.enc"
    enc_path.write_bytes(encrypted)

    # Write 16-byte legacy .salt file (no iteration count prefix)
    salt_file = tmp_path / "file.txt.salt"
    salt_file.write_bytes(salt)

    # Decrypt using worker
    worker = _make_worker(operation="decrypt", file_path=str(enc_path), password=password)
    worker.run()

    assert plain_path.exists(), "plaintext must be restored from legacy-format encrypted file"
    assert plain_path.read_bytes() == plaintext


# ---------------------------------------------------------------------------
# Corrupt salt file guard
# ---------------------------------------------------------------------------

def test_decrypt_corrupt_salt_emits_error(tmp_path):
    """A .salt file with an invalid length must emit finished_signal(False, ...)."""
    enc_file = tmp_path / "file.txt.enc"
    enc_file.write_bytes(b"dummy")

    salt_file = tmp_path / "file.txt.salt"
    salt_file.write_bytes(b"tooshort")   # 8 bytes — neither 16 nor 20

    worker = _make_worker(operation="decrypt", file_path=str(enc_file))
    worker.run()

    worker.finished_signal.emit.assert_called_once()
    call_args = worker.finished_signal.emit.call_args[0]
    assert call_args[0] is False, "success flag must be False for corrupt salt"
    assert "corrupt" in call_args[1].lower() or "unrecognised" in call_args[1].lower()

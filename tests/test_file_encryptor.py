# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for file_encryptor — PBKDF2 iteration count and salt-file format."""

import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Stub PyQt6 so the module can be imported without a display server.
# QThread must be a real Python class so EncryptionWorker can subclass it
# and __new__ works correctly during tests.
class _FakeQThread:
    """Minimal QThread stub — just enough for EncryptionWorker to subclass."""
    def __init__(self, *args, **kwargs):
        pass
    def start(self):
        pass

_qt_core_stub = MagicMock()
_qt_core_stub.QThread = _FakeQThread
_qt_core_stub.pyqtSignal = MagicMock(return_value=MagicMock())
_qt_core_stub.Qt = MagicMock()

sys.modules.setdefault("PyQt6", MagicMock())
sys.modules.setdefault("PyQt6.QtWidgets", MagicMock())
sys.modules["PyQt6.QtCore"] = _qt_core_stub

# Make src/ importable.
SRC_DIR = Path(__file__).parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from modules.file_encryptor import (  # noqa: E402
    _LEGACY_ITERATIONS,
    _PBKDF2_ITERATIONS,
    EncryptionWorker,
)


class TestPbkdf2Constant(unittest.TestCase):
    """Verify the PBKDF2 iteration constant meets the OWASP 2023 minimum."""

    def test_pbkdf2_iterations_equals_600000(self):
        """_PBKDF2_ITERATIONS must be 600 000 to meet OWASP 2023 minimum."""
        self.assertEqual(_PBKDF2_ITERATIONS, 600_000)

    def test_legacy_iterations_equals_100000(self):
        """_LEGACY_ITERATIONS must document the old value of 100 000."""
        self.assertEqual(_LEGACY_ITERATIONS, 100_000)


class TestDeriveKey(unittest.TestCase):
    """Unit tests for EncryptionWorker._derive_key."""

    def _make_worker(self):
        worker = EncryptionWorker.__new__(EncryptionWorker)
        worker.password = "test-password"
        return worker

    def test_deterministic_output(self):
        """Same password, salt, and iterations must produce identical keys."""
        worker = self._make_worker()
        salt = os.urandom(16)
        key1 = worker._derive_key("secret", salt, iterations=100_000)
        key2 = worker._derive_key("secret", salt, iterations=100_000)
        self.assertEqual(key1, key2)

    def test_different_iterations_produce_different_keys(self):
        """Different iteration counts must produce different keys."""
        worker = self._make_worker()
        salt = os.urandom(16)
        key_low = worker._derive_key("secret", salt, iterations=100_000)
        key_high = worker._derive_key("secret", salt, iterations=200_000)
        self.assertNotEqual(key_low, key_high)

    def test_default_iterations_is_pbkdf2_constant(self):
        """Default iterations parameter must equal _PBKDF2_ITERATIONS."""
        worker = self._make_worker()
        salt = os.urandom(16)
        key_default = worker._derive_key("secret", salt)
        key_explicit = worker._derive_key("secret", salt, iterations=_PBKDF2_ITERATIONS)
        self.assertEqual(key_default, key_explicit)


class TestEncryptDecryptRoundTrip(unittest.TestCase):
    """Integration test for the full encrypt → decrypt cycle."""

    def _run_worker(self, operation, file_path, password, is_folder=False):
        worker = EncryptionWorker(operation, file_path, password, is_folder)
        results = {}

        def on_finished(success, message):
            results["success"] = success
            results["message"] = message

        worker.finished_signal = MagicMock()
        worker.finished_signal.emit.side_effect = on_finished
        worker.progress_updated = MagicMock()
        worker.status_updated = MagicMock()
        worker.run()
        return results

    def test_new_salt_file_is_20_bytes(self):
        """After encryption the .salt file must be 20 bytes (4 + 16)."""
        with tempfile.TemporaryDirectory() as tmp:
            plain_file = os.path.join(tmp, "data.txt")
            Path(plain_file).write_text("hello world")

            result = self._run_worker("encrypt", plain_file, "pass123")
            self.assertTrue(result.get("success"), result.get("message"))

            salt_file = plain_file + ".salt"
            self.assertTrue(os.path.exists(salt_file), "Salt file not created")
            self.assertEqual(os.path.getsize(salt_file), 20,
                             "Salt file must be 20 bytes (4-byte uint32 + 16-byte salt)")

    def test_round_trip_restores_plaintext(self):
        """Encrypt then decrypt must restore the original plaintext."""
        original_content = b"super secret data"
        with tempfile.TemporaryDirectory() as tmp:
            plain_file = os.path.join(tmp, "secret.txt")
            Path(plain_file).write_bytes(original_content)

            enc_result = self._run_worker("encrypt", plain_file, "mypassword")
            self.assertTrue(enc_result.get("success"), enc_result.get("message"))

            enc_file = plain_file + ".enc"
            dec_result = self._run_worker("decrypt", enc_file, "mypassword")
            self.assertTrue(dec_result.get("success"), dec_result.get("message"))

            self.assertEqual(Path(plain_file).read_bytes(), original_content)


class TestLegacySaltFallback(unittest.TestCase):
    """Decryption with a legacy 16-byte salt file must succeed using 100 000 iterations."""

    def test_legacy_16_byte_salt_decrypts_correctly(self):
        """Files encrypted with the old 100 000 iteration scheme must still decrypt."""
        import base64
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        password = "legacy-password"
        salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=_LEGACY_ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
        fernet = Fernet(key)
        original = b"legacy file content"
        encrypted = fernet.encrypt(original)

        with tempfile.TemporaryDirectory() as tmp:
            plain_file = os.path.join(tmp, "legacy.txt")
            enc_file = plain_file + ".enc"
            salt_file = plain_file + ".salt"

            # Write legacy 16-byte salt file
            Path(salt_file).write_bytes(salt)
            Path(enc_file).write_bytes(encrypted)

            worker = EncryptionWorker("decrypt", enc_file, password)
            worker.finished_signal = MagicMock()
            worker.progress_updated = MagicMock()
            worker.status_updated = MagicMock()

            results = {}

            def on_finished(success, message):
                results["success"] = success
                results["message"] = message

            worker.finished_signal.emit.side_effect = on_finished
            worker.run()

            self.assertTrue(results.get("success"), results.get("message"))
            self.assertEqual(Path(plain_file).read_bytes(), original)


class TestCorruptSaltFile(unittest.TestCase):
    """Decryption with a corrupt or unrecognised salt file must emit failure signal."""

    def test_corrupt_salt_emits_error(self):
        """A salt file of unexpected length must cause finished_signal(False, ...)."""
        with tempfile.TemporaryDirectory() as tmp:
            plain_file = os.path.join(tmp, "file.txt")
            enc_file = plain_file + ".enc"
            salt_file = plain_file + ".salt"

            # Dummy encrypted content (won't be reached due to salt error)
            Path(enc_file).write_bytes(b"garbage")
            # Corrupt salt: 10 bytes (neither 16 nor 20)
            Path(salt_file).write_bytes(b"A" * 10)

            worker = EncryptionWorker("decrypt", enc_file, "anypassword")
            worker.finished_signal = MagicMock()
            worker.progress_updated = MagicMock()
            worker.status_updated = MagicMock()

            results = {}

            def on_finished(success, message):
                results["success"] = success
                results["message"] = message

            worker.finished_signal.emit.side_effect = on_finished
            worker.run()

            self.assertFalse(results.get("success", True))
            self.assertIn("corrupt", results.get("message", "").lower())


if __name__ == "__main__":
    unittest.main()

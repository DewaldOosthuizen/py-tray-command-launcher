# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for file_encryptor — PBKDF2 iteration count and salt-file format."""

import os
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


class TestLegacyDetectedSignal(unittest.TestCase):
    """EncryptionWorker must emit legacy_detected when a 16-byte salt is found."""

    def _run_worker_decrypt(self, enc_file, password):
        worker = EncryptionWorker("decrypt", enc_file, password)
        worker.finished_signal = MagicMock()
        worker.progress_updated = MagicMock()
        worker.status_updated = MagicMock()
        worker.legacy_detected = MagicMock()

        results = {}

        def on_finished(success, message):
            results["success"] = success
            results["message"] = message

        worker.finished_signal.emit.side_effect = on_finished
        worker.run()
        return worker, results

    def _encrypt_with_legacy(self, plain_file, password):
        """Encrypt a file using legacy 100 000 iterations and 16-byte salt."""
        import base64

        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        salt = os.urandom(16)
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=_LEGACY_ITERATIONS)
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        fernet = Fernet(key)
        plaintext = Path(plain_file).read_bytes()
        encrypted = fernet.encrypt(plaintext)

        enc_file = plain_file + ".enc"
        salt_file = plain_file + ".salt"
        Path(enc_file).write_bytes(encrypted)
        Path(salt_file).write_bytes(salt)  # 16-byte legacy format
        return enc_file

    def test_legacy_detected_emitted_for_16_byte_salt(self):
        """Worker must emit legacy_detected with decrypted path when salt is 16 bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            plain_file = os.path.join(tmp, "doc.txt")
            Path(plain_file).write_bytes(b"legacy content")
            enc_file = self._encrypt_with_legacy(plain_file, "pw")
            # Remove the original so decrypt can write it back
            os.remove(plain_file)

            worker, results = self._run_worker_decrypt(enc_file, "pw")

            self.assertTrue(results.get("success"), results.get("message"))
            worker.legacy_detected.emit.assert_called_once()
            emitted_path = worker.legacy_detected.emit.call_args[0][0]
            self.assertEqual(emitted_path, plain_file)

    def test_legacy_detected_not_emitted_for_20_byte_salt(self):
        """Worker must NOT emit legacy_detected when salt file is 20 bytes (current format)."""
        original_content = b"current content"
        with tempfile.TemporaryDirectory() as tmp:
            plain_file = os.path.join(tmp, "doc.txt")
            Path(plain_file).write_bytes(original_content)

            # Encrypt with current format
            enc_worker = EncryptionWorker("encrypt", plain_file, "pw")
            enc_worker.finished_signal = MagicMock()
            enc_worker.progress_updated = MagicMock()
            enc_worker.status_updated = MagicMock()
            enc_worker.run()

            enc_file = plain_file + ".enc"
            worker, results = self._run_worker_decrypt(enc_file, "pw")

            self.assertTrue(results.get("success"), results.get("message"))
            worker.legacy_detected.emit.assert_not_called()


class TestReencryptToCurrentStandard(unittest.TestCase):
    """Tests for FileEncryptor._reencrypt_to_current_standard."""

    def _make_encryptor(self):
        from modules.file_encryptor import FileEncryptor
        services = MagicMock()
        enc = FileEncryptor.__new__(FileEncryptor)
        enc.services = services
        return enc

    def test_reencrypt_produces_20_byte_salt_and_enc_file(self):
        """_reencrypt_to_current_standard must produce a 20-byte .salt and .enc file."""
        import modules.file_encryptor as fe_mod
        from modules.file_encryptor import ENC_FILE_SUFFIX, SALT_FILE_SUFFIX

        with tempfile.TemporaryDirectory() as tmp:
            plain_file = os.path.join(tmp, "plain.txt")
            Path(plain_file).write_bytes(b"secret data")

            enc = self._make_encryptor()

            accepted_sentinel = object()
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = accepted_sentinel
            mock_dialog.get_password.return_value = "newpassword"

            mock_qdialog = MagicMock()
            mock_qdialog.DialogCode.Accepted = accepted_sentinel

            with patch.object(fe_mod, "PasswordDialog", return_value=mock_dialog), \
                 patch.object(fe_mod, "QDialog", mock_qdialog), \
                 patch.object(fe_mod.QMessageBox, "information"):
                enc._reencrypt_to_current_standard(plain_file)

            salt_file = plain_file + SALT_FILE_SUFFIX
            enc_file = plain_file + ENC_FILE_SUFFIX

            self.assertTrue(os.path.exists(salt_file), "Salt file must exist after re-encryption")
            self.assertTrue(os.path.exists(enc_file), "Enc file must exist after re-encryption")
            self.assertEqual(os.path.getsize(salt_file), 20, "Salt file must be 20 bytes")
            self.assertFalse(os.path.exists(plain_file), "Plaintext must be removed")

    def test_reencrypt_atomic_cleanup_on_rename_failure(self):
        """If rename fails after writing temp enc file, original plaintext is preserved."""
        import modules.file_encryptor as fe_mod

        with tempfile.TemporaryDirectory() as tmp:
            plain_file = os.path.join(tmp, "plain.txt")
            Path(plain_file).write_bytes(b"must survive")

            enc = self._make_encryptor()

            accepted_sentinel = object()
            mock_dialog = MagicMock()
            mock_dialog.get_password.return_value = "pw"
            mock_dialog.exec.return_value = accepted_sentinel

            mock_qdialog = MagicMock()
            mock_qdialog.DialogCode.Accepted = accepted_sentinel

            replace_call_count = [0]
            real_replace = os.replace

            def fake_replace(src, dst):
                replace_call_count[0] += 1
                if replace_call_count[0] == 1:
                    raise OSError("simulated rename failure")
                return real_replace(src, dst)

            with patch.object(fe_mod, "PasswordDialog", return_value=mock_dialog), \
                 patch.object(fe_mod, "QDialog", mock_qdialog), \
                 patch("os.replace", side_effect=fake_replace), \
                 patch.object(fe_mod.QMessageBox, "warning"):
                enc._reencrypt_to_current_standard(plain_file)

            # Original plaintext must still exist
            self.assertTrue(os.path.exists(plain_file), "Plaintext must be preserved on failure")
            self.assertEqual(Path(plain_file).read_bytes(), b"must survive")
            # No leftover .enc.tmp files
            tmp_files = [f for f in os.listdir(tmp) if f.endswith(".enc.tmp") or f.endswith(".salt.tmp")]
            self.assertEqual(tmp_files, [], f"Temp files not cleaned up: {tmp_files}")


if __name__ == "__main__":
    unittest.main()

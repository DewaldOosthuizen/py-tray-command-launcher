# ADD-013 — File encryption with Fernet and PBKDF2

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | security, encryption, cryptography |

---

## Context

The application is a personal command launcher that often stores commands
containing sensitive paths, credentials embedded in scripts, or internal
tooling references.  Users requested the ability to encrypt arbitrary files
from within the tray interface as a convenience feature — applying strong
symmetric encryption without leaving the application.

---

## Decision

`FileEncryptor` (`modules/file_encryptor.py`) implements symmetric encryption
using the `cryptography` library's `Fernet` scheme.

### Key derivation

The user provides a passphrase.  A random 16-byte salt is generated with
`os.urandom(16)` and stored in a companion `.salt` file alongside the
encrypted output.  The encryption key is derived from the passphrase + salt
using PBKDF2-HMAC-SHA256 with 480,000 iterations:

```python
kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=salt,
    iterations=480_000,
)
key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
fernet = Fernet(key)
```

The iteration count follows the 2023 OWASP recommendation for PBKDF2-SHA256.

### Encryption

1. Read the plaintext file in binary mode.
2. Derive the key as above.
3. `fernet.encrypt(plaintext)` — produces an authenticated ciphertext (AES-128-CBC
   + HMAC-SHA256 under the hood, with a timestamp and random IV per encryption).
4. Write the ciphertext to `<original_filename>.enc`.
5. Write the salt to `<original_filename>.salt`.

### Decryption

1. Read the salt from the `.salt` companion file.
2. Re-derive the key from the user-supplied passphrase + salt.
3. `fernet.decrypt(ciphertext)` — authenticates and decrypts; raises
   `InvalidToken` if the passphrase is wrong or the ciphertext is tampered.
4. Write the plaintext to the original filename.

### Threading

Encryption and decryption run in a `QThread` subclass to keep the UI
responsive for large files.  A `QProgressBar` widget in the dialog is updated
via `pyqtSignal` emitted by the worker thread.

---

## Alternatives considered

**GnuPG / gpg subprocess** — battle-tested and integrates with the system
keyring.  Rejected: requires GPG to be installed; adds a system dependency and
a subprocess; the `cryptography` library is already a direct dependency.

**AES-CBC with manual IV management** — possible but error-prone to implement
correctly (IV reuse, padding oracle).  Fernet encapsulates these concerns
behind a safe API.

**No encryption feature** — the feature is additive; users who do not need it
never encounter the dialog.

---

## Consequences

+ Fernet's authenticated encryption prevents silent data corruption — a wrong
  passphrase or tampered file raises `InvalidToken` rather than producing
  garbage output.
+ Per-file random salts and Fernet's per-encryption random IV mean two
  encryptions of the same file with the same passphrase produce different
  ciphertext.
+ The threading approach keeps the UI responsive during encryption of large files.
- The `.salt` file must remain alongside the `.enc` file for decryption;
  losing it makes decryption impossible.  Users must be aware of this coupling.
- The `cryptography` library adds a compiled dependency; it is already required
  for other features but will complicate builds on unusual architectures.
- 480,000 PBKDF2 iterations cause a noticeable (~0.5 s) delay on first
  key derivation; this is intentional (slows brute-force attacks) but may
  surprise users with slow hardware.

# File Encryption — Breaking Change (v2+)

The `.salt` file written alongside encrypted files is **20 bytes**:
4-byte big-endian uint32 iteration count + 16-byte random salt.

Previous versions wrote a 16-byte raw salt only.

## Impact

`.salt` files produced by this version **cannot** be read by older versions of
the application. `.salt` files produced by older versions are handled transparently by the
legacy fallback (iteration count assumed to be 100,000).

## Migration Path

To benefit from the stronger PBKDF2 work factor (600,000 iterations, OWASP 2023 minimum):

1. Decrypt your existing files using the current version (the legacy fallback handles the
   old 16-byte salt file automatically).
2. Re-encrypt the files using the current version — the new `.salt` file will be written in
   the 20-byte format with 600,000 iterations.

Do **not** copy `.salt` files between machines running different versions of the application
without verifying the file length (16 bytes = legacy, 20 bytes = current).

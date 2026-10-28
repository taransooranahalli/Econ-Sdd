# Accounts and encrypted saved plans

Status: implemented and verified locally in release 0.4.0 on 2026-10-28; requested by the user on 2026-10-27. Hosting remains a later milestone. This supersedes the earlier no-account/no-database constraint only for explicit account creation and saving.

## Scope and privacy boundary

Add username/password registration, sign in/out, password change, one-time recovery codes, and a private saved-plan library for savings, savings goals and monthly cash flow. Calculators remain usable without an account. Saving is explicit; no automatic collection of unsaved financial inputs. No email address, bank credentials, birth date, identity record, analytics or third-party identity service is needed in this milestone. Username is a local app identifier (3..32 ASCII letters/digits/period/underscore/hyphen, case-insensitive).

SQLite is the durable local database for one application instance with a persistent disk. Its adapter is independent of calculator math. Public hosting is not authorized and is not made ready merely by adding sign-in. A hosted deployment later needs a reviewed HTTPS/proxy/domain configuration, managed secret storage, encrypted backups/restore drills, durable storage, abuse monitoring/capacity limits, and a recovery/MFA/account-lifecycle review. PostgreSQL or an external identity provider can replace these adapters when hosting is selected; do not add unused services now.

## Credentials and sessions

Passwords: 15..128 characters, max 512 UTF-8 bytes, no truncation or composition rules, hashed with Argon2id (64 MiB, 3 iterations, parallelism 1, fresh random salts). Do not encrypt passwords reversibly. Never log passwords, recovery codes or cookies. Upgrade hashes at successful login when parameters change; invalid/nonexistent login uses the same safe message and a dummy hash verification path. Registration conflict gives a generic unavailable message. All auth work is bounded and runs off the async request loop.

Opaque 256-bit random session tokens are cookies, not browser storage. Database stores SHA-256 token digests only. Use HttpOnly, SameSite=Strict, Path=/; Secure with __Host- cookie prefix for an explicitly HTTPS origin. Local loopback HTTP needs a separately named non-Secure development cookie. Rotate tokens on sign in, registration, password change and recovery. Logout revokes the server-side token; password change/recovery revoke all sessions. Enforce 30-minute idle and 7-day absolute expiry server-side. CSRF for authenticated mutations is bound to the session; anonymous login/register/recovery retains the same-origin/token boundary. Check Host/origin, JSON content type and a 1 MiB body limit; apply no-store/security headers to errors as well as success. No GET performs an account or plan mutation.

Use persistent per-login/per-client attempt limits for sign in/register/recovery; do not trust arbitrary forwarded IP headers. Rate keys are HMACs, not raw usernames/IPs, and expired buckets are removed. This is a single-instance local baseline; internet hosting needs appropriate shared/global abuse controls and capacity review.

A random 256-bit recovery code is shown once after registration or password recovery/change; store only its digest. Recovery requires username, code and a new password; it consumes the code atomically, rotates it, and revokes all sessions. Losing both password and code means no self-service recovery. No email sending or support override is silently added.

## Encryption and key management

Use the maintained cryptography library's AES-256-GCM with fresh 96-bit random nonces and verified tags. Encrypt username display data and every saved plan's title and original inputs; passwords use hashes instead. Bind ciphertext to purpose, owner, plan ID and revision with associated data to reject swaps/tampering. Database metadata (random IDs, ownership links, revisions, timestamps, credential hashes and keyed lookup/rate indices) remains visible; do not claim the entire database is encrypted.

Keys are server-managed. The running server can decrypt inputs to calculate them; this is not end-to-end or zero-knowledge encryption. Protecting a database copy does not protect against compromise of the running server or theft of both database and keys. Existing downloaded JSON/CSV remains unencrypted and is labeled accordingly.

A versioned keyring has independent data-encryption and lookup/CSRF keys; keep it outside the database under .secrets/ with owner-only file/directory permissions and source-control exclusion. Database is under data/ with owner-only permissions. Initialization is explicit and idempotent, never overwrites a keyring, and refuses to regenerate keys when an existing database has lost its keyring. Startup checks key compatibility and schema version, and fails closed on missing/wrong keys or corrupted ciphertext. No secrets in browser bundles or examples. Production keys must come from a secret manager or equivalent separately protected mounted file; database backups and key recovery must be managed separately. Key rotation retains old decryption keys until all ciphertext is migrated and backups have aged out; test rotation and restart/restore before retiring a key.

## Saved-plan contract

Save only validated canonical original inputs, calculator kind and model version, plus an explicit plain-text title of 1..80 characters (encrypted). Recompute authoritative results on open; do not trust stored derived balances. Maximum 100 plans per user. List/open/update/delete always scopes database queries to the authenticated owner. Return the same 404 for missing and other-user plan IDs. IDs are random UUIDs; SQL is parameterized. Updates/deletion require the current revision so stale tabs cannot silently overwrite newer saves. All operations are transactional. Each calculator retains its own model version and existing JSON/CSV behavior.

Use /account for sign in/create/recover/change password, /plans for the library. Add account links and Save to account within the accepted Studio design. Restore using a non-sensitive saved-plan ID in the calculator URL; do not put financial inputs or tokens there. Signed-out access prompts sign-in without fetching another user's data. Inputs are not saved until Save to account is clicked. Signing out clears private calculator output from the current page and invalidates pending save/load responses; a page restored from back/forward cache must refresh authentication state. Other tabs detect auth changes before private saves/opens. Do not place credentials, tokens or plans in localStorage/sessionStorage.

## Acceptance criteria

- AUTH-AC-01: registration, sign in/out, password change and one-use recovery work with safe validation, strong password hashes, rotated/revoked sessions and expiry.
- AUTH-AC-02: private plans survive application restart; each calculator opens and recomputes saved inputs with original currency/provenance/model. Anonymous calculations and original exports work.
- AUTH-AC-03: two-user list/open/save/update/delete isolation, revision conflicts, CSRF/origin/Host/method/body guards, rate limits and safe errors pass tests. No sensitive values appear in logs.
- AUTH-AC-04: raw database has no plaintext usernames, plan titles, categories or financial input strings; ciphertext tampering/owner/revision swaps fail. Missing/wrong keys, unsupported schema and unsafe file permissions fail safely. Keys remain separate and excluded from source control.
- AUTH-AC-05: desktop/phone Studio account/library/save controls work with keyboard, loading/error/signed-out/stale states; no runtime external assets. Browser QA is separate from API tests.
- AUTH-AC-06: full math regression suite, security tests, restart/restore and key rotation checks pass; record tested limits and hosting work still pending. This is not an independent security audit or public deployment.

## References

- [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [OWASP cryptographic storage](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [cryptography authenticated encryption](https://cryptography.io/en/latest/hazmat/primitives/aead/)
- [argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html)

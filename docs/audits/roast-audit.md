Status: Remediated by `docs/plans/roast-audit-remediation-plan.md` on 2026-05-20, except the local `.env` finding which was explicitly out of scope by user request.

Untracked TODO comments - FIXED in `docs/plans/roast-audit-remediation-plan.md` Slice 4.
test_structure.py:173
 removed untracked chore comment, 
domain_profile_schema.py:3
 removed untracked phase-3 comment. Only 2 were found, which was restrained, but they were still tickets with no tracking. Fix: Link to GitHub issues or delete.

No CONTRIBUTING.md — Repo has a LICENSE (good) and README.md, but anyone who wants to contribute is left guessing at conventions. Fix: Create one, or at minimum point to AGENTS.md for conventions.

Frontend deps all float with ^ — 
package.json:20-37
. 18/18 production dependencies use ^ ranges. You do have a package-lock.json, so this is mitigated for CI, but local npm install without the lockfile is a roulette wheel. Fix: Acceptable given the lockfile exists; just ensure CI uses npm ci.

Committed root image asset - FIXED in `docs/plans/roast-audit-remediation-plan.md` Slice 4.
Moved root `image.png` to `docs/assets/crawlerai-logo.png` and updated `README.md`.

Spicy (real problems — fix before the next PR)
extraction_rules.py
 (all 1,955 lines) God module — This file is the Death Star of config constants. 1,955 lines of frozensets, regex patterns, tuples, and Decimal thresholds. No human can hold the full mental model. Fix: Split by domain — extraction_rules/pricing.py, extraction_rules/variants.py, extraction_rules/identity.py, etc. Re-export from __init__.py.

extraction_rules.py:37-39
 globals() mutation at import time — globals()[_name] = _value injects dynamically-named constants from a JSON file into the module namespace. This defeats static analysis, IDE autocompletion, and any type checker. Same pattern at 
field_mappings.py:22
 and 
selectors.py:19
. Fix: Load into an explicit typed dict/dataclass. If you must have module-level names, use __getattr__ with proper type stubs.

pyproject.toml:10-46
 All 36 backend dependencies use >= (floor-only) — No upper bounds, no lockfile (only uv.lock which isn't a standard pip lockfile). A single breaking release in any dep nukes your build. Fix: Pin exact versions or add upper bounds (e.g., fastapi>=0.116.0,<1.0). Or commit a requirements.txt from uv pip freeze.

pyproject.toml:84-100
 Pylint disables every useful check — too-many-arguments, too-many-branches, too-many-locals, too-many-return-statements, too-many-statements, too-many-lines, duplicate-code, missing-function-docstring. You didn't configure pylint — you muzzled it. Fix: Re-enable with reasonable thresholds (e.g., max-args=7, max-branches=15). Fix violations instead of silencing them.

126+ bare except Exception: catches across backend/app/ — Files like 
traversal_recovery.py
 have 9 of them alone. 
traversal_helpers.py
 has 6. Most log and continue, which is fine for browser automation resilience, but many swallow errors in business logic paths like 
batch_runtime.py:48
, 
listing_extractor.py:480
, 
provider_client.py:65
. Fix: Narrow to specific exceptions (PlaywrightError, TimeoutError, json.JSONDecodeError). At minimum, re-raise KeyboardInterrupt and SystemExit.

Test-to-source ratio: 0.24 — 92 test files for 390 source modules. The threshold for "suspicious" is 0.5. Critical modules with zero test coverage: security.py (JWT + encryption), auth_service.py, api_key_service.py, access_service.py, alert_service.py, config_service.py. You test the crawl engine exhaustively but the auth layer is a trust exercise. Fix: Write unit tests for security.py (JWT encode/decode roundtrip, password hash/verify, Fernet encrypt/decrypt) and auth_service.py at minimum.

state_normalizer.py
 (1,500 lines), 
identity/core.py
 (1,301 lines), 
browser_surface_probe/core.py
 (2,076 lines) More god modules — These are not generated files or lockfiles. They're hand-written logic with functions stretching well past 30 lines. Fix: Decompose into focused submodules. state_normalizer.py → ecommerce_mapper.py, job_mapper.py, nuxt_reviver.py, product_identity.py.

No CI pipeline beyond secret scanning — 
gitleaks.yml
 and a Playwright smoke test. No pytest in CI, no ruff in CI, no mypy in CI. Your linters and type checkers exist only in pyproject.toml as decoration. Fix: Add a backend-ci.yml that runs ruff check, mypy, and pytest on every push.

Scorched (blocking / security risk — fix now)
.env:3-51
 Live API keys in unencrypted .env on disk — 10 API keys (Anthropic, Firecrawl, NVIDIA, Groq, OpenRouter, Xiaomi, Bedrock, BrightData, Zyte, SerpAPI), a JWT secret, an encryption key, and admin credentials. The .gitignore catches .env so it's not tracked in git history, but the file sits unprotected on the filesystem. If this repo is ever pushed to a fork, cloned to a shared machine, or backed up to cloud storage, you're cooked. Fix: Rotate every single key immediately. Use a secrets manager (Vault, AWS SSM, doppler) or at minimum git-crypt for the .env. Verify with git log --all -S 'sk-ant-api03' that these values never leaked into history.

security.py:40
 Broken Fernet key derivation — base64.urlsafe_b64encode(key.ljust(32, b"0")[:32]) pads your encryption key with literal ASCII "0" bytes to reach 32 bytes, then base64-encodes. This means: (a) if your key is shorter than 32 bytes, you're padding with predictable bytes that reduce entropy, (b) ljust with b"0" uses the byte 0x30, not 0x00, so it's literally the digit zero, and (c) any key longer than 32 bytes is silently truncated. Fix: Use hashlib.sha256(key).digest() to derive a proper 32-byte key, or require the config value to already be a valid 32-byte base64 Fernet key and validate on startup.

config.py:129
 Password guard checks the wrong value — _INSECURE_ADMIN_PASSWORD_DEFAULTS contains {"YourSecurePassword123!"} but the actual .env uses "AdminPassword123!". The guard passes. In staging/production, if someone copies this .env and sets APP_ENV=staging, the app boots happily with a known admin password. Fix: Add "AdminPassword123!" to the set. Better yet, require default_admin_password to meet minimum complexity requirements (length ≥ 16, not in a known-weak list).

config.py:144
 Secret guard reads APP_ENV from os.environ, not from settings — env = os.getenv("APP_ENV", "development"). If someone sets APP_ENV in .env (which they do — line 1 of .env is APP_ENV=development) but the pydantic Settings object already parsed it, this is fine coincidentally. But if APP_ENV is set differently in the environment vs the .env file, the guard and the app disagree on what environment they're in. Fix: Add app_env: str = "development" to the Settings class and use settings.app_env in the guard.

The Verdict
The single most embarrassing finding is the broken Fernet key derivation in 
security.py:40
 — you wrote a crypto function that pads keys with the ASCII digit "0" and silently truncates long keys, and the module has zero tests, so nobody has ever verified it produces correct ciphertext or can round-trip. Combined with the password guard that doesn't actually catch the password you ship, and 10 live API keys sitting in .env, the security posture is a house of cards. On the positive side, the extraction architecture is genuinely well-designed — the three-tier priority system, the disciplined config separation, and the thoughtful browser automation recovery logic show real engineering craft where it matters most for the product. This isn't a bad codebase; it's a good codebase that skipped the boring parts.

Grade: C+ — Solid domain logic, serious security hygiene gaps, and a testing strategy that protects the crawl engine but leaves the front door unlocked.

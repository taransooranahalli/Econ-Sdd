# Publication and hosting

## Live GitHub Pages showcase

Repository: https://github.com/taransooranahalli/Econ-Sdd

Site: https://taransooranahalli.github.io/Econ-Sdd/

GitHub Pages serves the static portfolio from `site/`, built into `dist/showcase/`. It does not run FastAPI, Python calculations, sign-in or SQLite. Screenshots and walkthrough figures are explicitly synthetic precomputed examples. The full application runs locally using README instructions.

The repository's workflow runs tests and safety checks before generating an allowlisted Pages artifact. Only a main-branch push or manual main-branch workflow run can publish; pull requests verify and build without publishing. Repository Settings -> Pages must use GitHub Actions as its publishing source. The default project URL is `https://<owner>.github.io/Econ-Sdd/`; do not replace an existing `<owner>.github.io` personal-site repository.

The builder uses the actual `GITHUB_REPOSITORY` value for source links and a passing JUnit report for the displayed test count. It refuses private/generated files, symlinks, unreviewed assets, failed reports and leftover placeholders. A separate publication checker reviews the tracked or staged Git file set.

## Later: the full application

Use GitHub for source, review and CI, with a separate Python host. Before making account storage public, specify and verify:

1. A durable disk for SQLite with a single application instance, or a reviewed SQL migration. Do not use ephemeral service storage for real users.
2. Exact HTTPS origin, trusted proxy chain, secure cookies, CSRF/Host guards and health checks. The current local launcher does not accept public binds or trust forwarded headers.
3. Server keys from a secret manager or protected mount, independently recoverable from database backups. Never upload the local keyring or user database to GitHub.
4. Encrypted backups, retention and tested restore/rotation, plus account recovery/deletion and MFA decisions.
5. Internet-facing request/concurrency limits, abuse monitoring and operational capacity. Local security tests are not an independent penetration test.
6. Explicit hosting budget and deployment authorization. The user selected the Pages showcase first; no paid backend is created in this milestone.

[GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) describes the static service. [Render's free-tier documentation](https://render.com/docs/free) explains why free ephemeral filesystems do not preserve SQLite across service restarts. A provider choice is still pending.

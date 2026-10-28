# Security and privacy

This is an evolving portfolio project. The local account layer has automated security checks; it has not undergone an independent penetration test or been approved for public financial-data collection.

The GitHub Pages site is a static showcase. It has no live sign-in, saved accounts or financial-data entry. The Python/SQLite app is separate and currently supported locally.

Never commit or share `.secrets/`, `data/`, database files, session cookies, recovery codes, exported personal records or credentials. The publication checker blocks sensitive/generated paths and common credential patterns, but it is not a complete secret scanner. Review the actual Git file set before publishing.

Saved calculator inputs and usernames use authenticated encryption with server-managed keys. Passwords use Argon2id hashes. IDs, ownership links, revisions, timestamps and credential/lookup hashes remain visible metadata. A compromised running server or theft of both database and keys is outside the protection offered by encryption at rest.

Do not report a suspected vulnerability in a public issue with real data or secrets. Use GitHub private vulnerability reporting if it is enabled for the repository; otherwise contact the repository owner privately through their profile. Use synthetic reproduction data.

See [the account contract](docs/account-spec.md), [release checks](docs/plan.md), and [hosting boundary](docs/deployment.md). Public backend hosting needs a separate review of TLS, trusted proxies, secrets, durable data, backups, abuse controls and account lifecycle.

# Repository and GitHub Pages publication

Status: requested 2026-10-28. The user selected GitHub Pages showcase first; full backend hosting is deferred. Publishing the reviewed repository/showcase is authorized. No paid service or backend account deployment is authorized by this selection.

## Purpose and boundary

Publish Econ-Sdd as a public personal GitHub repository demonstrating specification-driven development. Its GitHub Pages project site presents synthetic calculator screenshots, documented worked examples, implementation status, and links to specifications, algorithms and tests. It is a portfolio showcase, not the running FastAPI service. No live sign-in or personal financial data entry on Pages, and no claim that accounts persist there.

The existing Python/SQLite application remains runnable locally. Its real database, keyring, sessions, downloaded records, virtual environment, editor caches and machine-specific files must never enter the Git index or Pages artifacts. A fresh repository begins with the current reviewed snapshot; do not fabricate earlier commits or pretend Git records the previous local milestones.

## PUB-AC-01..06

- PUB-AC-01: public README describes the problem, current features, architecture, SDD process and evidence, local setup and hosting boundary. Link the authoritative specs and tests. Record limitations and distinguish implemented work from plans.
- PUB-AC-02: traceability maps requirements to models/implementation and meaningful tests. Include the existing independent $2,277.26 savings, $154.92 goal and exact monthly cash flow examples. PR/issue templates keep future requirements and verification reviewable.
- PUB-AC-03: a local Git repository tracks only reviewed source/docs/tests/assets/workflows. Ignore and independently guard against private runtime data, key material, credentials, databases, exports and caches. Verify the actual staged file set before initial commit and upload.
- PUB-AC-04: GitHub Pages publishes only an allowlisted static showcase directory, with local fonts and synthetic screenshots. Source/repository/spec links are injected from the actual GitHub owner/repository. No backend URL, account form, secret or private data is bundled. Label all walkthroughs as synthetic, precomputed examples.
- PUB-AC-05: the GitHub workflow runs Python tests, JavaScript syntax, package checks and a tracked-file safety check before building/deploying Pages. Public test counts derive from a passing JUnit report rather than an invented badge. Pull requests can verify/build but cannot publish; only main publishes to the github-pages environment using least permissions.
- PUB-AC-06: inspect desktop/phone showcase layout, links and accessibility controls; retain screenshots and local verification. Create the repository under the verified personal account, push the initial commit, enable Pages Actions, and verify the returned deployment URL before claiming it live. If GitHub authorization is missing, complete independent preparation and report the exact pending step.

## Roadmap and scope

Implemented: deterministic savings, goal solving, monthly cash flow, local sign-in and encrypted reusable plans. Planned: investment/portfolio research and prediction-market analysis. ML forecasting and native acceleration remain separate future research tracks requiring validated experiments and profiling. The current milestone adds no investment recommendations, market feeds, brokerage execution or trading.

GitHub Pages serves static HTML/CSS/JavaScript. Durable FastAPI/SQLite hosting later requires a Python host, persistent disk or reviewed SQL migration, TLS/trusted proxy configuration, managed secrets/key recovery, backups, capacity/abuse controls and account-lifecycle review. Do not deploy a real-user SQLite database to ephemeral free storage.

## References

- [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
- [Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [Render free storage limits](https://render.com/docs/free)

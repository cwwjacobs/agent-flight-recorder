# Dependency integrity plan

This document records the dependency-integrity controls implemented for AI Dev
Readiness Phase 01 and the containment repair applied on 2026-06-19.

## Current controls

### 1. Python direct-dependency pins

- `backend/pyproject.toml` remains the authoritative source of dependency
  metadata and supported version ranges for setuptools.
- `backend/requirements.txt` pins the direct runtime and dev dependencies to
  exact versions verified for this repair, plus the explicit AnyIO
  compatibility constraint used by the test transport:
  - `fastapi==0.137.1`
  - `uvicorn==0.49.0`
  - `pytest==9.1.0`
  - `httpx==0.28.1`
  - `anyio==4.14.2` (includes fixes for CVE-2026-63374 and CVE-2026-64847)

### 2. Containment removal: `httpx2`

`httpx2==2.4.0` previously appeared in `backend/requirements.txt` and
`httpx2>=2.4,<3.0` previously appeared in `backend/pyproject.toml` under the
`dev` extra.

That package name was removed during containment because it was not required by
AFR source code and is suspiciously close to the legitimate `httpx` test client
dependency already used by FastAPI and Starlette tests. Treat the prior entries
as a dependency-confusion / typo risk unless independently proven safe.

### 3. UI dependency and build gate

The React/Vite dependency tree was reviewed and refreshed on 2026-09-19. CI
installs it with lifecycle scripts disabled, fails on high-severity audit
findings, and compiles the production bundle. The review upgraded React Router
to the supported 7.x line and refreshed vulnerable PostCSS/Nanoid transitive
versions; `npm audit` reported zero known vulnerabilities at review time.

`@playwright/test` was added 2026-09-24 as a dev-only dependency for the
browser smoke journey (`npm run test:e2e`). It is not part of the production
bundle, installs no browser binaries under `npm ci --ignore-scripts`, and
reported zero known vulnerabilities at add time. CI explicitly installs Chromium
and its system dependencies, then runs the journey against a freshly seeded
backend with the constrained Python packages and the real CLI export path.

### 4. CI action pinning

Workflows in `.github/workflows/ci.yml` pin official GitHub Actions to specific
commit SHAs with a version comment, e.g.:

```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
```

Pinned actions:

| Action              | SHA                                          | Version |
|---------------------|----------------------------------------------|---------|
| actions/checkout    | `11bd71901bbe5b1630ceea73d27597364c9af683`   | v4.2.2  |
| actions/setup-python| `8d9ed9ac5c53483de85588cdf95a591a75ab9f55`   | v5.5.0  |
| actions/setup-node  | `49933ea5288caeca8642d1e84afbd3f7d6820020`   | v4.4.0  |

## Updating the pin file

1. Activate a clean Python virtual environment.
2. Install the backend with its dev extras:
   `pip install --constraint backend/requirements.txt -e './backend[dev]'`
3. Run the test suite:
   `python -m pytest backend/tests -q`
4. Copy the installed versions of the direct dependencies into
   `backend/requirements.txt`.
5. Update this document if any versions or SHAs change.

## Remaining risk / next steps

- **No hash verification**: `requirements.txt` pins by version, not by package
  hash. A future improvement is to adopt a lock tool such as `pip-compile`,
  Poetry, or `uv` and commit a generated lockfile with hashes.
- **No complete transitive lock**: Direct dependencies and one compatibility
  dependency are pinned. Other transitive packages can still drift.
- **Docker digest pinning**: Base images are pinned to patch-version tags, not
  immutable SHA digests. The next step is to switch to digest references after
  verifying the digests against Docker Hub or a trusted registry mirror.
- **UI audit freshness**: registry advisories change over time. Keep the CI
  audit gate enabled and review dependency update pull requests promptly.
- **Action update cadence**: SHA-pinned actions do not auto-update. Set up
  Dependabot or a similar tool to open PRs when new action releases are
  available.

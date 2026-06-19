# Dependency integrity plan

This document records the dependency-integrity controls implemented for AI Dev
Readiness Phase 01 and the remaining risk to address in later phases.

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
  - `httpx2==2.4.0`
  - `anyio==4.13.0`

The Docker build, CI workflow, and `make install` all consume this file through
pip's `--constraint` option. This constrains declared dependencies without
pretending to provide a complete cryptographic lockfile.

### 2. Dockerfile base-image pinning

Base images use patch-version tags instead of floating major-version tags:

- `node:20.19.3-slim` for the UI build stage
- `python:3.12.13-slim` for the runtime stage

Digest pinning (`image@sha256:...`) is the next step and is tracked below under
**Remaining risk / next steps**.

### 3. CI action pinning

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
  hash. A future improvement is to adopt a lock tool (e.g., `pip-compile`,
  Poetry, or `uv`) and commit a generated lockfile with hashes.
- **No complete transitive lock**: Direct dependencies and one compatibility
  dependency are pinned. Other transitive packages can still drift.
- **Docker digest pinning**: Base images are pinned to patch-version tags, not
  immutable SHA digests. The next step is to switch to digest references such as
  `node:20.19.3-slim@sha256:...` and `python:3.12.13-slim@sha256:...` after
  verifying the digests against Docker Hub or a trusted registry mirror.
- **Action update cadence**: SHA-pinned actions do not auto-update. Set up
  Dependabot or a similar tool to open PRs when new action releases are
  available.

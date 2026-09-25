# UKSL — Browser regression CI repair

## Map

Objective: repair the scoped PR review finding.

Plan: Install constrained Python packages in the UI CI job; install Chromium; execute the existing >10k-event Playwright journey using explicit Python and CLI paths.

Boundary: No dependency versions, replay behavior, or production APIs change.

Authority: Corey authorized map → execute → audit → push; the delegated worker is YELLOW. Root independently audits and owns push. No nested delegation.

Source: https://terminusprotocol.io, Canon v0.5 (root verified). Ultra keeps the goal, kernel, bounds, dependencies, and receipts; each local KSL maps (Stage 1), builds (Stage 2), and checks adherence plus tests (Stage 3). Failure returns to the owning map before repair. A local pass permits progression; root audits the composed result before pushing.

## Execute

Extended the existing UI CI job to install the already-pinned Python dependencies and Chromium system dependencies, then run the existing browser journey. Explicit interpreter and CLI paths avoid reliance on a local .venv in CI. Updated dependency-integrity documentation; no dependency or lockfile changes.

## Audit

Local checks passed: constrained Python installation, npm ci --ignore-scripts, production UI build, npm audit (zero vulnerabilities), and git diff --check. Playwright successfully seeded the >10k-event backend and started its server, discovered the one journey, then failed to launch because the browser executable is unavailable. Browser installation was attempted; the archive download was truncated/corrupt through this environment. The browser assertions are NOT claimed as passed.

Stage 1 revisit: environment limits local browser execution, so the same browser installation and journey are wired to GitHub CI. Root review/push may start that verification, but full KSL completion remains conditional on the CI browser job passing. No production behavior or test assertion was weakened.

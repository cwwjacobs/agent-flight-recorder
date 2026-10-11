# Proof status — evidence boundary

**Historical result (2026-09-28):** The project author previously reported a successful native `VesperaProof` test on Windows Server 2019 Standard Evaluation build `17763.3650`, including PID change after forced termination and a boot-time continuity check. The original build and its script artifacts are unavailable in this checkout. This report is *historical context only*, not evidence that the new implementation has run on Windows.

**Reconstruction (2026-10-11):** The source package provides a *distinct* test service called `VesperaProofRebuild` to avoid changing any original installation. It has an importable Windows SCM service class, loopback-only HTTP health endpoint, automatic-start and restart-on-failure installation script, crash recovery verifier, and a manual reboot before/after verifier. No Arabic NLP, private data, remote model, or container is involved.

**Checks:**
- [x] Portable Python unit tests: 4/4 passed locally on Linux, 2026-10-11 (`python -m unittest discover -s tests -v`); this is **not** SCM verification.
- [ ] Native service install and health on Windows Server 2019.
- [ ] Recovery test on Windows Server 2019 (new SCM PID + new instance ID).
- [ ] Reboot test on Windows Server 2019 (new OS boot timestamp, running SCM, healthy endpoint).

**Critical:** Do not describe the reconstructed service as Windows Server 2019 validated until Windows-generated evidence files exist and have been inspected. GitHub Actions Windows 2022 unit tests (if green) are not a substitute for Windows Server 2019 SCM/reboot validation.

# Windows Server 2019 — native Python service deployment proof

Small, synthetic reproduction of a **non-container** Windows Service Control Manager (SCM) lifecycle: automatic startup, service process failure recovery, and reboot persistence. This is an engineering proof **only**; it does not contain the client's Arabic API, corpus, models, credentials, or data.

## What is in this repository

- `src/ws19proof/windows_service.py`: importable pywin32 SCM service hosted by `pythonservice.exe` (native Windows service, **not** Task Scheduler, Docker, WSL, or an always-on terminal).
- `src/ws19proof/http_health.py`: localhost-only `GET /healthz` JSON reporting PID, unique instance ID and process start time.
- `scripts/install.ps1`: elevated installer, SCM Automatic startup, restart after unexpected exit (5s delay).
- `scripts/verify.ps1`: captures actual SCM state + HTTP health, force-kill/recovery test, manual reboot comparison.
- `scripts/uninstall.ps1`: stop and remove only the rebuilt test service.
- `tests/test_health.py`: portable HTTP contract tests.
- `PROOF_STATUS.md`: historical-vs-current evidence boundary.

## Prerequisites

1. A disposable **Windows Server 2019 x64** test VM, administrator PowerShell 5.1 or newer.
2. A **machine-wide x64 Python 3.11** install accessible to `LocalSystem`. Avoid Microsoft Store or per-user installs. Internet / offline package mirror access is required for first-time pip installs.
3. Python packaging tooling (`pip`). `install.ps1` installs the source package and pywin32; follow pywin32's service installation troubleshooting if DLL resolution fails.
4. Nothing at TCP port `127.0.0.1:8765` (loopback only; no firewall opening).

**Safety:** Use a disposable VM. Recovery verification deliberately kills the test service process. Reboot is a separate **manual**, operator-controlled step. Do not run the demo against production services or place client data in this repo.

## Build and test (portable Python HTTP contract)

```shell
python -m pip install .
python -m unittest discover -s tests -v
python -m ws19proof.http_health --port 8765
# In another console: http://127.0.0.1:8765/healthz
```

Portable unit tests do **not** validate the Windows SCM lifecycle.

## Windows Server 2019 test run

From an **elevated** PowerShell window in the checkout:

```powershell
# Step 1: Install into the machine-wide Python environment, register with SCM.
.\scripts\install.ps1 -PythonExe "C:\Program Files\Python311\python.exe"

# Step 2: Verify the SCM PID matches the HTTP process PID.
.\scripts\verify.ps1 -Mode Health -EvidencePath .\evidence\health.json

# Step 3: Intentionally kill THIS TEST SERVICE, watch SCM restart it.
.\scripts\verify.ps1 -Mode Recovery -EvidencePath .\evidence\recovery.json

# Step 4: Record an OS boot timestamp and running service BEFORE reboot.
.\scripts\verify.ps1 -Mode BeforeReboot -EvidencePath .\evidence\before-reboot.json

# Step 5: REBOOT THE VM MANUALLY through your normal approved process.
# No script in this repo performs a reboot.

# Step 6: After reconnecting, check OS boot timestamp advanced and service is healthy.
.\scripts\verify.ps1 -Mode AfterReboot -BaselinePath .\evidence\before-reboot.json -EvidencePath .\evidence\after-reboot.json
```

The verifier **fails** if the service isn't Running, isn't Automatic, health doesn't match SCM PID, or SCM recovery is absent. Recovery also requires a changed process PID **and** changed instance ID; reboot requires a later OS boot timestamp and a healthy service after that boot. The files in `evidence/` are intentionally gitignored—inspect and redact them before choosing whether to share.

Cleanup (elevated PowerShell):

```powershell
.\scripts\uninstall.ps1
```

## Verification claims

This is a **reconstruction**, not the original September 2026 test script. It carries a different service name (`VesperaProofRebuild`) to avoid overwriting the original (`VesperaProof`). No contemporary Windows 2019 success is claimed merely by publishing code. See `PROOF_STATUS.md` and genuine generated `evidence/*.json` before representing a Windows result as verified.

The Windows service integration depends on pywin32 and its system-wide post-install steps. See [pywin32's Windows Service guidance](https://github.com/mhammond/pywin32#installation) if the SCM host cannot locate the Python DLLs or import the installed service class.

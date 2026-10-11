"""Native Windows SCM service via pywin32's pythonservice.exe host.

Run installation as administrator:
    python -m ws19proof.windows_service --startup auto install

Use scripts/install.ps1 for complete installation and SCM recovery configuration.
"""

from __future__ import annotations

import threading

import servicemanager
import win32service
import win32serviceutil

from . import DEFAULT_HOST, DEFAULT_PORT, SERVICE_NAME
from .http_health import new_health_server


class VesperaProofRebuild(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = "Vespera Windows 2019 Service Proof (Rebuilt)"
    _svc_description_ = "Synthetic, loopback-only Python HTTP service for Windows SCM lifecycle validation"

    def __init__(self, args: object) -> None:
        super().__init__(args)
        self._server = None
        self._stop_requested = threading.Event()

    def SvcDoRun(self) -> None:  # noqa: N802 (SCM callback API)
        servicemanager.LogInfoMsg(f"{SERVICE_NAME} starting")
        server = new_health_server(host=DEFAULT_HOST, port=DEFAULT_PORT)
        self._server = server
        try:
            if not self._stop_requested.is_set():
                server.serve_forever(poll_interval=0.25)
        finally:
            server.server_close()
            self._server = None
            servicemanager.LogInfoMsg(f"{SERVICE_NAME} stopped")

    def SvcStop(self) -> None:  # noqa: N802 (SCM callback API)
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._stop_requested.set()
        if self._server is not None:
            self._server.shutdown()


if __name__ == "__main__":
    # Explicit import path matters: the SCM host imports the class from site-packages,
    # not from the install shell's current working directory.
    win32serviceutil.HandleCommandLine(
        VesperaProofRebuild,
        serviceClassString="ws19proof.windows_service.VesperaProofRebuild",
    )

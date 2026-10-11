"""Loopback-only synthetic HTTP workload for verifying SCM service lifecycle.

This endpoint does not process Arabic text, call LLMs, or read customer data.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
import uuid
from urllib.parse import urlsplit

from . import DEFAULT_HOST, DEFAULT_PORT, SERVICE_NAME


def new_health_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Create (but do not start) an HTTP server with per-process identity."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("This demonstration must only listen on loopback")

    started_at_utc = datetime.now(timezone.utc).isoformat()
    instance_id = uuid.uuid4().hex

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (stdlib HTTP handler API)
            if urlsplit(self.path).path != "/healthz":
                self.send_error(404, "Not found")
                return
            body = json.dumps(
                {
                    "status": "ok",
                    "service": SERVICE_NAME,
                    "pid": os.getpid(),
                    "instance_id": instance_id,
                    "started_at_utc": started_at_utc,
                },
                separators=(",", ":"),
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            logging.getLogger("ws19proof.http").info("%s: %s", self.address_string(), format % args)

    server = ThreadingHTTPServer((host, port), HealthHandler)
    server.daemon_threads = True
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic loopback HTTP health server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    options = parser.parse_args()
    server = new_health_server(port=options.port)
    print(f"Health endpoint: http://{DEFAULT_HOST}:{server.server_port}/healthz", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

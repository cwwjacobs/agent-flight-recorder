"""`python -m app` — convenience runner for the backend."""

from __future__ import annotations

import argparse

import uvicorn

from app.config import DEFAULT_PORT


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Agent Flight Recorder backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()

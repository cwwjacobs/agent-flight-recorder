"""HTTP client for the AFR backend.

`http_client` injection exists so tests (and embedders) can hand in any
httpx.Client-compatible object — e.g. starlette's TestClient — and exercise
the full SDK path without a network socket.
"""

from __future__ import annotations

from typing import Any

import httpx

from afr.types import resolve_api_token, resolve_api_url


class AFRAPIError(RuntimeError):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"AFR API error {status_code}: {detail}")


class AFRClient:
    def __init__(
        self,
        api_url: str | None = None,
        *,
        http_client: httpx.Client | None = None,
        timeout: float = 10.0,
        token: str | None = None,
    ):
        self._token = resolve_api_token(token)
        if http_client is not None:
            self._http = http_client
            self._owns_http = False
        else:
            headers = {"Authorization": f"Bearer {self._token}"} if self._token else None
            self._http = httpx.Client(
                base_url=resolve_api_url(api_url), timeout=timeout, headers=headers
            )
            self._owns_http = True

    # -- plumbing -----------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._http.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise AFRAPIError(response.status_code, detail)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "AFRClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- meta -----------------------------------------------------------------

    def health(self) -> dict:
        return self._request("GET", "/health")

    # -- runs ---------------------------------------------------------------

    def create_run(self, name: str | None = None, metadata: dict | None = None) -> dict:
        return self._request("POST", "/runs", json={"name": name, "metadata": metadata or {}})

    def get_run(self, run_id: str) -> dict:
        return self._request("GET", f"/runs/{run_id}")

    def list_runs(
        self,
        status: str | None = None,
        tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if tag:
            params["tag"] = tag
        return self._request("GET", "/runs", params=params)

    def end_run(self, run_id: str, status: str = "completed") -> dict:
        return self._request("POST", f"/runs/{run_id}/end", json={"status": status})

    # -- events -------------------------------------------------------------

    def append_event(
        self,
        run_id: str,
        event_type: str,
        name: str | None = None,
        payload: dict | None = None,
        created_at: str | None = None,
    ) -> dict:
        body: dict[str, Any] = {"event_type": event_type, "name": name, "payload": payload or {}}
        if created_at:
            body["created_at"] = created_at
        return self._request("POST", f"/runs/{run_id}/events", json=body)

    def list_events(
        self,
        run_id: str,
        event_type: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if event_type:
            params["event_type"] = event_type
        return self._request("GET", f"/runs/{run_id}/events", params=params)

    # -- checkpoints / state --------------------------------------------------

    def checkpoint(self, run_id: str, label: str | None = None, state: dict | None = None) -> dict:
        return self._request(
            "POST", f"/runs/{run_id}/checkpoint", json={"label": label, "state": state}
        )

    def list_checkpoints(self, run_id: str) -> list[dict]:
        return self._request("GET", f"/runs/{run_id}/checkpoints")

    def state_at(self, run_id: str, checkpoint_id: str, reconstruct: bool = False) -> dict:
        params = {"reconstruct": "true"} if reconstruct else None
        return self._request(
            "GET", f"/runs/{run_id}/state-at/{checkpoint_id}", params=params
        )

    # -- replay ---------------------------------------------------------------

    def replay(self, run_id: str, checkpoint_id: str, mode: str = "dry_run", **extra: Any) -> dict:
        body = {"checkpoint_id": checkpoint_id, "mode": mode, **extra}
        return self._request("POST", f"/runs/{run_id}/replay", json=body)

    # -- premium ----------------------------------------------------------------

    def fork(self, run_id: str, checkpoint_id: str, name: str | None = None) -> dict:
        """Fork a new run from a checkpoint (premium)."""
        return self._request(
            "POST", f"/runs/{run_id}/fork", json={"checkpoint_id": checkpoint_id, "name": name}
        )

    def update_run(
        self,
        run_id: str,
        *,
        name: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> dict:
        """Update run name/tags/notes (premium)."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if tags is not None:
            body["tags"] = tags
        if notes is not None:
            body["notes"] = notes
        return self._request("PATCH", f"/runs/{run_id}", json=body)

    def get_license(self) -> dict:
        return self._request("GET", "/license")

    # -- export ---------------------------------------------------------------

    def export_bundle(self, run_id: str) -> dict:
        """Compose a portable JSON bundle of a full run."""
        return {
            "format": "afr.export.v1",
            "run": self.get_run(run_id),
            "events": self.list_events(run_id, limit=10000),
            "checkpoints": self.list_checkpoints(run_id),
        }

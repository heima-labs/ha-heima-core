"""Shared Home Assistant REST client used by scripts/* live tools."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


class HAApiError(RuntimeError):
    """Raised for non-success HA API calls."""

    def __init__(self, message: str, *, status_code: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


@dataclass
class HAClient:
    """Minimal, dependency-free HA REST API client based on curl."""

    base_url: str
    token: str
    timeout_s: int = 20

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        accept_error: bool = False,
    ) -> tuple[int, Any]:
        base_url = str(self.base_url or "").strip()
        parsed = urlparse(base_url)
        if not base_url or not parsed.scheme or not parsed.netloc:
            raise HAApiError(
                "invalid Home Assistant base URL: pass --ha-url or load scripts/.env first"
            )
        if not str(self.token or "").strip():
            raise HAApiError(
                "missing Home Assistant token: pass --ha-token or load scripts/.env first"
            )

        url = f"{base_url.rstrip('/')}{path}"
        cmd = [
            "curl",
            "-sS",
            "-X",
            method,
            "-H",
            f"Authorization: Bearer {self.token}",
            "-H",
            "Content-Type: application/json",
            url,
            "--max-time",
            str(self.timeout_s),
            "--write-out",
            "\n%{http_code}",
        ]
        if payload is not None:
            cmd.extend(["-d", json.dumps(payload)])
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise HAApiError(f"curl failed for {method} {path}: {(proc.stderr or '').strip()}")

        out = proc.stdout or ""
        if "\n" not in out:
            raise HAApiError(f"unexpected response format for {method} {path}: {out!r}")
        body, status = out.rsplit("\n", 1)
        status_code = int(status.strip())

        parsed: Any = None
        if body.strip():
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = body

        if status_code >= 400 and not accept_error:
            raise HAApiError(
                f"HTTP {status_code} {method} {path}: {body}",
                status_code=status_code,
                body=body,
            )
        return status_code, parsed

    def get(self, path: str, *, accept_error: bool = False) -> Any:
        _, data = self.request("GET", path, accept_error=accept_error)
        return data

    def post(
        self, path: str, payload: dict[str, Any] | None = None, *, accept_error: bool = False
    ) -> Any:
        _, data = self.request("POST", path, payload, accept_error=accept_error)
        return data

    def patch(
        self, path: str, payload: dict[str, Any] | None = None, *, accept_error: bool = False
    ) -> Any:
        _, data = self.request("PATCH", path, payload, accept_error=accept_error)
        return data

    def delete(self, path: str, *, accept_error: bool = True) -> None:
        self.request("DELETE", path, accept_error=accept_error)

    def get_state(self, entity_id: str) -> dict[str, Any]:
        data = self.get(f"/api/states/{entity_id}")
        if not isinstance(data, dict):
            raise HAApiError(f"invalid state payload for {entity_id}: {type(data)}")
        return data

    def state_value(self, entity_id: str) -> str:
        return str(self.get_state(entity_id).get("state"))

    def entity_exists(self, entity_id: str) -> bool:
        status, _ = self.request("GET", f"/api/states/{entity_id}", accept_error=True)
        return status == 200

    def all_states(self) -> list[dict[str, Any]]:
        data = self.get("/api/states")
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def state_from_list(self, entity_id: str) -> dict[str, Any] | None:
        """Find entity state by scanning /api/states list.

        Avoids 404 from GET /api/states/{id} when the entity is temporarily
        absent from the state machine (integration reload, unavailable, etc.).
        Returns None if not found.
        """
        for s in self.all_states():
            if s.get("entity_id") == entity_id:
                return s
        return None

    def call_service(self, domain: str, service: str, data: dict[str, Any] | None = None) -> Any:
        return self.post(f"/api/services/{domain}/{service}", data or {})

    def wait_state(self, entity_id: str, expected: str, timeout_s: int, poll_s: float) -> None:
        deadline = time.time() + timeout_s
        last = "<missing>"
        while time.time() < deadline:
            if self.entity_exists(entity_id):
                last = self.state_value(entity_id)
                if last == expected:
                    return
            time.sleep(poll_s)
        raise HAApiError(f"Timeout waiting for {entity_id}='{expected}', last='{last}'")

    def list_config_entries(self) -> list[dict[str, Any]]:
        variants = [
            "/api/config/config_entries/entry",
            "/api/config/config_entries/entries",
        ]
        last: Exception | None = None
        for path in variants:
            try:
                data = self.get(path)
                if isinstance(data, list):
                    return [item for item in data if isinstance(item, dict)]
            except Exception as err:  # noqa: BLE001
                last = err
        raise HAApiError(f"unable to list config entries: {last}")

    def get_entry(self, entry_id: str) -> dict[str, Any]:
        detail_variants = [
            f"/api/config/config_entries/entry/{entry_id}",
            f"/api/config/config_entries/entries/{entry_id}",
        ]
        for path in detail_variants:
            status, data = self.request("GET", path, accept_error=True)
            if (
                status == 200
                and isinstance(data, dict)
                and str(data.get("entry_id") or "") == entry_id
            ):
                return data
        for entry in self.list_config_entries():
            if str(entry.get("entry_id") or "") == entry_id:
                return entry
        raise HAApiError(f"config entry not found: {entry_id}")

    # ------------------------------------------------------------------
    # Heima
    # ------------------------------------------------------------------

    def find_heima_entry_id(self) -> str:
        for entry in self.list_config_entries():
            if str(entry.get("domain")) == "heima":
                entry_id = str(entry.get("entry_id") or "")
                if entry_id:
                    return entry_id
        raise HAApiError("heima config entry not found")

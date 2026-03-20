"""Minimal Home Assistant WebSocket client — stdlib only (no external deps).

Covers only the operations needed by Heima live test scripts:
- area_registry: list, create
- entity_registry: update (area_id assignment)

Usage:
    with HAWebSocketClient("http://127.0.0.1:8123", token) as ws:
        area_id = ws.get_or_create_area("Test Heima Living")
        ws.assign_entity_to_area("light.foo", area_id)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import time
from typing import Any


class HAWebSocketError(RuntimeError):
    pass


class HAWebSocketClient:
    """Minimal HA WebSocket client built on raw sockets (stdlib only)."""

    def __init__(self, base_url: str, token: str, timeout: int = 20) -> None:
        url = base_url.rstrip("/")
        self._use_ssl = url.startswith("https://")
        host_port = url[8:] if self._use_ssl else url[7:]
        if ":" in host_port:
            host, port_s = host_port.rsplit(":", 1)
            self._port = int(port_s)
        else:
            host = host_port
            self._port = 443 if self._use_ssl else 80
        self._host = host
        self._token = token
        self._timeout = timeout
        self._sock: socket.socket | None = None
        self._msg_id = 1

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "HAWebSocketClient":
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:
        raw = socket.create_connection((self._host, self._port), timeout=self._timeout)
        if self._use_ssl:
            ctx = ssl.create_default_context()
            raw = ctx.wrap_socket(raw, server_hostname=self._host)
        self._sock = raw

        # HTTP upgrade handshake
        key = base64.b64encode(os.urandom(16)).decode()
        self._sock.sendall(
            (
                f"GET /api/websocket HTTP/1.1\r\n"
                f"Host: {self._host}:{self._port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n"
                f"\r\n"
            ).encode()
        )

        # Drain HTTP response headers
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise HAWebSocketError("Connection closed during WebSocket handshake")
            buf += chunk

        # Auth
        msg = self._recv()
        if msg.get("type") != "auth_required":
            raise HAWebSocketError(f"Expected auth_required, got: {msg}")
        self._send_raw({"type": "auth", "access_token": self._token})
        msg = self._recv()
        if msg.get("type") != "auth_ok":
            raise HAWebSocketError(f"HA auth failed: {msg}")

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    # ------------------------------------------------------------------
    # Framing
    # ------------------------------------------------------------------

    def _send_frame(self, *, opcode: int, payload: bytes = b"") -> None:
        assert self._sock
        length = len(payload)
        mask_key = os.urandom(4)
        masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

        header = bytearray([0x80 | (opcode & 0x0F)])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0xFE)
            header += struct.pack(">H", length)
        else:
            header.append(0xFF)
            header += struct.pack(">Q", length)

        self._sock.sendall(bytes(header) + mask_key + masked)

    def _send_raw(self, data: dict[str, Any]) -> None:
        payload = json.dumps(data).encode("utf-8")
        self._send_frame(opcode=0x1, payload=payload)

    def _recv_exactly(self, n: int) -> bytes:
        assert self._sock
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise HAWebSocketError("Connection closed while reading")
            buf += chunk
        return buf

    def _recv_message(self) -> tuple[int, bytes]:
        header = self._recv_exactly(2)
        opcode = header[0] & 0x0F
        masked = bool(header[1] & 0x80)
        length = header[1] & 0x7F

        if length == 126:
            length = struct.unpack(">H", self._recv_exactly(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._recv_exactly(8))[0]

        mask_key = self._recv_exactly(4) if masked else b""
        payload = self._recv_exactly(length)

        if masked:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

        return opcode, payload

    def _recv(self) -> dict[str, Any]:
        while True:
            opcode, payload = self._recv_message()
            if opcode == 0x8:
                raise HAWebSocketError("WebSocket closed by server")
            if opcode == 0x9:
                self._send_frame(opcode=0xA, payload=payload)
                continue
            if opcode == 0xA:
                continue
            if opcode != 0x1:
                continue
            return json.loads(payload.decode("utf-8"))

    # ------------------------------------------------------------------
    # RPC
    # ------------------------------------------------------------------

    def call(self, msg_type: str, **kwargs: Any) -> Any:
        msg_id = self._msg_id
        self._msg_id += 1
        self._send_raw({"id": msg_id, "type": msg_type, **kwargs})
        while True:
            resp = self._recv()
            if resp.get("id") == msg_id:
                if not resp.get("success", True):
                    raise HAWebSocketError(f"WS call {msg_type!r} failed: {resp}")
                return resp.get("result")

    def subscribe_events(self, event_type: str | None = None) -> int:
        msg_id = self._msg_id
        self._msg_id += 1
        payload: dict[str, Any] = {"id": msg_id, "type": "subscribe_events"}
        if event_type:
            payload["event_type"] = event_type
        self._send_raw(payload)
        while True:
            resp = self._recv()
            if resp.get("id") != msg_id:
                continue
            if not resp.get("success", False):
                raise HAWebSocketError(f"WS subscribe_events failed: {resp}")
            return msg_id

    def wait_for_subscription_events(
        self,
        subscription_id: int,
        *,
        timeout_s: float,
    ) -> list[dict[str, Any]]:
        deadline = time.monotonic() + timeout_s
        events: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            assert self._sock
            self._sock.settimeout(remaining)
            try:
                msg = self._recv()
            except TimeoutError as exc:
                raise HAWebSocketError("Timed out waiting for subscription events") from exc
            except socket.timeout as exc:
                raise HAWebSocketError("Timed out waiting for subscription events") from exc
            if msg.get("type") != "event" or msg.get("id") != subscription_id:
                continue
            event = msg.get("event")
            if isinstance(event, dict):
                events.append(event)
        return events

    def wait_for_matching_events(
        self,
        subscription_id: int,
        *,
        timeout_s: float,
        predicate: Any,
    ) -> list[dict[str, Any]]:
        deadline = time.monotonic() + timeout_s
        events: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            assert self._sock
            self._sock.settimeout(remaining)
            try:
                msg = self._recv()
            except TimeoutError as exc:
                raise HAWebSocketError("Timed out waiting for subscription events") from exc
            except socket.timeout as exc:
                raise HAWebSocketError("Timed out waiting for subscription events") from exc
            if msg.get("type") != "event" or msg.get("id") != subscription_id:
                continue
            event = msg.get("event")
            if not isinstance(event, dict):
                continue
            events.append(event)
            if predicate(events):
                return events
        raise HAWebSocketError("Timed out waiting for matching subscription events")

    # ------------------------------------------------------------------
    # Area registry
    # ------------------------------------------------------------------

    def list_areas(self) -> list[dict[str, Any]]:
        result = self.call("config/area_registry/list")
        return result if isinstance(result, list) else []

    def create_area(self, name: str) -> dict[str, Any]:
        result = self.call("config/area_registry/create", name=name)
        if not isinstance(result, dict):
            raise HAWebSocketError(f"Unexpected area create result: {result}")
        return result

    def get_or_create_area(self, name: str) -> str:
        for area in self.list_areas():
            if str(area.get("name", "")).lower() == name.lower():
                return str(area["area_id"])
        return str(self.create_area(name)["area_id"])

    # ------------------------------------------------------------------
    # Entity registry
    # ------------------------------------------------------------------

    def assign_entity_to_area(self, entity_id: str, area_id: str) -> None:
        self.call("config/entity_registry/update", entity_id=entity_id, area_id=area_id)

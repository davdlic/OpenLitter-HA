"""REST + WebSocket client for an OpenLitter device.

The firmware exposes:
  GET  /api/status                — JSON status payload (also broadcast every 500 ms via /ws)
  GET  /api/history               — array of recent cycles
  POST /api/cycle | /api/empty | /api/reset | /api/pause | /api/resume | /api/tare
  POST /api/update?type=firmware  — multipart upload of firmware.bin
  GET  /api/logs                  — plain-text ring buffer

This client wraps those plus a long-lived WebSocket subscription on /ws.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Optional

import aiohttp

from .const import COMMAND_PATHS

_LOGGER = logging.getLogger(__name__)

WS_RECONNECT_BACKOFF_SECONDS = (1, 2, 5, 10, 15, 30)


class OpenLitterApiError(Exception):
    """Raised for any non-recoverable API failure."""


class OpenLitterApi:
    """Async REST + WS client for one OpenLitter device."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int = 80,
    ) -> None:
        self._session = session
        self._host = host
        self._port = port
        self._ws_task: Optional[asyncio.Task[None]] = None
        self._ws_callback: Optional[Callable[[dict[str, Any]], None]] = None
        self._ws_stop_event = asyncio.Event()

    # --- URL helpers ---------------------------------------------------

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    @property
    def ws_url(self) -> str:
        return f"ws://{self._host}:{self._port}/ws"

    # --- REST: status, history, commands ------------------------------

    async def get_status(self, timeout: float = 5.0) -> dict[str, Any]:
        """Fetch the current device status."""
        url = f"{self.base_url}/api/status"
        try:
            async with self._session.get(url, timeout=timeout) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise OpenLitterApiError(f"GET {url}: {err}") from err

    async def get_history(self, timeout: float = 5.0) -> list[dict[str, Any]]:
        url = f"{self.base_url}/api/history"
        try:
            async with self._session.get(url, timeout=timeout) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise OpenLitterApiError(f"GET {url}: {err}") from err

    async def get_logs(self, timeout: float = 5.0) -> str:
        url = f"{self.base_url}/api/logs"
        try:
            async with self._session.get(url, timeout=timeout) as resp:
                resp.raise_for_status()
                return await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise OpenLitterApiError(f"GET {url}: {err}") from err

    async def send_command(self, name: str, timeout: float = 5.0) -> None:
        """Trigger one of the manual commands (cycle, empty, reset, ...)."""
        path = COMMAND_PATHS.get(name)
        if not path:
            raise ValueError(f"Unknown command: {name}")
        url = f"{self.base_url}{path}"
        try:
            async with self._session.post(url, timeout=timeout) as resp:
                resp.raise_for_status()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise OpenLitterApiError(f"POST {url}: {err}") from err

    async def restart(self, timeout: float = 5.0) -> None:
        url = f"{self.base_url}/api/restart"
        try:
            async with self._session.post(url, timeout=timeout) as resp:
                resp.raise_for_status()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise OpenLitterApiError(f"POST {url}: {err}") from err

    # --- REST: firmware / filesystem upload ---------------------------

    async def upload_update(
        self,
        payload: bytes,
        kind: str = "firmware",  # "firmware" or "fs"
        progress_cb: Optional[Callable[[int], None]] = None,
        timeout: float = 120.0,
    ) -> None:
        """POST a .bin to /api/update. The device reboots itself on success."""
        url = f"{self.base_url}/api/update?type={kind}"
        data = aiohttp.FormData()
        data.add_field(
            "update",
            payload,
            filename=f"{kind}.bin",
            content_type="application/octet-stream",
        )
        try:
            async with self._session.post(url, data=data, timeout=timeout) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    raise OpenLitterApiError(
                        f"POST {url}: HTTP {resp.status} {body!r}"
                    )
                json_body = await resp.json(content_type=None)
                if not json_body.get("ok", False):
                    raise OpenLitterApiError(
                        f"Update failed: {json_body.get('error', 'unknown')}"
                    )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise OpenLitterApiError(f"POST {url}: {err}") from err
        if progress_cb:
            progress_cb(100)

    # --- WebSocket: live status + log stream --------------------------

    def start_ws(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Start the long-lived WS subscription. `callback` is invoked
        with each parsed JSON message (`type` field distinguishes status
        vs log frames)."""
        if self._ws_task and not self._ws_task.done():
            return  # already running
        self._ws_callback = callback
        self._ws_stop_event.clear()
        self._ws_task = asyncio.create_task(self._ws_loop())

    async def stop_ws(self) -> None:
        """Cancel the WS task. Safe to call when not started."""
        self._ws_stop_event.set()
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except (asyncio.CancelledError, Exception):  # pragma: no cover
                pass
            self._ws_task = None

    async def _ws_loop(self) -> None:
        attempt = 0
        while not self._ws_stop_event.is_set():
            try:
                async with self._session.ws_connect(
                    self.ws_url,
                    heartbeat=20,
                    timeout=aiohttp.ClientWSTimeout(ws_close=5),  # type: ignore[arg-type]
                ) as ws:
                    attempt = 0
                    _LOGGER.debug("WS connected to %s", self.ws_url)
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            self._dispatch(msg.data)
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
                _LOGGER.debug("WS error (will retry): %s", err)
            except asyncio.CancelledError:
                raise
            if self._ws_stop_event.is_set():
                return
            delay = WS_RECONNECT_BACKOFF_SECONDS[
                min(attempt, len(WS_RECONNECT_BACKOFF_SECONDS) - 1)
            ]
            attempt += 1
            await asyncio.sleep(delay)

    def _dispatch(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return
        if self._ws_callback:
            try:
                self._ws_callback(payload)
            except Exception:  # noqa: BLE001  pragma: no cover
                _LOGGER.exception("WS callback raised")

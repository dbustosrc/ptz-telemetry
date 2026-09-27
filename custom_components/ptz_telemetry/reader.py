"""Reolink position reader; no camera control commands."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from reolink_aio.api import Host
from reolink_aio.enums import ConnectionEnum

from .monitor import Position


class ReolinkPositionReader:
    def __init__(self, host: str, username: str, password: str, port: int, connection: str, channel: int):
        self._api = Host(
            host, username, password, bc_port=port, bc_only=True,
            bc_connection=ConnectionEnum(connection), timeout=5,
        )
        self._channel = channel
        self._lock = asyncio.Lock()

    async def async_open(self) -> Position:
        return await asyncio.wait_for(self.async_read(), timeout=6)

    async def async_read(self) -> Position:
        async with self._lock:
            await asyncio.wait_for(self._api.baichuan.get_ptz_position(self._channel), timeout=5)
            pan = self._api.ptz_pan_position(self._channel)
            tilt = self._api.ptz_tilt_position(self._channel)
            if type(pan) is not int or type(tilt) is not int:
                raise ValueError("camera did not provide pan and tilt")
            return Position(pan, tilt, datetime.now(timezone.utc))

    async def async_close(self) -> None:
        async with self._lock:
            await asyncio.wait_for(self._api.logout(), timeout=3)

"""Small HA-native contract check; skipped by the plain local interpreter."""

from __future__ import annotations

import importlib.util
import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


@unittest.skipUnless(importlib.util.find_spec("homeassistant"), "requires Home Assistant")
class NativeContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_confirmation_does_not_remain_observing(self):
        from ptz_telemetry import CONFIRM_SCHEMA, PTZRuntime
        from ptz_telemetry.monitor import Position
        entered = asyncio.Event()
        async def read():
            entered.set()
            await asyncio.Event().wait()
        runtime = PTZRuntime(SimpleNamespace(async_read=read), Position(0, 0, datetime.now(timezone.utc)))
        task = asyncio.create_task(runtime.confirm(SimpleNamespace(data=CONFIRM_SCHEMA({
            "entity_id": "sensor.position", "pan": 100, "tilt": 200, "destination": "profile_a"}))))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(runtime.status, "cancelled")
        self.assertFalse(runtime.stable_intervals)

    async def test_reader_performs_a_fresh_baichuan_query(self):
        # The native integration must import with the same library as the reader.
        importlib.import_module("homeassistant.components.reolink")
        importlib.import_module("ptz_telemetry.config_flow")
        from ptz_telemetry.reader import ReolinkPositionReader

        reader = ReolinkPositionReader("camera.example", "user", "secret", 9000, "tcp", 0)
        self.addAsyncCleanup(reader.async_close)
        api = reader._api
        with (
            patch.object(api.baichuan, "get_ptz_position", new_callable=AsyncMock) as read_position,
            patch.object(api, "ptz_pan_position", return_value=100),
            patch.object(api, "ptz_tilt_position", return_value=200),
            patch.object(api, "get_host_data", new_callable=AsyncMock) as read_host,
        ):
            position = await reader.async_open()
            read_position.assert_awaited_once_with(0)
            self.assertEqual((position.pan, position.tilt), (100, 200))
            read_host.assert_not_called()

    async def test_response_and_no_camera_commands(self):
        from ptz_telemetry import CONFIRM_SCHEMA, PTZRuntime
        from ptz_telemetry.monitor import Position

        class Reader:
            def __init__(self):
                self.reads = 0

            async def async_read(self):
                self.reads += 1
                return Position(100, 200, datetime.now(timezone.utc))

        reader = Reader()
        runtime = PTZRuntime(reader, Position(0, 0, datetime.now(timezone.utc)))
        data = CONFIRM_SCHEMA({"entity_id": "sensor.ptz_telemetry", "pan": 100, "tilt": 200,
                               "destination": "profile_example"})
        response = await runtime.confirm(SimpleNamespace(data=data))
        self.assertTrue(response["confirmed"])
        self.assertEqual(response["samples"], 2)
        self.assertEqual(reader.reads, 2)
        self.assertEqual(runtime.status, "confirmed")
        self.assertEqual(len(runtime.stable_intervals), 1)
        self.assertEqual(runtime.stable_intervals[0]["destination"], "profile_example")
        self.assertEqual(runtime.stable_intervals[0]["start"], response["settled_since"])


if __name__ == "__main__":
    unittest.main()

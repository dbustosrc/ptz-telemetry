"""Small HA-native contract check; skipped by the plain local interpreter."""

from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


@unittest.skipUnless(importlib.util.find_spec("homeassistant"), "requires Home Assistant")
class NativeContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_reader_performs_a_fresh_baichuan_query(self):
        from ptz_telemetry.reader import ReolinkPositionReader

        with patch("ptz_telemetry.reader.Host") as host_type:
            api = host_type.return_value
            api.baichuan.get_ptz_position = AsyncMock()
            api.ptz_pan_position.return_value = 100
            api.ptz_tilt_position.return_value = 200
            reader = ReolinkPositionReader("camera.example", "user", "secret", 9000, "tcp", 0)
            position = await reader.async_open()
            api.baichuan.get_ptz_position.assert_awaited_once_with(0)
            self.assertEqual((position.pan, position.tilt), (100, 200))
            api.get_host_data.assert_not_called()

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
        data = CONFIRM_SCHEMA({"entity_id": "sensor.ptz_telemetry", "pan": 100, "tilt": 200})
        response = await runtime.confirm(SimpleNamespace(data=data))
        self.assertTrue(response["confirmed"])
        self.assertEqual(response["samples"], 2)
        self.assertEqual(reader.reads, 2)
        self.assertEqual(runtime.status, "confirmed")


if __name__ == "__main__":
    unittest.main()

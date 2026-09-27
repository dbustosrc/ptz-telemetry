"""Deterministic checks for the physical confirmation boundary."""

import asyncio
import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/ptz_telemetry/monitor.py"
SPEC = importlib.util.spec_from_file_location("ptz_monitor", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
Position = MODULE.Position
confirm_destination = MODULE.confirm_destination


class MonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_requires_two_fresh_matching_reads(self):
        readings = iter([(0, 0), (100, 100), (100, 100)])

        async def read():
            return Position(*next(readings), datetime.now(timezone.utc))

        result = await confirm_destination(read, pan=100, tilt=100, tolerance=0, interval=0.1)
        self.assertTrue(result.confirmed)
        self.assertEqual(result.samples, 3)

    async def test_error_and_superseded_fail_closed(self):
        async def failed():
            raise OSError("offline")

        offline = await confirm_destination(failed, pan=1, tilt=1)
        self.assertFalse(offline.confirmed)
        self.assertEqual(offline.reason, "unavailable")
        superseded = await confirm_destination(failed, pan=1, tilt=1, current=lambda: False)
        self.assertEqual(superseded.reason, "superseded")

    async def test_single_match_does_not_confirm(self):
        async def read():
            await asyncio.sleep(0.6)
            return Position(1, 1, datetime.now(timezone.utc))

        result = await confirm_destination(read, pan=1, tilt=1, interval=0.1, timeout=1)
        self.assertFalse(result.confirmed)
        self.assertEqual(result.reason, "timeout")

    async def test_stale_or_repeated_measurement_cannot_confirm(self):
        old = datetime(2020, 1, 1, tzinfo=timezone.utc)

        async def stale():
            return Position(1, 1, old)

        result = await confirm_destination(stale, pan=1, tilt=1)
        self.assertEqual(result.reason, "stale")
        self.assertEqual(result.samples, 0)

        measured_at = None

        async def repeated():
            nonlocal measured_at
            if measured_at is None:
                measured_at = datetime.now(timezone.utc)
            return Position(1, 1, measured_at)

        result = await confirm_destination(repeated, pan=1, tilt=1)
        self.assertEqual(result.reason, "stale")
        self.assertEqual(result.samples, 1)
        self.assertFalse(result.confirmed)

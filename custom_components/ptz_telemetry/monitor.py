"""Bounded destination confirmation independent of Home Assistant and camera brands."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable


@dataclass(frozen=True)
class Position:
    pan: int
    tilt: int
    measured_at: datetime


@dataclass(frozen=True)
class Confirmation:
    confirmed: bool
    reason: str
    position: Position | None
    samples: int


async def confirm_destination(
    read: Callable[[], Awaitable[Position]],
    *,
    pan: int,
    tilt: int,
    tolerance: int = 25,
    interval: float = 0.25,
    timeout: float = 12,
    current: Callable[[], bool] = lambda: True,
    on_read: Callable[[Position], None] = lambda _position: None,
) -> Confirmation:
    """Require two fresh destination readings; never infer arrival from elapsed time."""
    if tolerance < 0 or not 0.1 <= interval <= 2 or not 1 <= timeout <= 60:
        raise ValueError("invalid observation bounds")
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    started_at = datetime.now(timezone.utc)
    stable = samples = 0
    last: Position | None = None
    while current():
        remaining = deadline - loop.time()
        if remaining <= 0:
            return Confirmation(False, "timeout", last, samples)
        try:
            position = await asyncio.wait_for(read(), timeout=min(remaining, 3))
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return Confirmation(False, "timeout", last, samples)
        except Exception:
            return Confirmation(False, "unavailable", last, samples)
        if not current():
            break
        try:
            fresh = started_at <= position.measured_at <= datetime.now(timezone.utc)
            fresh = fresh and (last is None or position.measured_at > last.measured_at)
        except TypeError:
            fresh = False
        if not fresh:
            return Confirmation(False, "stale", last, samples)
        samples += 1
        last = position
        on_read(position)
        stable = stable + 1 if abs(position.pan - pan) <= tolerance and abs(position.tilt - tilt) <= tolerance else 0
        if stable >= 2:
            return Confirmation(True, "confirmed", position, samples)
        await asyncio.sleep(min(interval, max(0, deadline - loop.time())))
    return Confirmation(False, "superseded", last, samples)

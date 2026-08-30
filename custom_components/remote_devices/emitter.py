"""Serialised sending to an emitter entity.

A Broadlink answers one request at a time. Home Assistant's older `remote`
entity has always known this; the 2026.5 `radio_frequency` platform declares
`PARALLEL_UPDATES = 0` and sends straight through. Two presses that overlap
therefore arrive together, the device answers neither, and both fail with
`[Errno -4000] Network timeout` after a full five seconds, which piles up
faster than it drains.

Locks are keyed by emitter entity id, so separate emitters still send in
parallel and only the calls that would actually collide are queued.
"""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components import infrared, radio_frequency
from homeassistant.core import Context, HomeAssistant

# Held after a send, inside the lock, before the next one may start. The device
# acknowledges the request and then spends a few hundred milliseconds actually
# transmitting. HA's remote entity puts 0.4 s between repeats of a command by
# default, so a figure in this range is well precedented.
SETTLE_DELAY_S = 0.3

_LOCKS: dict[str, asyncio.Lock] = {}


def _lock_for(emitter_entity_id: str) -> asyncio.Lock:
    """Return the send lock for one emitter, creating it on first use.

    Safe without a lock of its own: every caller runs on the event loop, and
    there is no await between the lookup and the insert.
    """
    lock = _LOCKS.get(emitter_entity_id)
    if lock is None:
        lock = _LOCKS[emitter_entity_id] = asyncio.Lock()
    return lock


async def async_send_ir(
    hass: HomeAssistant,
    emitter_entity_id: str,
    command: Any,
    context: Context | None = None,
) -> None:
    """Send an IR command, waiting for any send already in flight."""
    async with _lock_for(emitter_entity_id):
        await infrared.async_send_command(hass, emitter_entity_id, command, context=context)
        await asyncio.sleep(SETTLE_DELAY_S)


async def async_send_rf(
    hass: HomeAssistant,
    emitter_entity_id: str,
    command: Any,
    context: Context | None = None,
) -> None:
    """Send an RF command, waiting for any send already in flight."""
    async with _lock_for(emitter_entity_id):
        await radio_frequency.async_send_command(
            hass, emitter_entity_id, command, context=context
        )
        await asyncio.sleep(SETTLE_DELAY_S)

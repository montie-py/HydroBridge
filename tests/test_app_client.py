"""The example app's polling loop must survive a PLC outage instead of exiting."""
import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest

from app.client import poll_forever
from hydrobridge.ports import SourceConnectionError
from hydrobridge.register_map import RegisterField
from hydrobridge.service import RegistersProcessingService

from fakes import FakePublisher, FakeSource


class _StopPolling(Exception):
    """Raised from the patched sleep to end poll_forever after a set number of rounds."""


class FlakySource(FakeSource):
    """Raises SourceConnectionError for the first `failures` reads, then reads normally."""

    def __init__(self, failures):
        super().__init__()
        self.failures = failures

    async def read_block(self):
        if self.failures:
            self.failures -= 1
            raise SourceConnectionError("Could not connect")
        return await super().read_block()


def run_rounds(service, rounds):
    sleep = AsyncMock(side_effect=[None] * (rounds - 1) + [_StopPolling()])
    with patch("app.client.asyncio.sleep", sleep), pytest.raises(_StopPolling):
        asyncio.run(poll_forever(service, interval_sec=7))
    return sleep


def test_plc_outage_is_logged_and_polling_continues(caplog):
    publisher = FakePublisher()
    service = RegistersProcessingService(FlakySource(failures=2), publisher, [RegisterField("level", 0)])

    with caplog.at_level(logging.INFO, logger="app.client"):
        sleep = run_rounds(service, 3)

    assert sleep.await_count == 3
    sleep.assert_awaited_with(7)
    assert len(publisher.sent) == 1
    errors = [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]
    assert errors == ["PLC unreachable (Could not connect); retrying in 7 s, 0 rows pending"] * 2
    assert caplog.records[-1].getMessage() == "Published 1 rows, 0 pending"


def test_other_errors_still_end_the_loop():
    source = FakeSource()
    source.read_block = AsyncMock(side_effect=RuntimeError("bug"))
    service = RegistersProcessingService(source, FakePublisher(), [RegisterField("level", 0)])

    with pytest.raises(RuntimeError, match="bug"):
        asyncio.run(poll_forever(service, interval_sec=0))

import asyncio
import logging

import pytest

from hydrobridge.adapters.modbus import ModbusPLCAdapter
from hydrobridge.ports import SourceConnectionError
from hydrobridge.register_map import RegisterField, RegisterMap
from hydrobridge.service import RegistersProcessingService

from fakes import FakeModbusClient, FakePublisher, FakeSource

REGISTER_MAP = [
    RegisterField("level", address=10, data_type="float32", word_order="high_low", decimals=2),
    RegisterField("state", address=12, data_type="uint16"),
]
# block read from address 10: level = 1.5 (0x3FC00000), state = 3
REGISTERS = [0x3FC0, 0x0000, 3]


def make_service(publisher=None, register_map=REGISTER_MAP, max_pending=20):
    source = FakeSource(REGISTERS, start_address=10, device_id="gw1")
    return RegistersProcessingService(source, publisher or FakePublisher(), register_map, max_pending=max_pending)


def test_run_once_publishes_decoded_values_under_the_map_names():
    publisher = FakePublisher()

    sent = asyncio.run(make_service(publisher).run_once())

    assert sent == 1
    [reading] = publisher.sent
    assert reading.device_id == "gw1"
    assert reading.registers == {"level": 1.5, "state": 3}


def test_accepts_a_register_map_object():
    publisher = FakePublisher()
    asyncio.run(make_service(publisher, register_map=RegisterMap(REGISTER_MAP)).run_once())
    assert publisher.sent[0].registers == {"level": 1.5, "state": 3}


def test_invalid_register_map_fails_at_construction():
    with pytest.raises(ValueError, match="overlaps"):
        make_service(register_map=[RegisterField("a", 0), RegisterField("b", 1)])


# --- logging ---

def test_publish_failure_logs_a_warning(caplog):
    caplog.set_level(logging.DEBUG, logger="hydrobridge")

    asyncio.run(make_service(FakePublisher(online=False)).run_once())

    [record] = caplog.records
    assert (record.name, record.levelno) == ("hydrobridge.service", logging.WARNING)
    assert record.getMessage() == "Publishing failed (Azure unreachable), 1 rows pending"


def test_full_queue_warns_once_per_dropped_reading(caplog):
    caplog.set_level(logging.WARNING, logger="hydrobridge")
    service = make_service(FakePublisher(online=False), max_pending=3)

    async def scenario():
        for _ in range(5):
            await service.run_once()
    asyncio.run(scenario())

    dropped = [r for r in caplog.records if "queue is full" in r.getMessage()]
    assert len(dropped) == 2        # readings 4 and 5 each push out the oldest
    assert dropped[0].getMessage().startswith("Pending queue is full (3 rows), dropping the oldest reading")


def test_successful_publish_logs_only_at_debug(caplog):
    caplog.set_level(logging.DEBUG, logger="hydrobridge")

    asyncio.run(make_service().run_once())

    assert [(r.levelno, r.getMessage()[:30]) for r in caplog.records] == [
        (logging.DEBUG, "Published reading from gw1, re")
    ]


def test_failed_connect_attempts_warn_and_the_final_failure_is_not_logged(caplog):
    caplog.set_level(logging.DEBUG, logger="hydrobridge")
    adapter = ModbusPLCAdapter("127.0.0.1", 5020, "gw1", 0, 2, connect_attempts=3, retry_interval_sec=0,
                               client_factory=lambda: FakeModbusClient(failures=100))

    with pytest.raises(SourceConnectionError):
        asyncio.run(adapter.read_block())

    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.WARNING, "Connection to 127.0.0.1:5020 failed (attempt 1/3): "
                          "[Errno 111] Connection refused; retrying in 0 s"),
        (logging.WARNING, "Connection to 127.0.0.1:5020 failed (attempt 2/3): "
                          "[Errno 111] Connection refused; retrying in 0 s"),
    ]


def test_successful_connect_and_read_are_logged(caplog):
    caplog.set_level(logging.DEBUG, logger="hydrobridge")
    adapter = ModbusPLCAdapter("127.0.0.1", 5020, "gw1", 0, 2, client_factory=lambda: FakeModbusClient())

    asyncio.run(adapter.read_block())

    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.INFO, "Connected to 127.0.0.1:5020"),
        (logging.DEBUG, "Read 2 registers from address 0"),
    ]

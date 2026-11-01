import asyncio
import datetime
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hydrobridge.adapters.azure_iot import AzureIoTHubPublisher
from hydrobridge.adapters.modbus import ModbusPLCAdapter
from hydrobridge.models import PLCReading
from hydrobridge.ports import PublishFailedError, SourceConnectionError
from hydrobridge.register_map import RegisterField
from hydrobridge.service import RegistersProcessingService

from fakes import FakeModbusClient, FakePublisher, FakeSource

REGISTERS = [0] * 52
REGISTER_MAP = [RegisterField("value", address=0)]


def make_plc_adapter(client):
    return ModbusPLCAdapter("127.0.0.1", 5020, "test-device", 0, 52, client_factory=lambda: client)


# --- Modbus server disruption ---

def test_server_down_raises_after_5_attempts_1_sec_apart():
    client = FakeModbusClient(failures=100)
    adapter = make_plc_adapter(client)

    with patch("hydrobridge.adapters.modbus.asyncio.sleep", new=AsyncMock()) as sleep:
        with pytest.raises(SourceConnectionError) as exc_info:
            asyncio.run(adapter.read_block())

    assert client.connect_calls == 5
    assert sleep.await_count == 4  # no sleep after the last attempt
    assert all(call.args == (1,) for call in sleep.await_args_list)
    assert isinstance(exc_info.value.__cause__, ConnectionRefusedError)


def test_server_recovers_within_retry_limit():
    client = FakeModbusClient(failures=4)
    adapter = make_plc_adapter(client)

    with patch("hydrobridge.adapters.modbus.asyncio.sleep", new=AsyncMock()):
        block = asyncio.run(adapter.read_block())

    assert client.connect_calls == 5
    assert block.registers == REGISTERS


def test_server_down_propagates_through_service():
    publisher = FakePublisher()
    service = RegistersProcessingService(make_plc_adapter(FakeModbusClient(failures=100)), publisher, REGISTER_MAP)

    with patch("hydrobridge.adapters.modbus.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(SourceConnectionError):
            asyncio.run(service.run_once())

    assert publisher.sent == []
    assert service.pending_count == 0


# --- PLC dropping mid-session ---
# easymodbus keeps reporting is_connected() after the PLC closes the connection; the read raises
# ModbusTimeoutError and close() raises OSError (FakeModbusClient.drop() reproduces this)

def connected_adapter_whose_plc_dropped():
    client = FakeModbusClient(registers=REGISTERS)
    adapter = ModbusPLCAdapter("127.0.0.1", 5020, "test-device", 0, 52, retry_interval_sec=0, client_factory=lambda: client)
    asyncio.run(adapter.read_block())
    client.drop()
    return adapter, client


def test_plc_drop_reconnects_and_reads_again():
    adapter, client = connected_adapter_whose_plc_dropped()

    block = asyncio.run(adapter.read_block())

    assert block.registers == REGISTERS
    assert client.connect_calls == 2


def test_plc_drop_without_recovery_raises_source_connection_error():
    adapter, client = connected_adapter_whose_plc_dropped()
    client.failures = 100        # every reconnect attempt is refused

    with pytest.raises(SourceConnectionError):
        asyncio.run(adapter.read_block())


def test_plc_drop_replaces_the_dead_client_with_a_new_one():
    # a real easymodbus client can't reconnect after a drop, so the adapter must ask for a new one
    first, second = FakeModbusClient(registers=REGISTERS), FakeModbusClient(registers=[5] * 52)
    clients = iter([first, second])
    adapter = ModbusPLCAdapter("127.0.0.1", 5020, "test-device", 0, 52, client_factory=lambda: next(clients))

    asyncio.run(adapter.read_block())
    first.drop()
    block = asyncio.run(adapter.read_block())

    assert block.registers == [5] * 52
    assert (first.connect_calls, second.connect_calls) == (1, 1)


def test_read_failing_again_after_reconnecting_raises_source_connection_error():
    adapter, client = connected_adapter_whose_plc_dropped()
    client.connect = lambda: None        # connects but stays dropped: the PLC accepts and closes again

    with pytest.raises(SourceConnectionError, match="failed again after reconnecting") as exc_info:
        asyncio.run(adapter.read_block())

    assert type(exc_info.value.__cause__).__name__ == "ModbusTimeoutError"


def test_plc_drop_logs_a_warning(caplog):
    caplog.set_level(logging.WARNING, logger="hydrobridge")
    adapter, _ = connected_adapter_whose_plc_dropped()

    asyncio.run(adapter.read_block())

    assert [r.getMessage() for r in caplog.records] == [
        "Read from 127.0.0.1:5020 failed (ModbusTimeoutError: Connection closed Exception); reconnecting"
    ]


@pytest.mark.parametrize("count", [0, 126])
def test_count_outside_the_modbus_limit_is_rejected(count):
    with pytest.raises(ValueError, match="count must be 1..125"):
        ModbusPLCAdapter("127.0.0.1", 5020, "test-device", 0, count, client_factory=FakeModbusClient)


def test_closing_after_a_plc_drop_does_not_raise():
    adapter, _ = connected_adapter_whose_plc_dropped()

    async def close():
        async with adapter:
            pass
    asyncio.run(close())


# --- Azure disruption ---

def test_azure_down_keeps_rows_pending_and_flushes_in_order_on_recovery():
    publisher = FakePublisher(online=False)
    service = RegistersProcessingService(FakeSource(), publisher, REGISTER_MAP)

    async def scenario():
        for _ in range(3):
            assert await service.run_once() == 0
        assert service.pending_count == 3

        publisher.online = True
        assert await service.run_once() == 4

    asyncio.run(scenario())

    assert service.pending_count == 0
    read_times = [reading.read_at for reading in publisher.sent]
    assert read_times == sorted(read_times)


def test_azure_down_keeps_only_20_most_recent_rows():
    publisher = FakePublisher(online=False)
    service = RegistersProcessingService(FakeSource(), publisher, REGISTER_MAP)

    async def scenario():
        for _ in range(25):
            await service.run_once()
        assert service.pending_count == 20
        queued = list(service._pending)

        publisher.online = True
        await service.run_once()
        return queued

    queued = asyncio.run(scenario())

    # the fresh reading is queued before flushing, so it pushes out the oldest queued row
    assert len(publisher.sent) == 20
    assert publisher.sent[:19] == queued[1:]


def make_azure_publisher(iot_client):
    return AzureIoTHubPublisher(client=iot_client, operation_timeout_sec=0.05)


def make_reading():
    return PLCReading(device_id="test-device", registers={"x": "1.00"}, read_at=datetime.datetime.now())


def test_azure_publisher_works_as_async_context_manager():
    iot_client = MagicMock()
    iot_client.shutdown = AsyncMock()
    publisher = make_azure_publisher(iot_client)

    async def scenario():
        async with publisher as entered:
            assert entered is publisher

    asyncio.run(scenario())

    iot_client.shutdown.assert_awaited_once()


def test_azure_connect_failure_raises_publish_failed():
    iot_client = MagicMock(connected=False)
    iot_client.connect = AsyncMock(side_effect=ConnectionError("network down"))
    publisher = make_azure_publisher(iot_client)

    with pytest.raises(PublishFailedError, match="network down"):
        asyncio.run(publisher.publish(make_reading()))


def test_azure_send_timeout_raises_publish_failed():
    async def hang(_msg):
        await asyncio.sleep(10)

    iot_client = MagicMock(connected=True)
    iot_client.send_message = AsyncMock(side_effect=hang)
    publisher = make_azure_publisher(iot_client)

    with pytest.raises(PublishFailedError, match="TimeoutError"):
        asyncio.run(publisher.publish(make_reading()))

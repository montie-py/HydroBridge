import asyncio
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from business.client.adapters.azure_iot_adapter import AzureIoTHubPublisher
from business.client.adapters.modbus_adapter import ModbusPLCAdapter
from business.client.domain.models import PLCReading
from business.client.domain.ports import PublishFailedError, SourceConnectionError
from business.client.domain.services import RegistersProcessingService

REGISTERS = [0] * 52


class FakeModbusClient:
    """Stands in for easymodbus ModbusClient: connect() fails `failures` times, then succeeds."""

    def __init__(self, failures):
        self.failures = failures
        self.connect_calls = 0
        self.connected = False

    def is_connected(self):
        return self.connected

    def connect(self):
        self.connect_calls += 1
        if self.connect_calls <= self.failures:
            raise ConnectionRefusedError(111, "Connection refused")
        self.connected = True

    def read_holding_registers(self, start_address, count):
        return REGISTERS

    def close(self):
        self.connected = False


def make_plc_adapter(failures):
    adapter = ModbusPLCAdapter("127.0.0.1", 5020, "test-device", 0, 52)
    adapter._client = FakeModbusClient(failures)
    return adapter


class FakeSource:
    async def read_block(self):
        return await make_plc_adapter(failures=0).read_block()


class FakePublisher:
    """Fails while `online` is False, records delivered readings otherwise."""

    def __init__(self, online=True):
        self.online = online
        self.sent: list[PLCReading] = []

    async def publish(self, plc_reading):
        if not self.online:
            raise PublishFailedError("Azure unreachable")
        self.sent.append(plc_reading)


# --- Modbus server disruption ---

def test_server_down_raises_after_5_attempts_1_sec_apart():
    adapter = make_plc_adapter(failures=100)

    with patch("business.client.adapters.modbus_adapter.asyncio.sleep", new=AsyncMock()) as sleep:
        with pytest.raises(SourceConnectionError) as exc_info:
            asyncio.run(adapter.read_block())

    assert adapter._client.connect_calls == 5
    assert sleep.await_count == 4  # no sleep after the last attempt
    assert all(call.args == (1,) for call in sleep.await_args_list)
    assert isinstance(exc_info.value.__cause__, ConnectionRefusedError)


def test_server_recovers_within_retry_limit():
    adapter = make_plc_adapter(failures=4)

    with patch("business.client.adapters.modbus_adapter.asyncio.sleep", new=AsyncMock()):
        block = asyncio.run(adapter.read_block())

    assert adapter._client.connect_calls == 5
    assert block.registers == REGISTERS


def test_server_down_propagates_through_service():
    publisher = FakePublisher()
    service = RegistersProcessingService(make_plc_adapter(failures=100), publisher)

    with patch("business.client.adapters.modbus_adapter.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(SourceConnectionError):
            asyncio.run(service.run_once())

    assert publisher.sent == []
    assert service.pending_count == 0


# --- Azure disruption ---

def test_azure_down_keeps_rows_pending_and_flushes_in_order_on_recovery():
    publisher = FakePublisher(online=False)
    service = RegistersProcessingService(FakeSource(), publisher)

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
    service = RegistersProcessingService(FakeSource(), publisher)

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
    with patch("business.client.adapters.azure_iot_adapter.IoTHubDeviceClient") as client_class:
        client_class.create_from_connection_string.return_value = iot_client
        return AzureIoTHubPublisher("fake-connection-string", operation_timeout_sec=0.05)


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

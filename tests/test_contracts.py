"""What every RegisterSourcePort and TelemetryPublisherPort must do for the service to work.

Each contract is a class of tests with factory methods left to subclasses; a new adapter gets the
same checks by subclassing the contract and implementing the factories.
"""
import asyncio
import datetime
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from hydrobridge.adapters.azure_iot import AzureIoTHubPublisher
from hydrobridge.adapters.modbus import ModbusPLCAdapter
from hydrobridge.models import PLCReading, RawRegisterBlock
from hydrobridge.ports import PublishFailedError, SourceConnectionError
from hydrobridge.register_map import RegisterField, RegisterMap

from fakes import FakeModbusClient


class SourceContract:

    def make_source(self, registers, start_address):
        """A source whose next read returns `registers` read from `start_address`."""
        raise NotImplementedError

    def make_unreachable_source(self):
        """A source whose server can't be reached."""
        raise NotImplementedError

    def test_read_block_returns_a_raw_register_block(self):
        block = asyncio.run(self.make_source([1, 2, 3, 4], start_address=0).read_block())

        assert isinstance(block, RawRegisterBlock)
        assert list(block.registers) == [1, 2, 3, 4]
        assert isinstance(block.read_at, datetime.datetime)
        assert block.device_id

    def test_block_start_address_lets_the_map_find_its_fields(self):
        register_map = RegisterMap([RegisterField("a", 40, "uint16"), RegisterField("b", 41, "uint16")])

        block = asyncio.run(self.make_source([7, 8], start_address=40).read_block())

        assert block.start_address == 40
        assert register_map.decode(block.registers, block.start_address) == {"a": 7, "b": 8}

    def test_unreachable_server_raises_source_connection_error(self):
        # the service and the app only know SourceConnectionError, not the client library's errors
        with pytest.raises(SourceConnectionError):
            asyncio.run(self.make_unreachable_source().read_block())


class PublisherContract:

    def make_publisher(self, failure=None):
        """A publisher whose delivery raises `failure` (any exception) or succeeds if None."""
        raise NotImplementedError

    @staticmethod
    def reading():
        return PLCReading(device_id="gw1", registers={"level": 1.5, "state": 3},
                          read_at=datetime.datetime(2026, 10, 19, 12, 0, 0))

    def test_successful_publish_does_not_raise(self):
        asyncio.run(self.make_publisher().publish(self.reading()))

    @pytest.mark.parametrize("failure", [
        ConnectionError("network down"),
        OSError(101, "Network is unreachable"),
        TimeoutError(),
        RuntimeError("unexpected SDK state"),
    ], ids=lambda exc: type(exc).__name__)
    def test_any_delivery_failure_becomes_publish_failed_error(self, failure):
        # the service keeps the reading queued only on PublishFailedError; anything else would crash it
        with pytest.raises(PublishFailedError):
            asyncio.run(self.make_publisher(failure).publish(self.reading()))


# --- the adapters ---

class TestModbusSource(SourceContract):

    def make_source(self, registers, start_address):
        return ModbusPLCAdapter("127.0.0.1", 5020, "gw1", start_address, len(registers),
                                client_factory=lambda: FakeModbusClient(registers=registers))

    def make_unreachable_source(self):
        return ModbusPLCAdapter("127.0.0.1", 5020, "gw1", 0, 4, retry_interval_sec=0,
                                client_factory=lambda: FakeModbusClient(failures=100))

    def test_reads_the_configured_block(self):
        client = FakeModbusClient(registers=range(10))
        adapter = ModbusPLCAdapter("127.0.0.1", 5020, "gw1", 3, 10, client_factory=lambda: client)

        asyncio.run(adapter.read_block())

        assert client.reads == [(3, 10)]


class TestAzurePublisher(PublisherContract):

    def make_publisher(self, failure=None):
        self.iot_client = MagicMock(connected=True)
        self.iot_client.send_message = AsyncMock(side_effect=failure)
        return AzureIoTHubPublisher(client=self.iot_client, operation_timeout_sec=0.05)

    def test_payload_is_json_with_numbers(self):
        asyncio.run(self.make_publisher().publish(self.reading()))

        [message] = self.iot_client.send_message.await_args.args
        assert (message.content_type, message.content_encoding) == ("application/json", "utf-8")
        assert json.loads(message.data) == {
            "deviceId": "gw1",
            "ts": "2026-10-19T12:00:00",
            "registers": {"level": 1.5, "state": 3},
        }

    def test_connects_first_when_not_connected(self):
        publisher = self.make_publisher()
        self.iot_client.connected = False
        self.iot_client.connect = AsyncMock()

        asyncio.run(publisher.publish(self.reading()))

        self.iot_client.connect.assert_awaited_once()
        self.iot_client.send_message.assert_awaited_once()

    def test_needs_exactly_one_of_connection_string_or_client(self):
        with pytest.raises(ValueError, match="exactly one"):
            AzureIoTHubPublisher()
        with pytest.raises(ValueError, match="exactly one"):
            AzureIoTHubPublisher("HostName=x", client=MagicMock())

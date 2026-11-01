"""Test doubles shared by the test modules (pytest puts tests/ on sys.path, so `from fakes import ...` works)."""
import datetime

from easymodbus.modbus_exception import ModbusTimeoutError

from hydrobridge.models import PLCReading, RawRegisterBlock
from hydrobridge.ports import PublishFailedError, RegisterSourcePort, TelemetryPublisherPort


class FakeModbusClient:
    """Stands in for easymodbus ModbusClient.

    connect() fails `failures` times, then succeeds. After drop() it behaves like easymodbus
    when the PLC closes the connection mid-session (checked against a real socket):
    is_connected() stays True, reads raise ModbusTimeoutError and close() raises OSError,
    until connect() is called again.
    """

    def __init__(self, failures=0, registers=None):
        self.failures = failures
        self.registers = list(registers) if registers is not None else [0] * 52
        self.connect_calls = 0
        self.connected = False
        self.dropped = False
        self.reads : list[tuple[int, int]] = []

    def is_connected(self):
        return self.connected

    def connect(self):
        self.connect_calls += 1
        if self.connect_calls <= self.failures:
            raise ConnectionRefusedError(111, "Connection refused")
        self.connected = True
        self.dropped = False

    def read_holding_registers(self, start_address, count):
        if self.dropped:
            raise ModbusTimeoutError("Connection closed Exception")
        self.reads.append((start_address, count))
        return self.registers[:count]

    def close(self):
        if self.dropped:
            raise OSError(107, "Transport endpoint is not connected")
        self.connected = False

    def drop(self):
        self.dropped = True


class FakeSource(RegisterSourcePort):
    """Returns the same registers on every read."""

    def __init__(self, registers=None, start_address=0, device_id="test-device"):
        self.registers = list(registers) if registers is not None else [0] * 52
        self.start_address = start_address
        self.device_id = device_id

    async def read_block(self):
        return RawRegisterBlock(
            device_id=self.device_id,
            registers=list(self.registers),
            read_at=datetime.datetime.now(),
            start_address=self.start_address
        )


class FakePublisher(TelemetryPublisherPort):
    """Fails while `online` is False, records delivered readings otherwise."""

    def __init__(self, online=True):
        self.online = online
        self.sent : list[PLCReading] = []

    async def publish(self, plc_reading):
        if not self.online:
            raise PublishFailedError("Azure unreachable")
        self.sent.append(plc_reading)

import asyncio
import datetime

from business.client.domain.models import RawRegisterBlock
from business.client.domain.ports import RegisterSourcePort
from easymodbus.modbus_client import ModbusClient

class ModbusPLCAdapter(RegisterSourcePort):
    def __init__(self, host, port, device_id, start_address, count):
        self._client = ModbusClient(host, port)
        self._device_id = device_id
        self._start_address = start_address
        self._count = count

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # easymodbus runs a non-daemon listener thread that keeps the process alive until close()
        if self._client.is_connected():
            await asyncio.to_thread(self._client.close)

    async def read_block(self) -> RawRegisterBlock:
        # easymodbus is blocking, so run its calls in a thread to keep the event loop free
        if not self._client.is_connected():
            await asyncio.to_thread(self._client.connect)

        registers_values_list = await asyncio.to_thread(
            self._client.read_holding_registers, self._start_address, self._count
        )

        return RawRegisterBlock(
            device_id=self._device_id,
            registers=registers_values_list,
            read_at=datetime.datetime.now()
        )

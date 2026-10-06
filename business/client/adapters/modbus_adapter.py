import asyncio
import datetime

from business.client.domain.models import RawRegisterBlock
from business.client.domain.ports import RegisterSourcePort, SourceConnectionError
from easymodbus.modbus_client import ModbusClient

class ModbusPLCAdapter(RegisterSourcePort):
    def __init__(self, host, port, device_id, start_address, count,
                 connect_attempts : int = 5, retry_interval_sec : float = 1):
        self._host = host
        self._port = port
        self._connect_attempts = connect_attempts
        self._retry_interval_sec = retry_interval_sec
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
            await self._connect()

        registers_values_list = await asyncio.to_thread(
            self._client.read_holding_registers, self._start_address, self._count
        )

        return RawRegisterBlock(
            device_id=self._device_id,
            registers=registers_values_list,
            read_at=datetime.datetime.now()
        )

    async def _connect(self):
        for attempt in range(1, self._connect_attempts + 1):
            try:
                await asyncio.to_thread(self._client.connect)
                return
            except OSError as exc:
                print(f"Connection to {self._host}:{self._port} failed "
                      f"(attempt {attempt}/{self._connect_attempts}): {exc}")
                if attempt < self._connect_attempts:
                    await asyncio.sleep(self._retry_interval_sec)
                else:
                    raise SourceConnectionError(
                        f"Could not connect to {self._host}:{self._port} "
                        f"after {self._connect_attempts} attempts"
                    ) from exc

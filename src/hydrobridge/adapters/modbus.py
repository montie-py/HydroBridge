import asyncio
import datetime
import logging

from hydrobridge.models import RawRegisterBlock
from hydrobridge.ports import RegisterSourcePort, SourceConnectionError
from easymodbus.modbus_client import ModbusClient

logger = logging.getLogger(__name__)


class ModbusPLCAdapter(RegisterSourcePort):
    def __init__(self, host, port, device_id, start_address, count,
                 connect_attempts : int = 5, retry_interval_sec : float = 1,
                 *, client : ModbusClient | None = None):
        """``client`` replaces the ModbusClient(host, port) the adapter would create;
        it needs connect(), close(), is_connected() and read_holding_registers(start, count)."""
        self._host = host
        self._port = port
        self._connect_attempts = connect_attempts
        self._retry_interval_sec = retry_interval_sec
        self._client = client if client is not None else ModbusClient(host, port)
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
        logger.debug("Read %d registers from address %d", len(registers_values_list), self._start_address)

        return RawRegisterBlock(
            device_id=self._device_id,
            registers=registers_values_list,
            read_at=datetime.datetime.now(),
            start_address=self._start_address
        )

    async def _connect(self):
        for attempt in range(1, self._connect_attempts + 1):
            try:
                await asyncio.to_thread(self._client.connect)
                logger.info("Connected to %s:%s", self._host, self._port)
                return
            except OSError as exc:
                if attempt < self._connect_attempts:
                    logger.warning("Connection to %s:%s failed (attempt %d/%d): %s; retrying in %s s",
                                   self._host, self._port, attempt, self._connect_attempts, exc,
                                   self._retry_interval_sec)
                    await asyncio.sleep(self._retry_interval_sec)
                else:
                    # not logged: the caller gets the error, with this attempt's exception as __cause__
                    raise SourceConnectionError(
                        f"Could not connect to {self._host}:{self._port} "
                        f"after {self._connect_attempts} attempts"
                    ) from exc

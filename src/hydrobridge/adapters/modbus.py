import asyncio
import datetime
import logging
from typing import Callable

from hydrobridge.models import RawRegisterBlock
from hydrobridge.ports import RegisterSourcePort, SourceConnectionError

try:
    from easymodbus.modbus_client import ModbusClient
    from easymodbus.modbus_exception import ModbusException
except ImportError as exc:
    raise ImportError('hydrobridge.adapters.modbus needs easymodbus: pip install "hydrobridge[modbus]"') from exc

logger = logging.getLogger(__name__)

# easymodbus rejects a holding-register read of more than 125 registers (the Modbus limit)
MAX_REGISTERS_PER_READ = 125

# what easymodbus raises when the connection is gone: its own exceptions (ModbusTimeoutError on a closed
# connection) and socket errors
_CONNECTION_ERRORS = (ModbusException, OSError)


class ModbusPLCAdapter(RegisterSourcePort):
    def __init__(self, host, port, device_id, start_address, count,
                 connect_attempts : int = 5, retry_interval_sec : float = 1,
                 *, client_factory : Callable[[], ModbusClient] | None = None):
        """``client_factory`` returns a new client in place of ModbusClient(host, port); it needs
        connect(), close(), is_connected() and read_holding_registers(start, count).

        A factory rather than a client because an easymodbus client can't reconnect after the PLC drops
        the connection, so the adapter replaces it with a new one.
        """
        if not 1 <= count <= MAX_REGISTERS_PER_READ:
            raise ValueError(f"count must be 1..{MAX_REGISTERS_PER_READ} registers, got {count}")
        self._host = host
        self._port = port
        self._connect_attempts = connect_attempts
        self._retry_interval_sec = retry_interval_sec
        self._client_factory = client_factory if client_factory is not None else lambda: ModbusClient(host, port)
        self._client = self._client_factory()
        self._device_id = device_id
        self._start_address = start_address
        self._count = count

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # easymodbus runs a non-daemon listener thread that keeps the process alive until close()
        if self._client.is_connected():
            await self._close_quietly()

    async def read_block(self) -> RawRegisterBlock:
        # easymodbus is blocking, so run its calls in a thread to keep the event loop free
        if not self._client.is_connected():
            await self._connect()

        try:
            registers_values_list = await self._read()
        except _CONNECTION_ERRORS as exc:
            # easymodbus still reports is_connected() after the PLC closes the connection, so a failed
            # read is the only sign of a drop: start over with a new client and read once more
            logger.warning("Read from %s:%s failed (%s: %s); reconnecting",
                           self._host, self._port, type(exc).__name__, exc)
            await self._close_quietly()
            self._client = self._client_factory()
            await self._connect()
            try:
                registers_values_list = await self._read()
            except _CONNECTION_ERRORS as retry_exc:
                await self._close_quietly()
                raise SourceConnectionError(
                    f"Read from {self._host}:{self._port} failed again after reconnecting"
                ) from retry_exc

        logger.debug("Read %d registers from address %d", len(registers_values_list), self._start_address)

        return RawRegisterBlock(
            device_id=self._device_id,
            registers=registers_values_list,
            read_at=datetime.datetime.now(),
            start_address=self._start_address
        )

    async def _read(self):
        return await asyncio.to_thread(self._client.read_holding_registers, self._start_address, self._count)

    async def _close_quietly(self):
        # on a dropped connection easymodbus' close() raises OSError (socket not connected); its listener
        # thread still stops, and the client is replaced on the next connect anyway
        try:
            await asyncio.to_thread(self._client.close)
        except OSError as exc:
            logger.debug("Closing the connection to %s:%s failed: %s", self._host, self._port, exc)

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

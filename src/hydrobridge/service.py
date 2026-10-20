import logging
import struct
from collections import deque
from typing import Iterable

from hydrobridge.models import PLCReading
from hydrobridge.register_map import RegisterField, RegisterMap
from hydrobridge.ports import PublishFailedError, TelemetryPublisherPort, RegisterSourcePort

logger = logging.getLogger(__name__)


def registers_to_float(low_word : int, high_word : int) -> float:
    """Decode a 32-bit float stored low word first (easymodbus RegisterOrder.lowHigh)."""
    return struct.unpack('<f', struct.pack('<HH', low_word, high_word))[0]


class RegistersProcessingService:
    def __init__(
            self,
            source : RegisterSourcePort,
            publisher : TelemetryPublisherPort,
            register_map : Iterable[RegisterField],
            max_pending : int = 20
    ):
        # wrapping validates the fields: unique names, no overlapping registers
        self._register_map : RegisterMap = (
            register_map if isinstance(register_map, RegisterMap) else RegisterMap(register_map)
        )
        self._source : RegisterSourcePort = source
        self._publisher : TelemetryPublisherPort = publisher
        # rows not yet delivered to Azure; when full, appending drops the oldest row
        self._pending : deque[PLCReading] = deque(maxlen=max_pending)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    async def run_once(self) -> int:
        """Read one row from the PLC, queue it and try to deliver the whole queue.

        Returns the number of rows sent; on connection failure the unsent rows stay queued for the next call.
        """
        raw_register_block_instance = await self._source.read_block()

        plc_reading = PLCReading(
            device_id=raw_register_block_instance.device_id,
            registers=self._register_map.decode(
                raw_register_block_instance.registers,
                raw_register_block_instance.start_address
            ),
            read_at=raw_register_block_instance.read_at
        )

        if len(self._pending) == self._pending.maxlen:
            logger.warning("Pending queue is full (%d rows), dropping the oldest reading, read at %s",
                           self._pending.maxlen, self._pending[0].read_at.isoformat())
        self._pending.append(plc_reading)
        return await self._flush_pending()

    async def _flush_pending(self) -> int:
        sent = 0
        while self._pending:
            try:
                await self._publisher.publish(self._pending[0])
            except PublishFailedError as exc:
                logger.warning("Publishing failed (%s), %d rows pending", exc, len(self._pending))
                break
            published = self._pending.popleft()
            logger.debug("Published reading from %s, read at %s",
                         published.device_id, published.read_at.isoformat())
            sent += 1
        return sent

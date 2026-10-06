from collections import deque

import easymodbus.modbus_client as modbus_client_class_file

from business.client.adapters.azure_iot_adapter import AzureIoTHubPublisher
from business.client.adapters.modbus_adapter import ModbusPLCAdapter
from business.client.domain.models import PLCReading
from business.client.domain.ports import PublishFailedError


class RegistersProcessingService:
    __columns = ["worker_inlet_conductivity", "worker_inlet_temperature", "worker_pre_pump_pressure",
               "worker_post_pump_pressure", "worker_product_pressure", "Worker Product Flow (GPM)",
               "Worker Product Temperature (C)", "Worker Waste Flow (GPM)", "Worker Recycle Flow (GPM)",
               "Worker Product Conductivity (uS)", "Polisher Inlet Conductivity (uS)", "Polisher Inlet Temperature (C)",
               "Polisher Pre Pump Pressure (PSI)", "Polisher Post Pump Pressure (PSI)",
               "Polisher Product Pressure (PSI)", "Polisher Product Flow (GPM)", "Polisher Product Temperature (C)",
               "Polisher Waste Flow (GPM)", "Polisher Recycle Flow (GPM)", "Polisher Product Conductivity (uS)",
               "System Product Conductivity (uS)", "-Reserved1-", "-Reserved2-", "-Reserved3-",
               "Worker Inlet Flow (GPM, calc)", "Polisher Inlet Flow (GPM, calc)"
               ]

    def __init__(
            self,
            source : ModbusPLCAdapter,
            publisher : AzureIoTHubPublisher,
            max_pending : int = 20
    ):
        self._source : ModbusPLCAdapter = source
        self._publisher : AzureIoTHubPublisher = publisher
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

        parsed_registers_block = self._parse(raw_register_block_instance.registers)
        headed_registers_block = self._attach_headers(parsed_registers_block)

        plc_reading = PLCReading(
            device_id=raw_register_block_instance.device_id,
            registers=headed_registers_block,
            read_at=raw_register_block_instance.read_at
        )

        self._pending.append(plc_reading)
        return await self._flush_pending()

    async def _flush_pending(self) -> int:
        sent = 0
        while self._pending:
            try:
                await self._publisher.publish(self._pending[0])
            except PublishFailedError as exc:
                print(f"Publishing failed ({exc}), {len(self._pending)} rows pending")
                break
            self._pending.popleft()
            sent += 1
        return sent

    def _attach_headers(self, parsed_registers_block):
        return {self.__columns[k]: v for k, v in enumerate(parsed_registers_block)}

    def _parse(self, registers_block):
        registers_floats = []
        registers_count = 0
        while registers_count < 52:
            converted_value = modbus_client_class_file.convert_registers_to_float(
                [registers_block[registers_count],
                 registers_block[registers_count + 1]]
            )[0]

            registers_floats.append(f'{converted_value:.2f}')
            registers_count += 2

        return registers_floats

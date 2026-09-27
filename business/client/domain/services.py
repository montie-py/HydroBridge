from typing import Mapping

import easymodbus.modbus_client as modbus_client_class_file

from business.client.adapters.azure_iot_adapter import AzureIoTHubPublisher
from business.client.adapters.modbus_adapter import ModbusPLCAdapter
from business.client.domain.models import PLCReading


class RegistersProcessingService:
    __columns = ["worker_inlet_conductivity", "worker_inlet_temperature", "worker_pre_pump_pressure",
               "worker_post_pump_pressure", "worker_product_pressure", "Worker Product Flow (GPM)",
               "Worker Product Temperature (C)", "Worker Waste Flow (GPM)", "Worker Recycle Flow (GPM)",
               "Worker Product Conductivity (uS)", "Polisher Inlet Conductivity (uS)", "Polisher Inlet Temperature (C)",
               "Polisher Pre Pump Pressure (PSI)", "Polisher Post Pump Pressure (PSI)",
               "Polisher Product Pressure (PSI)", "Polisher Product Flow (GPM)", "Polisher Product Temperature (C)",
               "Polisher Waste Flow (GPM)", "Polisher Recycle Flow (GPM)", "Polisher Product Conductivity (uS)",
               "System Product Conductivity (uS)", "-Reserved-", "-Reserved-", "-Reserved-",
               "Worker Inlet Flow (GPM, calc)", "Polisher Inlet Flow (GPM, calc)"
               ]

    def __init__(
            self,
            source : ModbusPLCAdapter,
            publisher : AzureIoTHubPublisher
    ):
        self._source : ModbusPLCAdapter = source
        self._publisher : AzureIoTHubPublisher = publisher

    async def run_once(self) -> Mapping[str, int]:
        raw_register_block_instance = await self._source.read_block()

        parsed_registers_block = self._parse(raw_register_block_instance.registers)
        headed_registers_block = self._attach_headers(parsed_registers_block)

        plc_reading = PLCReading(
            device_id=raw_register_block_instance.device_id,
            registers=headed_registers_block,
            read_at=raw_register_block_instance.read_at
        )

        return await self._publisher.publish(plc_reading)

    def _attach_headers(self, parsed_registers_block):
        return {self.__columns[k]: v for k, v in enumerate(parsed_registers_block)}

    def _parse(self, registers_block):
        registers_floats = []
        registers_count = 0
        while registers_count < 52:
            registers_floats.append(modbus_client_class_file.convert_registers_to_float(
                [registers_block[registers_count],
                 registers_block[registers_count + 1]]))
            registers_count += 2

        return registers_floats

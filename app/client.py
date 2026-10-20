from hydrobridge.adapters.azure_iot import AzureIoTHubPublisher
from hydrobridge.adapters.modbus import ModbusPLCAdapter
from hydrobridge import RegistersProcessingService
from app.runnable import Runnable
from app.config.devices_config import get_config
import asyncio
from project_settings import IOTHUB_DEVICE_CONNECTION_STRING

class Client(Runnable):
    def __init__(self):
        self._config = get_config()

    async def run(self):
        await self.parse_server()

    async def parse_server(self):
        register_map = self._config.devices_configuration[0].build_register_map()

        async with ModbusPLCAdapter(
            host="127.0.0.1",
            port=5020,
            device_id="hydrobridge-gw1",
            start_address=register_map.start_address,
            count=register_map.register_count
        ) as plc_adapter, AzureIoTHubPublisher(
            connection_string=IOTHUB_DEVICE_CONNECTION_STRING
        ) as azure_publisher:
            service = RegistersProcessingService(plc_adapter, azure_publisher, register_map)

            while True:
                sent = await service.run_once()
                print(f"Published {sent} rows, {service.pending_count} pending")
                await asyncio.sleep(3)



from business.client.adapters.azure_iot_adapter import AzureIoTHubPublisher
from business.client.adapters.modbus_adapter import ModbusPLCAdapter
from business.client.domain.services import RegistersProcessingService
from business.runnable import Runnable
from config.devices_config import get_config
import asyncio
from project_settings import IOTHUB_DEVICE_CONNECTION_STRING

class Client(Runnable):
    def __init__(self):
        __config = get_config()

    async def run(self):
        await self.parse_server()

    async def parse_server(self):
        async with ModbusPLCAdapter(
            host="127.0.0.1",
            port=5020,
            device_id="hydrobridge-gw1",
            start_address=0,
            count=52
        ) as plc_adapter, AzureIoTHubPublisher(
            connection_string=IOTHUB_DEVICE_CONNECTION_STRING
        ) as azure_publisher:
            service = RegistersProcessingService(plc_adapter, azure_publisher)

            while True:
                readings = await service.run_once()
                print(f"Published {len(readings)} readings")
                await asyncio.sleep(3)



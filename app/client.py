from hydrobridge.adapters.azure_iot import AzureIoTHubPublisher
from hydrobridge.adapters.modbus import ModbusPLCAdapter
from hydrobridge import RegistersProcessingService
from hydrobridge.ports import SourceConnectionError
from app.runnable import Runnable
from app.config.devices_config import get_config
import asyncio
import logging

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 3


async def poll_forever(service : RegistersProcessingService, interval_sec : float = POLL_INTERVAL_SEC):
    """Run the service every ``interval_sec``; a PLC outage is logged and retried instead of ending the loop.

    Unsent rows stay queued in the service, so they are delivered once the PLC and Azure are back.
    """
    while True:
        try:
            sent = await service.run_once()
        except SourceConnectionError as exc:
            logger.error("PLC unreachable (%s); retrying in %s s, %d rows pending",
                         exc, interval_sec, service.pending_count)
        else:
            logger.info("Published %d rows, %d pending", sent, service.pending_count)
        await asyncio.sleep(interval_sec)


class Client(Runnable):
    def __init__(self):
        self._config = get_config()

    async def run(self):
        await self.parse_server()

    async def parse_server(self):
        # imported here so the module imports without project_settings.py (gitignored, holds the secret)
        from project_settings import IOTHUB_DEVICE_CONNECTION_STRING

        device = self._config.devices_configuration[0]
        register_map = device.build_register_map()

        async with ModbusPLCAdapter(
            host=device.device_ip,
            port=device.device_port,
            device_id="hydrobridge-gw1",
            start_address=register_map.start_address,
            count=register_map.register_count
        ) as plc_adapter, AzureIoTHubPublisher(
            connection_string=IOTHUB_DEVICE_CONNECTION_STRING
        ) as azure_publisher:
            service = RegistersProcessingService(plc_adapter, azure_publisher, register_map)
            await poll_forever(service)

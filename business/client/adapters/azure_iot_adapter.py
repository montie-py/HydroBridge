import asyncio
import json

from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import Message

from business.client.domain.models import PLCReading
from business.client.domain.ports import TelemetryPublisherPort, PublishFailedError


class AzureIoTHubPublisher(TelemetryPublisherPort):

    def __init__(self, connection_string : str, operation_timeout_sec : float = 10):
        self._client = IoTHubDeviceClient.create_from_connection_string(
            connection_string, connection_retry=False
        )
        self._operation_timeout_sec = operation_timeout_sec

    async def __aexit__(self, exc_type, exc, tb):
        await self._client.shutdown()

    async def publish(self, plc_reading : PLCReading):
        payload = {
            "deviceId" : plc_reading.device_id,
            "ts" : plc_reading.read_at.isoformat(),
            "registers" : plc_reading.registers
        }
        msg = Message(json.dumps(payload))
        msg.content_type = "application/json"
        msg.content_encoding = "utf-8"

        try:
            if not self._client.connected:
                await asyncio.wait_for(self._client.connect(), self._operation_timeout_sec)
            await asyncio.wait_for(self._client.send_message(msg), self._operation_timeout_sec)
        except Exception as exc:
            raise PublishFailedError(str(exc) or type(exc).__name__) from exc

        return plc_reading.registers

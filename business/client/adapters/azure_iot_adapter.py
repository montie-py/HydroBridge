from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import Message
import json

from business.client.domain.models import PLCReading
from business.client.domain.ports import TelemetryPublisherPort


class AzureIoTHubPublisher(TelemetryPublisherPort):

    def __init__(self, connection_string : str):
        self._client = IoTHubDeviceClient.create_from_connection_string(connection_string)

    async def __aenter__(self):
        await self._client.connect()
        return self

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
        await self._client.send_message(msg)
        return plc_reading.registers

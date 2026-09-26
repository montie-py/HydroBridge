from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import Message
import time, json
from business.client.domain.ports import TelemetryPublisherPort


class AzureIoTHubPublisher(TelemetryPublisherPort):

    def __init__(self, connection_string):
        self._client = IoTHubDeviceClient.create_from_connection_string(connection_string)
        self._client.connect()


    async def publish(self, plc_reading):
        payload = {
            "deviceId" : plc_reading.device_id,
            "ts" : plc_reading.read_at,
            "registers" : plc_reading.registers
        }
        msg = Message(json.dumps(payload))
        msg.content_type = "application/json"
        msg.content_encoding = "utf-8"
        await self._client.send_message(msg)

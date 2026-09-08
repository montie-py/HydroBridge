from business.runnable import Runnable
from config.devices_config import get_config
from easymodbus.modbus_client import ModbusClient
import asyncio, time, json
import easymodbus.modbus_client as modbus_client
from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import Message
from project_settings import IOTHUB_DEVICE_CONNECTION_STRING

class Client(Runnable):
    def __init__(self):
        __config = get_config()

    async def run(self):
        await self._initializeAzureConnection()
        await self.parse_server()

    async def parse_server(self):
        modbus_client_class_instance = ModbusClient("127.0.0.1", 5020)
        modbus_client_class_instance.connect()
        try:
            while True:
                registers_values_list = modbus_client_class_instance.read_holding_registers(0, 52)
                registers_floats = []
                registers_count = 0
                while registers_count < 52:
                    registers_floats.append(modbus_client.convert_registers_to_float(
                        [registers_values_list[registers_count], registers_values_list[registers_count + 1]]))
                    registers_count += 2
                await self._send_to_azure(registers_floats)
                print(registers_floats)
                time.sleep(3)
        finally:
            await self._azure_iot_client.disconnect()

    async def _initializeAzureConnection(self):
        self._azure_iot_client = IoTHubDeviceClient.create_from_connection_string(IOTHUB_DEVICE_CONNECTION_STRING)
        await self._azure_iot_client.connect()

    async def _send_to_azure(self, registers_data_row):
        payload = {
            "deviceId" : "hydrobridge-gw1",
            "ts" : time.time(),
            "registers" : registers_data_row
        }
        msg = Message(json.dumps(payload))
        msg.content_type = "application/json"
        msg.content_encoding = "utf-8"
        await self._azure_iot_client.send_message(msg)
        # await asyncio.sleep(2)

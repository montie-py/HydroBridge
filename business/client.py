from business.runnable import Runnable
from config.devices_config import get_config
from easymodbus.modbus_client import ModbusClient

class Client(Runnable):
    def __init__(self):
        __config = get_config()

    def run(self):
        pass

    def parse_server(self):
        client = ModbusClient("127.0.0.1", 502)
        client.connect()
        while True:
            registers_list = client.read_holding_registers(52)
            #todo transform registers back to int values


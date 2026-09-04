from business.runnable import Runnable
from config.devices_config import get_config
from easymodbus.modbus_client import ModbusClient
from time import sleep
import easymodbus.modbus_client as modbus_client

class Client(Runnable):
    def __init__(self):
        __config = get_config()

    def run(self):
        self.parse_server()

    def parse_server(self):
        client = ModbusClient("127.0.0.1", 5020)
        client.connect()
        while True:
            registers_values_list = client.read_holding_registers(0, 52)
            registers_ints = []
            registers_count = 0
            while registers_count < 52:
                registers_ints.append(modbus_client.convert_registers_to_float([registers_values_list[registers_count], registers_values_list[registers_count+1]]))
                registers_count += 2
            print(registers_ints)
            sleep(3)


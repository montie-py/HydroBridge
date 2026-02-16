from pymodbus.client import ModbusTcpClient
import time

client = ModbusTcpClient("127.0.0.1", port=1502)

while True:
    try:
        if not client.connected:
            client.connect()
        result = client.read_holding_registers(0, count=50)
        if not result.isError():
            print(result.registers)
        else:
            print("Read error:", result)
        time.sleep(5)

    except Exception as e:
        print("Exception: ", e)

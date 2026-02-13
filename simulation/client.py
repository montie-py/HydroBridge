from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("127.0.0.1", port=1502)
client.connect()
print(client.read_holding_registers(0, count=10))

import datetime

from business.client.domain.models import RawRegisterBlock
from business.client.domain.ports import RegisterSourcePort
from easymodbus.modbus_client import ModbusClient

class ModbusPLCAdapter(RegisterSourcePort):
    def __init__(self, host, port, device_id, start_address, count):
        self._client = ModbusClient(host, port)
        self._device_id = device_id
        self._start_address = start_address
        self._count = count

    async def read_block(self) -> RawRegisterBlock:
        if not self._client.is_connected():
            self._client.connect()

        registers_values_list = await ModbusClient.read_holding_registers(self._start_address, self._count)

        return RawRegisterBlock(
            device_id=self._device_id,
            registers=registers_values_list,
            read_at=datetime.datetime.now()
        )
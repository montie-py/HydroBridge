from main import decode_by_chunks, decode_registers
from pymodbus.client import ModbusTcpClient


def test_decode_by_chunks():
    registers = list(range(6))
    rules = "0:uint16,1-2:float32,3:int16,4-5:float32"
    decoded_registers = decode_by_chunks(registers, rules)
    decoded_registers_keys = list(decoded_registers.keys())
    assert isinstance(decoded_registers_keys[0], int)
    assert isinstance(decoded_registers_keys[1], tuple)
    assert isinstance(decoded_registers_keys[2], int)
    assert isinstance(decoded_registers_keys[3], tuple)

def test_decode_registers():
    registers = list(range(6))
    rules = "0:uint16,1-2:float32,3:int16,4-5:float32"
    decoded_registers = decode_registers(registers, rules)
    for register in decoded_registers[::2]:
        assert isinstance(register, int)
    for register in decoded_registers[1::2]:
        assert isinstance(register, float)
    assert 1 ==1



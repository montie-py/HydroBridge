from pymodbus.client import ModbusTcpClient

def raw_tcp_parse_register(
        ip: str,
        port: int,
        function_code: int = 0x03,
        start_address_from: int = 0x03,
        start_address_to: int = 0xE8,
        quantity_from: int = 0x00,
        quantity_to: int = 0x2F
) -> list[int]:
    import socket

    # Modbus TCP request: Read 1 register starting at 0
    request = bytes([
        0x00, 0x01,  # Transaction ID
        0x00, 0x00,  # Protocol ID
        0x00, 0x06,  # Length
        0x01,  # Unit ID
        function_code,  # Function code (Read Holding Registers)
        start_address_from, start_address_to,  # Start address = 1000 (0x03E8)
        quantity_from, quantity_to  # Quantity = 47 (0x002F)
    ])

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, port))
    sock.sendall(request)

    response = sock.recv(256)

    sock.close()

    return list(response)


def pymodbus_parse_register(
        ip: str,
        port: int,
        address: int,
        count: int
) -> list[int]:

    client = ModbusTcpClient(ip, port=port)
    client.connect()

    result = client.read_holding_registers(address=address, count=count, device_id=1)

    client.close()

    return result.registers


def decode_by_chunks(registers_output: list, decode_schema: str) -> dict:
    rules_dict = {}
    chunks_rules = decode_schema.split(',')
    for chunk_rule in chunks_rules:
        chunk_rule_split = chunk_rule.split(':')
        rule_type = chunk_rule_split[1]
        register_location = chunk_rule_split[0]
        if '-' in register_location:
            interval = register_location.split('-')
            interval_from = int(interval[0])
            interval_to = int(interval[1]) + 1
            rules_dict[tuple(registers_output[interval_from:interval_to])] = rule_type
        else:
            rules_dict[registers_output[registers_output[int(register_location)]]] = rule_type

    return rules_dict


def decode_registers(registers_output: list, decode_schema: str | None) -> list:
    if not decode_schema:
        return registers_output

    decoded_list = []
    decode_rules_by_chunks = decode_by_chunks(registers_output, decode_schema)
    for registers, data_type in decode_rules_by_chunks.items():
        if isinstance(registers, int):
            registers_list = [registers]
        else:
            registers_list = list(registers)
        decoded_register = ModbusTcpClient.convert_from_registers(
            registers=registers_list,
            data_type=ModbusTcpClient.DATATYPE[data_type.upper()],
            word_order="little"
        )
        decoded_list.append(decoded_register)

    return decoded_list
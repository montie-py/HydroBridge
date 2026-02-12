# #!/usr/bin/env python3
import csv, argparse
from pymodbus.client import ModbusTcpClient
from settings import OUTPUT_FILE_NAME


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


def generate_csv_output(registers: list[int]):
    with open(OUTPUT_FILE_NAME, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'seconds_counter',
            'minutes_counter',
            'valve1_open',
            'motor_on',
            'pump_on',
            'flow_meter_1_screen',
            'alert_flag_1',
            'alert_flag_2',
            'shutdown_flag',
            'heater_status'
        ])
        writer.writerow(registers)


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

def main(argv=None):
    global args
    parser = argparse.ArgumentParser(description='Image metadata search CLI')
    parser.add_argument('--ip', default='192.168.1.200', help='IPv4 of a PLC/HMI')
    parser.add_argument('--port', type=int, default=502, help='Port of PLC/HMI')
    parser.add_argument('--address_from', type=int, default=10, help='Index of the first register to search')
    parser.add_argument('--address_to', type=int, default=10,
                        help='How many registers to search from the initial index')
    parser.add_argument('--schema', default='--schema "0:uint16,1-2:float32,3:int16,4-5:int32"',
                        help='How to decode the registers')
    args = parser.parse_args(argv)

    # run parsing and CSV generation logic
    registers_output = pymodbus_parse_register(ip=args.ip, port=args.port, address=args.address_from,
                                               count=args.address_to)
    decoded_registers_output = decode_registers(registers_output, args.schema)

    generate_csv_output(decoded_registers_output)


if __name__ == "__main__":
    main()
    print("Done")

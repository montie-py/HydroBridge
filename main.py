# #!/usr/bin/env python3
import csv, argparse
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
        0x00,0x01,        # Transaction ID
        0x00,0x00,        # Protocol ID
        0x00,0x06,        # Length
        0x01,             # Unit ID
        function_code,             # Function code (Read Holding Registers)
        start_address_from, start_address_to,        # Start address = 1000 (0x03E8)
        quantity_from, quantity_to         # Quantity = 47 (0x002F)
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

    from pymodbus.client import ModbusTcpClient

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

def main(argv=None):
    parser = argparse.ArgumentParser(description='Image metadata search CLI')
    parser.add_argument('--ip', default='192.168.1.200', help='IPv4 of a PLC/HMI')
    parser.add_argument('--port', type=int, default=502, help='Port of PLC/HMI')
    args = parser.parse_args(argv)

    #run parsing and CSV generation logic
    registers_output = pymodbus_parse_register(ip=args.ip, port=args.port, address=10, count=10)
    generate_csv_output(registers_output)


if __name__ == "__main__":
    main()
    print("Done")
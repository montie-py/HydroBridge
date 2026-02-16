# #!/usr/bin/env python3
import argparse
from business.csv_generation import generate_csv_output
from business.polling import pymodbus_parse_register, decode_registers


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

    headers = [
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
    ]
    generate_csv_output(decoded_registers_output, headers)


if __name__ == "__main__":
    main()
    print("Done")

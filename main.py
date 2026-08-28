# #!/usr/bin/env python3
import argparse
from business.csv_generation import CsvGeneration
from business.polling import Polling
from business.client import Client
from business.server import Server
from business.publish_to_plc import PublishToPLC

class InstanceHandler:
    def get_client(self):
        return Client()

    def get_server(self):
        return Server()

    def get_publish_to_plc(self):
        return PublishToPLC()


def main(argv=None):
    global args
    parser = argparse.ArgumentParser(description='HydroBridge: Parsing PLC registers and sending them to Azure')
    parser.add_argument('--instance', default='client', help='client|server|publish_plc')
    args = parser.parse_args(argv)

    instance_handler = InstanceHandler()

    instance_handler_dict = {
       "client": instance_handler.get_client,
        "server": instance_handler.get_server, "publish_plc": instance_handler.get_publish_to_plc,
        "default": instance_handler.get_client
    }

    instance = instance_handler_dict.get(args.instance, "default")
    instance.run()

    polling = Polling()
    # run parsing and CSV generation logic
    registers_output = polling.pymodbus_parse_register(ip=args.ip, port=args.port, address=args.address_from,
                                               count=args.address_to)
    decoded_registers_output = polling.decode_registers(registers_output, args.schema)

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
    csv_generation = CsvGeneration()
    csv_generation.generate_csv_output(decoded_registers_output, headers)

if __name__ == "__main__":
    main()
    print("Done")

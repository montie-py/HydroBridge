## Description
A script, that connects to an *already existing* PLC/HMI device through TCP / Modbus TCP protocol, extracts data from particular registers, and generates an output CSV file with the result.

Pretty useful for scenarios, when you need to send some data from a PLC to a remote server (Cloud/on-premises) for some analytical/statistical purposes through a separate device.

Example:

                          Script
                             |
                             |
                             V
    PLC <---------> Device with Internet connection <---------> Data Server

## Usage

`main.py --ip="192.168.1.200" --port=502 --address_from=10 --address_to=10`


## Description
A script, that connects to an *already existing* PLC/HMI device through TCP / Modbus TCP protocol, extracts data from particular registers, and generates an output CSV file with the result.

Pretty useful for scenarios, when you need to send some data from a PLC to a remote server (Cloud/on-premises) for some analytical/statistical purposes through a separate device.

Example:

                          Script
                             |
                             |
                             V
    PLC <---------> Device with Internet connection <---------> Data Server

## Installation

The core (`hydrobridge`) has no dependencies; adapters need extras:

    pip install "hydrobridge[modbus,azure]"

## Usage

The example application in `app/` wires the Modbus source to Azure IoT Hub. Run it from the project root:

    poetry install --all-extras --all-groups
    python -m app.main --instance server   # local Modbus test server fed from app/input.csv
    python -m app.main --instance client   # poll the PLC and publish to Azure

## TODO
- [ ] Transform main.py into a polling client: to poll everything from server.py, and to generate a csv file once in 2 mins.

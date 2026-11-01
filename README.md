## Description
HydroBridge is a Python library that reads registers from an *already existing* PLC/HMI device over Modbus TCP, decodes them into named values using a register map you supply, and publishes them as telemetry (Azure IoT Hub out of the box).

Pretty useful for scenarios, when you need to send some data from a PLC to a remote server (Cloud/on-premises) for some analytical/statistical purposes through a separate device.

Example:

                        HydroBridge
                             |
                             |
                             V
    PLC <---------> Device with Internet connection <---------> Data Server

If the data server is unreachable, the most recent readings (20 by default) are kept and sent once it's back. If the PLC drops the connection, the Modbus adapter reconnects on its own.

## Installation

The core (`hydrobridge`) has no dependencies; the adapters need extras:

    pip install "hydrobridge[modbus,azure]"   # Modbus source + Azure IoT Hub publisher
    pip install "hydrobridge[modbus]"         # only the Modbus source
    pip install hydrobridge                   # only the core, with your own source/publisher

Requires Python 3.11+.

## Usage

```python
import asyncio
from hydrobridge import RegisterField, RegisterMap, RegistersProcessingService
from hydrobridge.adapters.modbus import ModbusPLCAdapter
from hydrobridge.adapters.azure_iot import AzureIoTHubPublisher

register_map = RegisterMap([
    RegisterField("tank_level", address=0, data_type="float32", word_order="low_high", decimals=2),
    RegisterField("pump_state", address=2, data_type="uint16"),
])

async def main():
    async with ModbusPLCAdapter(
        host="192.168.1.10", port=502, device_id="gateway-1",
        start_address=register_map.start_address, count=register_map.register_count,
    ) as plc, AzureIoTHubPublisher(connection_string="HostName=...") as azure:
        service = RegistersProcessingService(plc, azure, register_map)
        while True:
            await service.run_once()        # read one block, publish it (and anything still pending)
            await asyncio.sleep(5)

asyncio.run(main())
```

Each reading is published as JSON:

```json
{"deviceId": "gateway-1", "ts": "2026-10-19T12:00:00", "registers": {"tank_level": 883.8, "pump_state": 1}}
```

### Register map

Each `RegisterField` names one value in the PLC's registers:

| Argument | Meaning |
|---|---|
| `name` | key in the published `registers` |
| `address` | Modbus address of the field's first register |
| `data_type` | `float32` (default), `int32`, `uint32` (2 registers each), `int16`, `uint16` (1 register) |
| `word_order` | for 32-bit types: `low_high` (default, low word first) or `high_low` |
| `decimals` | round the value to this many decimals; `None` (default) keeps it as decoded |

`RegisterMap` rejects duplicate names and overlapping fields, and gives the block to read: `start_address` and `register_count` (a Modbus read is limited to 125 registers).

The map can also live in a file, `.toml` or `.json`, with the same keys:

```toml
[[register]]
name = "tank_level"
address = 0
data_type = "float32"
word_order = "low_high"
decimals = 2

[[register]]
name = "pump_state"
address = 2
data_type = "uint16"
```

```python
from hydrobridge import load_register_map
register_map = load_register_map("plc_map.toml")
```

### Your own source or publisher

The service works with anything implementing the ports in `hydrobridge.ports`:

- `RegisterSourcePort.read_block()` returns a `RawRegisterBlock` and raises `SourceConnectionError` when the server can't be reached;
- `TelemetryPublisherPort.publish(reading)` raises `PublishFailedError` when a reading wasn't delivered (the service keeps it and retries).

The adapters also accept a ready-made client, e.g. for tests or a custom-configured connection: `ModbusPLCAdapter(..., client_factory=lambda: my_client)` (a factory, because a dropped easymodbus client can't reconnect and is replaced), `AzureIoTHubPublisher(client=my_iot_hub_client)`.

### Logging

HydroBridge logs through the standard `logging` module under the `hydrobridge` logger and doesn't configure logging itself. Without any setup only warnings are shown. To see more:

```python
import logging

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("hydrobridge").setLevel(logging.DEBUG)   # or logging.INFO
```

- WARNING: failed connection attempts, a dropped PLC connection, failed publishes, readings dropped because the pending queue is full
- INFO: connected to the PLC
- DEBUG: every block read and every reading published

Set the level on `"hydrobridge"` rather than with `basicConfig(level=...)`: easymodbus logs every request and response on the root logger at INFO and can change the root logger's level.

## Example application

The example application in `app/` (not part of the package) wires the Modbus source to Azure IoT Hub, with the device and its register map in `app/config/devices_config.json`. Run it from the project root:

    poetry install --all-extras --all-groups
    python -m app.main --instance server   # local Modbus test server fed from app/input.csv
    python -m app.main --instance client   # poll the PLC and publish to Azure
    python -m app.main --instance client --log-level DEBUG

The client reads the Azure connection string from `project_settings.py` (not in the repository).

## Development

    poetry install --all-extras --all-groups
    poetry run pytest                           # everything
    poetry run pytest -m "not packaging"        # skip the slower wheel/venv test

GitHub Actions runs the tests on Python 3.11–3.14 on every push and pull request.

### Releasing

1. Set the new version in `pyproject.toml` (`poetry version patch`, `minor` or `major`) and commit it.
2. Tag the commit with the same version and push the tag:

       git tag v0.1.1
       git push origin v0.1.1

GitHub Actions (`release.yml`) then runs the tests, builds the package, publishes it to TestPyPI, checks that it installs from there, and publishes it to PyPI. A version number can only be uploaded once.

## License

MIT, see [LICENSE](https://github.com/montie-py/HydroBridge/blob/master/LICENSE).

## TODO
- [ ] Transform main.py into a polling client: to poll everything from server.py, and to generate a csv file once in 2 mins.

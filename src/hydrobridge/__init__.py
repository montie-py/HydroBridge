"""HydroBridge: read PLC registers over Modbus and publish them as telemetry.

Adapters live in ``hydrobridge.adapters`` and need optional extras:
``hydrobridge[modbus]`` for the Modbus source, ``hydrobridge[azure]`` for Azure IoT Hub.
"""
from hydrobridge.models import PLCReading, RawRegisterBlock
from hydrobridge.ports import (
    PublishFailedError,
    RegisterSourcePort,
    SourceConnectionError,
    TelemetryPublisherPort,
)
from hydrobridge.register_map import RegisterField, RegisterMap, load_register_map
from hydrobridge.service import RegistersProcessingService, registers_to_float

__all__ = [
    "PLCReading",
    "RawRegisterBlock",
    "PublishFailedError",
    "RegisterSourcePort",
    "SourceConnectionError",
    "TelemetryPublisherPort",
    "RegisterField",
    "RegisterMap",
    "load_register_map",
    "RegistersProcessingService",
    "registers_to_float",
]

from dataclasses import dataclass
from typing import Mapping, Sequence
from datetime import datetime

@dataclass(frozen=True)
class RawRegisterBlock:
    device_id : str
    registers : Sequence[int]
    read_at : datetime
    # Modbus address of registers[0]
    start_address : int = 0

@dataclass(frozen=True)
class PLCReading:
   device_id : str
   registers : Mapping[str, float | int]
   read_at : datetime



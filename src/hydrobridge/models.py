from dataclasses import dataclass
from typing import Mapping
from datetime import datetime

@dataclass(frozen=True)
class RawRegisterBlock:
    device_id : str
    registers : Mapping[int, int]
    read_at : datetime

@dataclass(frozen=True)
class PLCReading:
   device_id : str
   registers : Mapping[str, int]
   read_at : datetime



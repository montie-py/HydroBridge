import json
import struct
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping, Sequence, get_args

DataType = Literal["float32", "int32", "uint32", "int16", "uint16"]
WordOrder = Literal["low_high", "high_low"]

# struct format of each type once its words are packed as big-endian bytes
_FORMATS = {"float32": ">f", "int32": ">i", "uint32": ">I", "int16": ">h", "uint16": ">H"}


@dataclass(frozen=True)
class RegisterField:
    """One named value in the PLC's register space.

    ``address`` is the Modbus address of the field's first register.
    ``word_order`` only matters for 32-bit types: ``low_high`` means the low word comes first
    (easymodbus RegisterOrder.lowHigh), ``high_low`` means the high word comes first.
    ``decimals`` rounds the decoded value; None leaves it as decoded.
    """
    name : str
    address : int
    data_type : DataType = "float32"
    word_order : WordOrder = "low_high"
    decimals : int | None = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("RegisterField name must not be empty")
        if self.address < 0:
            raise ValueError(f"{self.name}: address must be >= 0, got {self.address}")
        if self.data_type not in _FORMATS:
            raise ValueError(f"{self.name}: unknown data_type {self.data_type!r}, "
                             f"expected one of {', '.join(_FORMATS)}")
        if self.word_order not in get_args(WordOrder):
            raise ValueError(f"{self.name}: unknown word_order {self.word_order!r}, "
                             f"expected one of {', '.join(get_args(WordOrder))}")
        if self.decimals is not None and self.decimals < 0:
            raise ValueError(f"{self.name}: decimals must be >= 0, got {self.decimals}")

    @property
    def width(self) -> int:
        """Number of 16-bit registers the field occupies."""
        return 2 if self.data_type.endswith("32") else 1

    def decode(self, words : Sequence[int]) -> float | int:
        """Decode the field's value from its own registers (``width`` words, in address order)."""
        if len(words) != self.width:
            raise ValueError(f"{self.name}: expected {self.width} registers, got {len(words)}")
        if self.word_order == "low_high":
            words = words[::-1]
        value = struct.unpack(_FORMATS[self.data_type], struct.pack(f">{self.width}H", *words))[0]
        if self.decimals is not None:
            value = round(value, self.decimals)
        return value


class RegisterMap(Sequence[RegisterField]):
    """An ordered set of fields with unique names and non-overlapping registers."""

    def __init__(self, fields : Iterable[RegisterField]):
        self._fields : tuple[RegisterField, ...] = tuple(fields)
        if not self._fields:
            raise ValueError("RegisterMap needs at least one field")

        names = set()
        for field in self._fields:
            if field.name in names:
                raise ValueError(f"duplicate field name {field.name!r}")
            names.add(field.name)

        by_address = sorted(self._fields, key=lambda f: f.address)
        for previous, current in zip(by_address, by_address[1:]):
            if current.address < previous.address + previous.width:
                raise ValueError(f"{current.name} (address {current.address}) overlaps "
                                 f"{previous.name} (address {previous.address}, {previous.width} registers)")

    @classmethod
    def from_dicts(cls, entries : Iterable[Mapping]) -> "RegisterMap":
        """Build a map from plain dicts whose keys are RegisterField's attribute names."""
        fields = []
        for index, entry in enumerate(entries):
            try:
                fields.append(RegisterField(**entry))
            except TypeError as exc:
                raise ValueError(f"register entry {index}: {exc}") from exc
        return cls(fields)

    @property
    def start_address(self) -> int:
        """Lowest address the map covers, i.e. where a block read should start."""
        return min(field.address for field in self._fields)

    @property
    def register_count(self) -> int:
        """Number of registers from start_address to the end of the last field."""
        return max(field.address + field.width for field in self._fields) - self.start_address

    def decode(self, registers : Sequence[int], start_address : int) -> dict[str, float | int]:
        """Decode every field from a block of registers read starting at ``start_address``."""
        values = {}
        for field in self._fields:
            offset = field.address - start_address
            if offset < 0 or offset + field.width > len(registers):
                raise ValueError(f"{field.name} (address {field.address}) is outside the block read "
                                 f"from address {start_address} ({len(registers)} registers)")
            values[field.name] = field.decode(registers[offset:offset + field.width])
        return values

    def __getitem__(self, index):
        return self._fields[index]

    def __len__(self) -> int:
        return len(self._fields)

    def __repr__(self) -> str:
        return f"RegisterMap({list(self._fields)!r})"


def load_register_map(path : str | Path) -> RegisterMap:
    """Read a register map from a .json or .toml file.

    The file holds a list of entries under the key ``register`` (TOML ``[[register]]`` tables);
    a JSON file may also be just the list. Entry keys are RegisterField's attribute names.
    """
    path = Path(path)
    if path.suffix == ".toml":
        with path.open("rb") as file:
            data = tomllib.load(file)
    elif path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise ValueError(f"unsupported register map file type {path.suffix!r}, use .json or .toml")

    entries = data if isinstance(data, list) else data.get("register")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: expected a list of register entries under the key 'register'")
    return RegisterMap.from_dicts(entries)

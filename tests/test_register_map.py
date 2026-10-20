import csv
import json
from pathlib import Path

import pytest
from easymodbus.modbus_client import convert_float_to_two_registers

from hydrobridge.register_map import RegisterField, RegisterMap, load_register_map

INPUT_CSV = Path(__file__).resolve().parents[1] / "app" / "input.csv"


# --- decoding single fields from known register words ---

@pytest.mark.parametrize("data_type, word_order, words, expected", [
    # 1.5 is 0x3FC00000; -2.25 is 0xC0100000
    ("float32", "high_low", [0x3FC0, 0x0000], 1.5),
    ("float32", "low_high", [0x0000, 0x3FC0], 1.5),
    ("float32", "high_low", [0xC010, 0x0000], -2.25),
    ("uint32", "high_low", [0x1234, 0x5678], 0x12345678),
    ("uint32", "low_high", [0x5678, 0x1234], 0x12345678),
    ("uint32", "high_low", [0xFFFF, 0xFFFF], 4294967295),
    ("int32", "high_low", [0xFFFF, 0xFFFE], -2),
    ("int32", "low_high", [0xFFFE, 0xFFFF], -2),
    ("int32", "high_low", [0x7FFF, 0xFFFF], 2147483647),
    ("uint16", "low_high", [0xFFFF], 65535),
    ("int16", "low_high", [0xFFFF], -1),
    ("int16", "low_high", [0x8000], -32768),
    ("int16", "low_high", [0x7FFF], 32767),
])
def test_decode_known_values(data_type, word_order, words, expected):
    field = RegisterField("x", address=0, data_type=data_type, word_order=word_order)
    assert field.decode(words) == expected


def test_word_order_does_not_affect_16_bit_types():
    assert RegisterField("x", 0, "int16", "high_low").decode([0xFFFF]) == -1


@pytest.mark.parametrize("data_type, width", [
    ("float32", 2), ("int32", 2), ("uint32", 2), ("int16", 1), ("uint16", 1),
])
def test_width(data_type, width):
    assert RegisterField("x", 0, data_type).width == width


def test_decimals_rounds_and_none_keeps_full_value():
    words = convert_float_to_two_registers(89.23)        # float32 can't hold 89.23 exactly
    assert RegisterField("x", 0, decimals=2).decode(words) == 89.23
    assert RegisterField("x", 0).decode(words) != 89.23
    assert RegisterField("x", 0).decode(words) == pytest.approx(89.23, abs=1e-5)


def test_decode_rejects_wrong_number_of_words():
    with pytest.raises(ValueError, match="expected 2 registers, got 1"):
        RegisterField("x", 0, "float32").decode([1])


# --- the real data: values written the way the simulator writes them decode back ---

def load_csv_rows(limit):
    with INPUT_CSV.open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))[1:limit + 1]
    return [[float(column) for column in row[3:]] for row in rows]


@pytest.mark.parametrize("row", load_csv_rows(limit=20))
def test_csv_values_decode_back_to_the_csv_numbers(row):
    registers = []
    for value in row:
        registers += convert_float_to_two_registers(value)   # same as app/server.py
    register_map = RegisterMap(
        RegisterField(f"column_{index}", address=index * 2, decimals=3) for index in range(len(row))
    )

    values = register_map.decode(registers, start_address=0)

    assert list(values.values()) == pytest.approx(row, rel=1e-6)


# --- the map ---

def make_map():
    return RegisterMap([
        RegisterField("level", address=101, data_type="uint16"),
        RegisterField("temperature", address=102, data_type="float32", word_order="high_low"),
        RegisterField("state", address=105, data_type="int16"),
    ])


def test_start_address_and_register_count_cover_all_fields():
    register_map = make_map()
    assert register_map.start_address == 101
    assert register_map.register_count == 5    # 101..105; 104 is a gap


def test_decode_block_read_from_an_earlier_address():
    # block read from address 100: index 0 is address 100, which the map doesn't use
    block = [9999, 42, 0x3FC0, 0x0000, 7777, 0xFFFF]
    assert make_map().decode(block, start_address=100) == {"level": 42, "temperature": 1.5, "state": -1}


def test_decode_keeps_the_map_order():
    register_map = RegisterMap([RegisterField("b", 2, "uint16"), RegisterField("a", 0, "uint16")])
    assert list(register_map.decode([1, 0, 2], start_address=0)) == ["b", "a"]


@pytest.mark.parametrize("block, start_address", [
    ([0] * 4, 101),     # ends before "state" at 105
    ([0] * 10, 102),    # starts after "level" at 101
])
def test_decode_rejects_a_block_that_misses_a_field(block, start_address):
    with pytest.raises(ValueError, match="outside the block"):
        make_map().decode(block, start_address)


def test_map_is_a_read_only_sequence():
    register_map = make_map()
    assert len(register_map) == 3
    assert register_map[0].name == "level"
    assert [field.name for field in register_map] == ["level", "temperature", "state"]
    with pytest.raises(AttributeError):
        register_map[0].address = 5      # fields are frozen


# --- validation ---

@pytest.mark.parametrize("kwargs, message", [
    (dict(name="", address=0), "name must not be empty"),
    (dict(name="x", address=-1), "address must be >= 0"),
    (dict(name="x", address=0, data_type="float64"), "unknown data_type 'float64'"),
    (dict(name="x", address=0, word_order="big"), "unknown word_order 'big'"),
    (dict(name="x", address=0, decimals=-1), "decimals must be >= 0"),
])
def test_field_validation(kwargs, message):
    with pytest.raises(ValueError, match=message):
        RegisterField(**kwargs)


def test_map_rejects_overlapping_fields():
    with pytest.raises(ValueError, match=r"b \(address 1\) overlaps a \(address 0, 2 registers\)"):
        RegisterMap([RegisterField("a", 0, "float32"), RegisterField("b", 1, "uint16")])


def test_map_allows_adjacent_fields():
    RegisterMap([RegisterField("a", 0, "float32"), RegisterField("b", 2, "uint16")])


def test_map_rejects_duplicate_names():
    with pytest.raises(ValueError, match="duplicate field name 'a'"):
        RegisterMap([RegisterField("a", 0), RegisterField("a", 2)])


def test_map_rejects_no_fields():
    with pytest.raises(ValueError, match="at least one field"):
        RegisterMap([])


# --- building from dicts and files ---

def test_from_dicts_uses_defaults():
    register_map = RegisterMap.from_dicts([{"name": "level", "address": 4}])
    assert register_map[0] == RegisterField("level", 4, "float32", "low_high", None)


def test_from_dicts_names_the_bad_entry_and_suggests_the_key():
    with pytest.raises(ValueError, match="register entry 1: .*'adress'"):
        RegisterMap.from_dicts([{"name": "a", "address": 0}, {"name": "b", "adress": 2}])


EXPECTED_FROM_FILE = [
    RegisterField("tank_level", 0, "float32", "low_high", 2),
    RegisterField("pump_state", 2, "uint16"),
]


def test_load_toml(tmp_path):
    path = tmp_path / "map.toml"
    path.write_text(
        '[[register]]\nname = "tank_level"\naddress = 0\ndata_type = "float32"\n'
        'word_order = "low_high"\ndecimals = 2\n\n'
        '[[register]]\nname = "pump_state"\naddress = 2\ndata_type = "uint16"\n'
    )
    assert list(load_register_map(path)) == EXPECTED_FROM_FILE


@pytest.mark.parametrize("content", [
    {"register": [{"name": "tank_level", "address": 0, "decimals": 2},
                  {"name": "pump_state", "address": 2, "data_type": "uint16"}]},
    [{"name": "tank_level", "address": 0, "decimals": 2},
     {"name": "pump_state", "address": 2, "data_type": "uint16"}],
])
def test_load_json_with_or_without_the_register_key(tmp_path, content):
    path = tmp_path / "map.json"
    path.write_text(json.dumps(content))
    assert list(load_register_map(str(path))) == EXPECTED_FROM_FILE


def test_load_rejects_other_file_types(tmp_path):
    path = tmp_path / "map.yaml"
    path.write_text("")
    with pytest.raises(ValueError, match="use .json or .toml"):
        load_register_map(path)


def test_load_rejects_a_file_without_entries(tmp_path):
    path = tmp_path / "map.json"
    path.write_text('{"registers": []}')
    with pytest.raises(ValueError, match="under the key 'register'"):
        load_register_map(path)

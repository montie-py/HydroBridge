"""The example app's devices_config.json must load and give a usable register map."""
from app.config.devices_config import get_config
from hydrobridge.adapters.modbus import MAX_REGISTERS_PER_READ


def test_devices_config_loads_and_builds_a_register_map():
    config = get_config()

    assert config.devices_configuration
    for device in config.devices_configuration:
        register_map = device.build_register_map()      # validates types, overlaps, duplicate names
        assert device.device_ip and device.device_port
        assert 1 <= register_map.register_count <= MAX_REGISTERS_PER_READ


def test_register_map_matches_the_simulator_layout():
    # app/server.py writes each input.csv column as a float32 at address 2 * column index
    register_map = get_config().devices_configuration[0].build_register_map()

    assert (register_map.start_address, register_map.register_count) == (0, 52)
    assert all(field.data_type == "float32" and field.address % 2 == 0 for field in register_map)

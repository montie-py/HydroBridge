from pydantic import BaseModel, Field

class DevicesConfig(BaseModel):
    serial_number: str = Field(alias="SerialNumber")
    device_ip: str = Field(alias="DeviceIP")
    device_port: str = Field(alias="DevicePort")
    registers_range_from: int = Field(alias="RegistersRangeFrom")
    registers_range_quantity: int = Field(alias="RegistersRangeQuantity")

    class Config:
        populate_by_name = True


class AppConfig(BaseModel):
    devices_configuration: list[DevicesConfig] = Field(alias="DevicesConfiguration")


def get_config():
    with open('devices_config.json', 'r') as f:
        config = AppConfig.model_validate_json(f.read())
    return config
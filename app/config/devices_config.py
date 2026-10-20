from pathlib import Path

from pydantic import BaseModel, Field

from hydrobridge import RegisterMap

_CONFIG_PATH = Path(__file__).resolve().parent / "devices_config.json"

class RegisterFieldConfig(BaseModel):
    name: str = Field(alias="Name")
    address: int = Field(alias="Address")
    data_type: str = Field(default="float32", alias="DataType")
    word_order: str = Field(default="low_high", alias="WordOrder")
    decimals: int | None = Field(default=None, alias="Decimals")

    class Config:
        populate_by_name = True


class DevicesConfig(BaseModel):
    serial_number: str = Field(alias="SerialNumber")
    device_ip: str = Field(alias="DeviceIp")
    device_port: int = Field(alias="DevicePort")
    register_map: list[RegisterFieldConfig] = Field(alias="RegisterMap")

    class Config:
        populate_by_name = True

    def build_register_map(self) -> RegisterMap:
        # the block to read (start address, register count) follows from the map
        return RegisterMap.from_dicts(field.model_dump() for field in self.register_map)


class IntervalConfiguration(BaseModel):
    polling_loop_pause_mills: int = Field(alias="PollingLoopPauseMills")
    connection_trying_timeout_mills: int = Field(alias="ConnectionTryingTimeoutMills")
    polling_loop_interval_mills: int = Field(alias="PollingLoopIntervalMills")
    retry_delay_mills: int = Field(alias="RetryDelayMills")


class AppConfig(BaseModel):
    devices_configuration: list[DevicesConfig] = Field(alias="DevicesConfiguration")
    interval_configuration: dict = Field(alias="IntervalConfiguration")


def get_config():
    return AppConfig.model_validate_json(_CONFIG_PATH.read_text(encoding="utf-8"))
from pathlib import Path

from pydantic import BaseModel, Field

_CONFIG_PATH = Path(__file__).resolve().parent / "devices_config.json"

class DevicesConfig(BaseModel):
    serial_number: str = Field(alias="SerialNumber")
    device_ip: str = Field(alias="DeviceIp")
    device_port: int = Field(alias="DevicePort")
    registers_range_from: int = Field(alias="RegistersRangeFrom")
    registers_range_quantity: int = Field(alias="RegistersRangeQuantity")

    class Config:
        populate_by_name = True


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
from abc import ABC, abstractmethod

from business.client.domain.models import PLCReading


class RegisterSourcePort(ABC):

    @abstractmethod
    def read_block(self):
        pass

class TelemetryPublisherPort(ABC):

    @abstractmethod
    def publish(self, plc_reading : PLCReading):
        pass
from abc import ABC, abstractmethod

class RegisterSourcePort(ABC):

    @abstractmethod
    def read_block(self):
        pass

class TelemetryPublisherPort(ABC):

    @abstractmethod
    def publish(self, plc_reading):
        pass
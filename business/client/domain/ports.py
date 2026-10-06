from abc import ABC, abstractmethod

from business.client.domain.models import PLCReading


class PublishFailedError(Exception):
    """Raised by a TelemetryPublisherPort when a reading could not be delivered."""


class RegisterSourcePort(ABC):

    @abstractmethod
    async def read_block(self):
        pass

class TelemetryPublisherPort(ABC):

    @abstractmethod
    async def publish(self, plc_reading : PLCReading):
        """Deliver one reading; raise PublishFailedError if it wasn't sent."""
        pass

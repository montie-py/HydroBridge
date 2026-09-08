from abc import ABC, abstractmethod
class Runnable(ABC):
    @abstractmethod
    async def run(self):
        pass
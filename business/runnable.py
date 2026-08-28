from abc import ABC, abstractmethod
class Runnable(ABC):
    @abstractmethod
    def run(self):
        pass
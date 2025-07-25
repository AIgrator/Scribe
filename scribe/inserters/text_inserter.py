# inserters/text_inserter.py
from abc import ABC, abstractmethod


class TextInserter(ABC):
    @abstractmethod
    def wait_until_idle(self, timeout=2.0):
        """By default, does nothing (for compatibility)."""
        pass
    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def insert_text(self, text: str):
        pass

    @abstractmethod
    def erase_chars(self, count: int):
        pass

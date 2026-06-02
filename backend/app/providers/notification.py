import logging
from abc import ABC, abstractmethod

log = logging.getLogger("dispatch")


class NotificationProvider(ABC):
    @abstractmethod
    def send(self, to: str, body: str) -> None:
        raise NotImplementedError


class MockProvider(NotificationProvider):
    def send(self, to: str, body: str) -> None:
        log.info("MOCK SMS to %s\n%s", to, body)

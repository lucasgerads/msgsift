from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    id: str
    source: str
    sender: str
    subject: str
    snippet: str
    timestamp: datetime


class MessageSource:
    def fetch(self) -> list[Message]:
        raise NotImplementedError

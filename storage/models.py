from dataclasses import dataclass
from datetime import datetime

@dataclass
class Transcript:
    text: str
    timestamp: datetime

@dataclass
class Summary:
    text: str
    timestamp: datetime

"""
Event type definitions.
All events carry a type string and a payload dict.
"""
from dataclasses import dataclass, field
from typing import Dict, Any
from utils.time_utils import now_iso


@dataclass
class Event:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=now_iso)

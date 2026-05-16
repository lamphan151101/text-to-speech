from dataclasses import dataclass, field


@dataclass
class Speaker:
    name: str
    voice: str = ""
    language_group: str = ""
    pitch: int = 0
    rate: int = 0
    segments: set[int] = field(default_factory=set)

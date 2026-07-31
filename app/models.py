from dataclasses import dataclass


@dataclass
class WordEntry:
    word: str
    definition: str
    theme: str = ""
    placed: bool = False


@dataclass(frozen=True)
class Placement:
    word: str
    definition: str
    row: int
    col: int
    horizontal: bool

from dataclasses import dataclass, field


# Types de flèches d'une case définition vers le début de son mot.
ARROW_RIGHT = "right"            # définition à gauche d'un mot horizontal
ARROW_DOWN = "down"              # définition au-dessus d'un mot vertical
ARROW_DOWN_RIGHT = "down_right"  # définition au-dessus du début d'un mot horizontal (coudée)
ARROW_RIGHT_DOWN = "right_down"  # définition à gauche du début d'un mot vertical (coudée)


@dataclass
class Definition:
    text: str
    register: str = "factuel"  # factuel | joueur
    level: int = 1


@dataclass
class Entry:
    word: str                  # forme grille : MAJUSCULES A-Z sans accents
    display: str = ""          # forme naturelle : "Mbappé", "Di María"
    category: str = ""
    definitions: list[Definition] = field(default_factory=list)
    placed: bool = False


@dataclass
class Placement:
    word: str
    definition: str
    row: int
    col: int
    horizontal: bool
    clue_row: int
    clue_col: int
    arrow: str
    display: str = ""

"""Fonction de pénalité d'un masque de mots fléchés.

Barèmes recopiés de l'état de l'art (J. Engel, « Generating Swedish-style
Crossword Puzzle Masks » — voir docs/reference_masques.md). Un masque est une
matrice de booléens : True = case définition, False = case lettre. Plus le
score est bas, meilleur est le masque ; les composantes « validité » non
nulles signalent un masque inutilisable tel quel.

Adaptations à notre modèle (flèches implicites) signalées par [nous].
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Pénalité par longueur de mot. L'optimum est 5-6 lettres ; les mots de
# 2 lettres coûtent presque autant qu'une case invalide.
WORD_LENGTH_PENALTY = {
    2: 650,
    3: 100,
    4: 10,
    5: 0,
    6: 0,
    7: 30,
    8: 50,
    9: 150,
    10: 250,
    11: 400,
    12: 550,
    13: 750,
    14: 1000,
    15: 1300,
}

# Couverture d'une case lettre.
PENALTY_ORPHAN = 1500        # couverte par aucun mot (invalide)
PENALTY_SINGLE = 200         # couverte par un seul mot
PENALTY_SINGLE_BORDER = 75   # idem mais en bord haut/gauche (souvent forcé)

PENALTY_DEAD_END = 400       # lettre cernée par 3 cases non-lettre
PENALTY_ARROW = 2000         # mot sans case définition atteignable, ou case
                             # définition surchargée (> 2 mots) — analogue du
                             # « mot non enclavé » de la thèse
PENALTY_LENGTH_UNAVAILABLE = 1500  # [nous] aucune entrée de cette longueur
PENALTY_DEAD_CLUE = 40       # [nous] case définition ne servant aucun mot

# Amas de cases définitions (8-connexes) : table (taille, étendue max) de la
# thèse, sous forme (étendue min, pénalité de base, pente par cran d'étendue).
_CLUSTER_ROWS: dict[int, tuple[int, float, float]] = {
    2: (2, 150.0, 0.0),
    3: (2, 288.0, 32.0),
    4: (2, 542.0, 64.0),
    5: (3, 794.0, 93.0),
    6: (4, 1053.0, 123.0),
    7: (5, 1620.0, 190.0),
}


def word_length_penalty(length: int) -> int:
    if length < 2:
        return 0
    if length in WORD_LENGTH_PENALTY:
        return WORD_LENGTH_PENALTY[length]
    return 1300 + 300 * (length - 15)


def _cluster_row(size: int) -> tuple[int, float, float]:
    if size in _CLUSTER_ROWS:
        return _CLUSTER_ROWS[size]
    # Au-delà de la table publiée : extrapolation superlinéaire.
    ext_min, base, slope = _CLUSTER_ROWS[7]
    factor = (size / 7.0) ** 1.6
    return ext_min, base * factor, slope * factor


def _cluster_penalty_int(size: int, extension: int) -> float:
    if size <= 1:
        return 0.0
    ext_min, base, slope = _cluster_row(size)
    return base + slope * max(0, extension - ext_min)


def cluster_penalty(size: float, extension: int) -> float:
    """Pénalité d'un amas ; la taille peut être fractionnaire (les cases en
    bord haut/gauche comptent moitié)."""
    if size <= 1.0:
        return 0.0
    low = int(size)
    high = low + 1
    penalty_low = _cluster_penalty_int(low, extension)
    if size == low:
        return penalty_low
    penalty_high = _cluster_penalty_int(high, extension)
    return penalty_low + (penalty_high - penalty_low) * (size - low)


@dataclass
class MaskScore:
    total: int
    validity: int
    quality: int
    details: dict[str, int] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return self.validity == 0


def _runs_of(clue: list[list[bool]]):
    """Suites maximales de cases lettre : (ligne, colonne, horizontal, long.)."""
    height, width = len(clue), len(clue[0])
    runs = []
    for r in range(height):
        c = 0
        while c < width:
            if clue[r][c]:
                c += 1
                continue
            start = c
            while c < width and not clue[r][c]:
                c += 1
            runs.append((r, start, True, c - start))
    for c in range(width):
        r = 0
        while r < height:
            if clue[r][c]:
                r += 1
                continue
            start = r
            while r < height and not clue[r][c]:
                r += 1
            runs.append((start, c, False, r - start))
    return runs


def score_mask(
    clue: list[list[bool]],
    available_lengths: set[int] | None = None,
) -> MaskScore:
    height, width = len(clue), len(clue[0])
    details = {
        "couverture": 0,
        "orphelines": 0,
        "longueurs": 0,
        "croisements_longs": 0,
        "amas": 0,
        "culs_de_sac": 0,
        "fleches": 0,
        "longueurs_indisponibles": 0,
        "cases_mortes": 0,
    }

    runs = _runs_of(clue)
    hlen = [[0] * width for _ in range(height)]
    vlen = [[0] * width for _ in range(height)]
    for r, c, horizontal, length in runs:
        for i in range(length):
            if horizontal:
                hlen[r][c + i] = length
            else:
                vlen[r + i][c] = length

    # --- couverture de chaque case lettre
    for r in range(height):
        for c in range(width):
            if clue[r][c]:
                continue
            covered_h = hlen[r][c] >= 2
            covered_v = vlen[r][c] >= 2
            if covered_h and covered_v:
                continue
            if not covered_h and not covered_v:
                details["orphelines"] += PENALTY_ORPHAN
            elif r == 0 or c == 0:
                details["couverture"] += PENALTY_SINGLE_BORDER
            else:
                details["couverture"] += PENALTY_SINGLE

    # --- longueur des mots, disponibilité, flèches
    loads: dict[tuple[int, int], int] = {}
    for r, c, horizontal, length in runs:
        if length < 2:
            continue
        details["longueurs"] += word_length_penalty(length)
        if available_lengths is not None and length not in available_lengths:
            details["longueurs_indisponibles"] += PENALTY_LENGTH_UNAVAILABLE

        # Case définition atteignable : la case précédente (naturelle), ou la
        # flèche coudée depuis l'autre direction en bord de grille.
        if horizontal:
            anchor = (r, c - 1) if c > 0 else (r - 1, c)
        else:
            anchor = (r - 1, c) if r > 0 else (r, c - 1)
        ar, ac = anchor
        if ar < 0 or ac < 0 or not clue[ar][ac]:
            details["fleches"] += PENALTY_ARROW
        else:
            loads[anchor] = loads.get(anchor, 0) + 1

    for load in loads.values():
        if load > 2:
            details["fleches"] += PENALTY_ARROW * (load - 2)

    # --- croisements de deux mots longs (> 6 lettres)
    for r in range(height):
        for c in range(width):
            if not clue[r][c] and hlen[r][c] >= 7 and vlen[r][c] >= 7:
                details["croisements_longs"] += hlen[r][c] * vlen[r][c]

    # --- amas 8-connexes de cases définitions
    seen = [[False] * width for _ in range(height)]
    for r in range(height):
        for c in range(width):
            if not clue[r][c] or seen[r][c]:
                continue
            stack = [(r, c)]
            seen[r][c] = True
            cells = []
            while stack:
                cr, cc = stack.pop()
                cells.append((cr, cc))
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        nr, nc = cr + dr, cc + dc
                        if (
                            0 <= nr < height
                            and 0 <= nc < width
                            and clue[nr][nc]
                            and not seen[nr][nc]
                        ):
                            seen[nr][nc] = True
                            stack.append((nr, nc))
            size = sum(
                0.5 if (cr == 0 or cc == 0) else 1.0 for cr, cc in cells
            )
            rows_ = [cr for cr, _ in cells]
            cols_ = [cc for _, cc in cells]
            extension = max(
                max(rows_) - min(rows_) + 1, max(cols_) - min(cols_) + 1
            )
            details["amas"] += int(round(cluster_penalty(size, extension)))

    # --- culs-de-sac : lettre cernée par 3 cases non-lettre (hors bords
    # haut/gauche, où c'est inévitable)
    for r in range(1, height):
        for c in range(1, width):
            if clue[r][c]:
                continue
            blocked = 0
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < height and 0 <= nc < width) or clue[nr][nc]:
                    blocked += 1
            if blocked >= 3:
                details["culs_de_sac"] += PENALTY_DEAD_END

    # --- cases définitions ne servant aucun mot [nous]
    for r in range(height):
        for c in range(width):
            if clue[r][c] and (r, c) not in loads:
                details["cases_mortes"] += PENALTY_DEAD_CLUE

    validity = (
        details["orphelines"]
        + details["fleches"]
        + details["longueurs_indisponibles"]
    )
    quality = sum(details.values()) - validity
    return MaskScore(
        total=validity + quality,
        validity=validity,
        quality=quality,
        details=details,
    )

"""Amélioration locale d'un masque par hill-climbing guidé.

Méthode recopiée de l'état de l'art (docs/reference_masques.md) :
- mutations centralisées : un point central, k ∈ {2, 3} cases modifiées à
  proximité (les changements corrélés aident à franchir les optima locaux) ;
- mutation guidée : le centre est choisi par tournoi sur la pénalité locale
  (on mute là où le masque pèche) ;
- opérateurs prédéfinis : « décaler » une case définition, « couper » un mot
  long en deux.

L'acceptation est lexicographique (validité, total) : un masque valide ne
peut jamais être remplacé par un invalide, même meilleur en score brut.
"""

from __future__ import annotations

import random
import time

from app.mask_score import MaskScore, score_mask

# Au-delà de cette part de lettres doublement croisées, le remplissage
# devient trop contraint pour notre dictionnaire : pénalité progressive.
CROSSING_CAP = 0.78
CROSSING_SLOPE = 60_000


def _objective(
    clue: list[list[bool]],
    lengths: set[int],
    counts: dict[int, int],
    with_cells: bool = False,
) -> tuple[tuple[int, int], MaskScore]:
    score = score_mask(clue, lengths, counts, with_cells=with_cells)
    total = score.total
    if score.crossed_ratio > CROSSING_CAP:
        total += int((score.crossed_ratio - CROSSING_CAP) * CROSSING_SLOPE)
    return (score.validity, total), score


def _pick_center(
    rng: random.Random,
    cell_map: dict[tuple[int, int], float],
    height: int,
    width: int,
) -> tuple[int, int]:
    """Tournoi (α = 2) sur la pénalité locale."""
    first = (rng.randrange(height), rng.randrange(width))
    second = (rng.randrange(height), rng.randrange(width))
    if cell_map.get(second, 0.0) > cell_map.get(first, 0.0):
        return second
    return first


def _mutate(
    clue: list[list[bool]],
    rng: random.Random,
    cell_map: dict[tuple[int, int], float],
) -> list[list[bool]]:
    height, width = len(clue), len(clue[0])
    candidate = [row[:] for row in clue]
    draw = rng.random()

    if draw < 0.55:
        # Mutation centralisée : k cases proches du centre choisi par tournoi.
        center_r, center_c = _pick_center(rng, cell_map, height, width)
        flips = 2 if rng.random() < 0.5 else 3
        done = 0
        for _ in range(24):
            if done >= flips:
                break
            r = min(height - 1, max(0, round(center_r + rng.gauss(0, 1.5))))
            c = min(width - 1, max(0, round(center_c + rng.gauss(0, 1.5))))
            if (r, c) == (0, 0):
                continue
            candidate[r][c] = not candidate[r][c]
            done += 1
    elif draw < 0.80:
        # Décaler une case définition d'un cran.
        clues = [
            (r, c)
            for r in range(height)
            for c in range(width)
            if candidate[r][c] and (r, c) != (0, 0)
        ]
        if clues:
            r, c = rng.choice(clues)
            dr, dc = rng.choice(((-1, 0), (1, 0), (0, -1), (0, 1)))
            nr, nc = r + dr, c + dc
            if (
                0 <= nr < height
                and 0 <= nc < width
                and not candidate[nr][nc]
            ):
                candidate[r][c] = False
                candidate[nr][nc] = True
    else:
        # Couper un mot long en insérant une case définition.
        long_runs = []
        for r in range(height):
            c = 0
            while c < width:
                if candidate[r][c]:
                    c += 1
                    continue
                start = c
                while c < width and not candidate[r][c]:
                    c += 1
                if c - start >= 7:
                    long_runs.append((r, start, True, c - start))
        for c in range(width):
            r = 0
            while r < height:
                if candidate[r][c]:
                    r += 1
                    continue
                start = r
                while r < height and not candidate[r][c]:
                    r += 1
                if r - start >= 7:
                    long_runs.append((start, c, False, r - start))
        if long_runs:
            r, c, horizontal, length = rng.choice(long_runs)
            cut = rng.randrange(2, length - 2)
            if horizontal:
                candidate[r][c + cut] = True
            else:
                candidate[r + cut][c] = True

    candidate[0][0] = True
    return candidate


def improve_mask(
    clue: list[list[bool]],
    lengths: set[int],
    counts: dict[int, int],
    rng: random.Random,
    deadline: float,
    max_evaluations: int = 6000,
) -> list[list[bool]]:
    """Fait descendre le score du masque par mutations successives.

    Renvoie le meilleur masque rencontré (au pire, l'entrée inchangée).
    """
    current = [row[:] for row in clue]
    current_key, current_score = _objective(
        current, lengths, counts, with_cells=True
    )
    cell_map = current_score.cell_penalties or {}

    best = [row[:] for row in current]
    best_key = current_key

    accepted_since_map = 0
    evaluations = 0
    while evaluations < max_evaluations:
        if evaluations % 64 == 0 and time.time() > deadline:
            break
        candidate = _mutate(current, rng, cell_map)
        key, _ = _objective(candidate, lengths, counts)
        evaluations += 1
        if key <= current_key:
            current = candidate
            current_key = key
            if key < best_key:
                best = [row[:] for row in candidate]
                best_key = key
            accepted_since_map += 1
            if accepted_since_map >= 12:
                # Rafraîchir la carte des pénalités locales qui guide les
                # mutations (tolère un léger retard, coûte un calcul complet).
                _, refreshed = _objective(
                    current, lengths, counts, with_cells=True
                )
                cell_map = refreshed.cell_penalties or {}
                accepted_since_map = 0

    return best

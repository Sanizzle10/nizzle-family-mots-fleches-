"""Moteur de mots fléchés : grille pleine, façon magazine.

Deux phases :
1. génération d'une structure (positions des cases définitions) valide :
   chaque suite de 2+ lettres est un emplacement de mot avec une case
   définition atteignable (flèche droite ou coudée), chaque case définition
   sert au plus 2 mots, aucune lettre orpheline ;
2. remplissage des emplacements par backtracking (heuristique de
   l'emplacement le plus contraint), avec priorité aux mots thématiques.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from app.models import (
    ARROW_DOWN,
    ARROW_DOWN_RIGHT,
    ARROW_RIGHT,
    ARROW_RIGHT_DOWN,
    Entry,
    Placement,
)

CLUE_CELL = "#CLUE#"


if hasattr(int, "bit_count"):  # Python 3.10+
    def _popcount(value: int) -> int:
        return value.bit_count()
else:
    def _popcount(value: int) -> int:
        return bin(value).count("1")


class WordIndex:
    """Index binaire du dictionnaire, groupé par longueur de mot.

    Les mots d'une même longueur sont numérotés, et chaque contrainte
    (position, lettre) devient un masque d'entier. Chercher les mots
    compatibles avec un motif se réduit alors à un ET binaire — une
    opération native, là où un parcours de liste coûtait un tour de boucle
    Python par mot du dictionnaire.
    """

    def __init__(self, entries: list[Entry], max_length: int) -> None:
        pools: dict[int, list[Entry]] = {}
        for entry in entries:
            if 2 <= len(entry.word) <= max_length:
                pools.setdefault(len(entry.word), []).append(entry)

        self.words: dict[int, tuple[Entry, ...]] = {}
        self.masks: dict[int, dict[tuple[int, str], int]] = {}
        self.full: dict[int, int] = {}
        frequencies: dict[str, int] = {}

        for length, pool in pools.items():
            self.words[length] = tuple(pool)
            masks: dict[tuple[int, str], int] = {}
            for rank, entry in enumerate(pool):
                bit = 1 << rank
                for position, letter in enumerate(entry.word):
                    key = (position, letter)
                    masks[key] = masks.get(key, 0) | bit
                    frequencies[letter] = frequencies.get(letter, 0) + 1
            self.masks[length] = masks
            self.full[length] = (1 << len(pool)) - 1

        self.lengths = set(self.words)
        self.available = {
            length: len(pool) for length, pool in self.words.items()
        }
        top = max(frequencies.values()) if frequencies else 1
        self.letter_weight = {
            letter: count / top for letter, count in frequencies.items()
        }


@dataclass
class Slot:
    row: int
    col: int
    horizontal: bool
    length: int
    clue_row: int = -1
    clue_col: int = -1
    arrow: str = ARROW_RIGHT

    def cells(self) -> list[tuple[int, int]]:
        dr, dc = (0, 1) if self.horizontal else (1, 0)
        return [(self.row + i * dr, self.col + i * dc) for i in range(self.length)]


class ArrowGridGenerator:
    def __init__(
        self,
        width: int = 8,
        height: int = 13,
        seconds: float = 8.0,
        seed: int | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.seconds = seconds
        self.rng = random.Random(seed)
        self.lengths: set[int] = set()
        self.last_stats: dict = {}

    # ------------------------------------------------------------------ API

    def generate(
        self, entries: list[Entry]
    ) -> tuple[list[list[str | None]], list[Placement]]:
        deadline = time.time() + self.seconds
        index = WordIndex(entries, max(self.width, self.height))
        if not index.lengths:
            raise ValueError("Aucun mot du dictionnaire ne tient dans la grille.")

        best_score = -1
        best_pack = None
        layouts_tried = 0

        while time.time() < deadline:
            # Recalculés à chaque tour : sous forte charge, des défaillances
            # sporadiques de l'environnement (EDR/antivirus) peuvent corrompre
            # l'état du process ; des dérivés frais rendent chaque itération
            # sacrifiable.
            self.lengths = set(index.lengths)
            self.available = dict(index.available)
            try:
                layout = self._make_layout()
            except (SystemError, TypeError):
                continue
            if layout is None:
                continue

            # Mutation guidée par l'échec : quand un emplacement résiste au
            # remplissage, on y insère une case définition et on répare la
            # structure, au lieu de repartir de zéro. La limite de cases
            # mortes n'est stricte que pour la structure initiale : les
            # mutations doivent rester libres d'ajouter des cases.
            for attempt in range(14):
                if time.time() > deadline:
                    break
                try:
                    slots = self._slots_from_layout(
                        layout,
                        max_dead=None if attempt == 0 else 10_000,
                        strict=attempt == 0,
                    )
                except (SystemError, TypeError):
                    break
                if slots is None:
                    break
                layouts_tried += 1
                fill_deadline = min(
                    deadline, time.time() + max(0.5, self.seconds / 8)
                )
                try:
                    complete, assigned = self._fill(slots, index, fill_deadline)
                except (SystemError, TypeError):
                    # Défaillances sporadiques de l'interpréteur observées sous
                    # forte charge sur certains postes (EDR/antivirus) : on
                    # sacrifie la tentative, pas la génération.
                    break
                score = sum(a is not None for a in assigned)
                if complete:
                    score += 1_000_000
                if score > best_score:
                    best_score = score
                    best_pack = (layout, slots, assigned, complete)
                if complete:
                    break

                failed = [
                    slots[i]
                    for i in range(len(slots))
                    if assigned[i] is None
                ]
                if not failed:
                    break
                slot = self.rng.choice(failed)
                r, c = self.rng.choice(slot.cells())
                mutated = [row[:] for row in layout]
                mutated[r][c] = True
                try:
                    mutated = self._repair_layout(mutated)
                except (SystemError, TypeError):
                    break
                if mutated is None:
                    break
                layout = mutated

            if best_pack is not None and best_pack[3]:
                break

        for entry in entries:
            entry.placed = False

        if best_pack is None:
            empty = [[None] * self.width for _ in range(self.height)]
            self.last_stats = {"complete": False, "words": 0, "fill": 0.0}
            return empty, []

        layout, slots, assigned, complete = best_pack
        grid, placements = self._build_result(layout, slots, assigned)

        total_cells = self.width * self.height
        filled = sum(
            1 for row in grid for value in row if value is not None
        )
        self.last_stats = {
            "complete": complete,
            "words": len(placements),
            "fill": round(100.0 * filled / total_cells, 1),
            "layouts": layouts_tried,
        }
        return grid, placements

    # ------------------------------------------------------- structure

    def _make_layout(self) -> list[list[bool]] | None:
        w, h = self.width, self.height
        rng = self.rng
        clue = [[False] * w for _ in range(h)]
        clue[0][0] = True

        target = int(w * h * rng.uniform(0.22, 0.30))
        count, guard = 1, 0
        while count < target and guard < 1000:
            guard += 1
            r, c = rng.randrange(h), rng.randrange(w)
            if not clue[r][c]:
                clue[r][c] = True
                count += 1

        return self._repair_layout(clue)

    def _repair_layout(self, clue: list[list[bool]]) -> list[list[bool]] | None:
        w, h = self.width, self.height
        # Chaque passe ne corrige qu'un défaut : il en faut d'autant plus que
        # la grille est grande.
        for _ in range(max(400, w * h * 4)):
            problem = self._first_problem(clue)
            if problem is None:
                total = sum(sum(row) for row in clue)
                if total > 0.42 * w * h:
                    return None
                return clue
            r, c = problem
            if clue[r][c]:
                return None
            clue[r][c] = True
        return None

    def _runs(self, clue: list[list[bool]]):
        w, h = self.width, self.height
        runs = []
        for r in range(h):
            c = 0
            while c < w:
                if clue[r][c]:
                    c += 1
                    continue
                start = c
                while c < w and not clue[r][c]:
                    c += 1
                runs.append((r, start, True, c - start))
        for c in range(w):
            r = 0
            while r < h:
                if clue[r][c]:
                    r += 1
                    continue
                start = r
                while r < h and not clue[r][c]:
                    r += 1
                runs.append((start, c, False, r - start))
        return runs

    def _first_problem(self, clue: list[list[bool]]) -> tuple[int, int] | None:
        """Renvoie une case à transformer en case définition, ou None si la
        structure est valide."""
        rng = self.rng
        runs = self._runs(clue)
        hlen: dict[tuple[int, int], int] = {}
        vlen: dict[tuple[int, int], int] = {}
        for r, c, horizontal, length in runs:
            for i in range(length):
                cell = (r, c + i) if horizontal else (r + i, c)
                if horizontal:
                    hlen[cell] = length
                else:
                    vlen[cell] = length

        # Lettres orphelines : dans aucun mot.
        for cell, length in hlen.items():
            if length == 1 and vlen.get(cell, 0) == 1:
                return cell

        loads: dict[tuple[int, int], list] = {}
        for r, c, horizontal, length in runs:
            if length < 2:
                continue
            # Longueur sans mot correspondant dans le dictionnaire : couper.
            if length not in self.lengths:
                cut = rng.randrange(1, length)
                return (r, c + cut) if horizontal else (r + cut, c)
            # Case définition atteignable ?
            if horizontal:
                if c > 0:
                    pos = (r, c - 1)
                elif r > 0 and clue[r - 1][c]:
                    pos = (r - 1, c)
                elif r > 0:
                    return (r - 1, c) if rng.random() < 0.5 else (r, c)
                else:
                    return (r, c)
            else:
                if r > 0:
                    pos = (r - 1, c)
                elif c > 0 and clue[r][c - 1]:
                    pos = (r, c - 1)
                elif c > 0:
                    return (r, c - 1) if rng.random() < 0.5 else (r, c)
                else:
                    return (r, c)
            loads.setdefault(pos, []).append((r, c, horizontal, length))

        # Une case définition sert au plus 2 mots.
        for slot_list in loads.values():
            if len(slot_list) > 2:
                r, c, horizontal, _ = slot_list[-1]
                return (r, c)
        return None

    def _slots_from_layout(
        self,
        clue: list[list[bool]],
        max_dead: int | None = None,
        strict: bool = True,
    ) -> list[Slot] | None:
        slots: list[Slot] = []
        loads: dict[tuple[int, int], int] = {}
        for r, c, horizontal, length in self._runs(clue):
            if length < 2:
                continue
            if horizontal:
                if c > 0:
                    pos, arrow = (r, c - 1), ARROW_RIGHT
                else:
                    pos, arrow = (r - 1, c), ARROW_DOWN_RIGHT
            else:
                if r > 0:
                    pos, arrow = (r - 1, c), ARROW_DOWN
                else:
                    pos, arrow = (r, c - 1), ARROW_RIGHT_DOWN
            pr, pc = pos
            if pr < 0 or pc < 0 or not clue[pr][pc]:
                return None
            loads[pos] = loads.get(pos, 0) + 1
            if loads[pos] > 2:
                return None
            slots.append(
                Slot(r, c, horizontal, length, pr, pc, arrow)
            )

        if not slots:
            return None
        # Il faut des emplacements longs pour les mots vedettes, et pas trop
        # d'emplacements de 2 lettres (les plus durs à croiser). Ces seuils
        # sont proportionnels à la surface : une constante absolue rejetterait
        # la totalité des structures des grands formats.
        cells = self.width * self.height
        long_needed = 2 if max(self.width, self.height) >= 10 else 1
        if sum(1 for s in slots if s.length >= 6) < long_needed:
            return None
        if sum(1 for s in slots if s.length == 2) > max(10, cells // 10):
            return None
        if any(s.length not in self.lengths for s in slots):
            return None
        # Pas plus d'emplacements d'une longueur que de mots disponibles :
        # chaque mot ne sert qu'une fois par grille.
        needs: dict[int, int] = {}
        for s in slots:
            needs[s.length] = needs.get(s.length, 0) + 1
        for length, need in needs.items():
            if need > self.available.get(length, 0):
                return None
        # Trop de lettres doublement croisées rend le remplissage impossible
        # avec un dictionnaire de taille raisonnable.
        coverage: dict[tuple[int, int], int] = {}
        for slot in slots:
            for cell in slot.cells():
                coverage[cell] = coverage.get(cell, 0) + 1
        letters = len(coverage)
        if letters:
            crossed = sum(1 for v in coverage.values() if v >= 2)
            if crossed / letters > 0.78:
                return None
        # Limiter les cases définitions "mortes" (aucun mot à indiquer),
        # rendues comme des cases pleines. Proportionnel là aussi.
        if max_dead is None:
            max_dead = max(12, cells // 8)
        used_clues = {(s.clue_row, s.clue_col) for s in slots}
        dead = sum(
            1
            for r in range(self.height)
            for c in range(self.width)
            if clue[r][c] and (r, c) not in used_clues
        )
        if dead > max_dead:
            return None
        return slots

    # ------------------------------------------------------- remplissage

    def _fill(
        self,
        slots: list[Slot],
        index: WordIndex,
        deadline: float,
    ) -> tuple[bool, list[Entry | None]]:
        rng = self.rng
        letters: dict[tuple[int, int], str] = {}
        assigned: list[Entry | None] = [None] * len(slots)
        # Mots déjà employés, un masque binaire par longueur.
        used: dict[int, int] = {length: 0 for length in index.words}
        # Masque des mots compatibles avec les lettres posées, par emplacement.
        cache: list[int | None] = [None] * len(slots)

        cover: dict[tuple[int, int], list[int]] = {}
        for position, slot in enumerate(slots):
            for cell in slot.cells():
                cover.setdefault(cell, []).append(position)

        cells_of = [slot.cells() for slot in slots]
        length_of = [slot.length for slot in slots]
        weight = index.letter_weight

        def compatible(position: int) -> int:
            mask = cache[position]
            if mask is None:
                length = length_of[position]
                mask = index.full[length]
                position_masks = index.masks[length]
                for offset, cell in enumerate(cells_of[position]):
                    letter = letters.get(cell)
                    if letter is not None:
                        mask &= position_masks.get((offset, letter), 0)
                        if not mask:
                            break
                cache[position] = mask
            return mask & ~used[length_of[position]]

        def invalidate(position: int) -> None:
            for cell in cells_of[position]:
                for other in cover[cell]:
                    cache[other] = None

        best = {"count": 0, "assigned": list(assigned)}
        nodes = 0
        node_limit = 30000

        def backtrack() -> bool:
            nonlocal nodes
            nodes += 1
            if nodes > node_limit:
                raise TimeoutError
            if nodes % 128 == 0 and time.time() > deadline:
                raise TimeoutError

            # Emplacement le plus contraint d'abord ; un emplacement sans
            # candidat signale un cul-de-sac et coupe la branche aussitôt.
            chosen = -1
            fewest = -1
            open_count = 0
            for position in range(len(slots)):
                if assigned[position] is not None:
                    continue
                open_count += 1
                count = _popcount(compatible(position))
                if count == 0:
                    return False
                if fewest < 0 or count < fewest:
                    fewest = count
                    chosen = position

            if open_count == 0:
                return True

            done = len(slots) - open_count
            if done > best["count"]:
                best["count"] = done
                best["assigned"] = list(assigned)

            length = length_of[chosen]
            words = index.words[length]
            open_cells = [
                (offset, cell)
                for offset, cell in enumerate(cells_of[chosen])
                if cell not in letters
            ]

            options = []
            mask = compatible(chosen)
            while mask:
                bit = mask & -mask
                entry = words[bit.bit_length() - 1]
                # Les lettres fréquentes aux croisements laissent plus
                # d'options aux emplacements voisins.
                score = sum(
                    weight.get(entry.word[offset], 0.0)
                    for offset, _ in open_cells
                )
                options.append(
                    (
                        entry.category == "fillfoot",
                        -score + rng.uniform(0.0, 1.5),
                        entry,
                        bit,
                    )
                )
                mask ^= bit
            options.sort(key=lambda item: item[:2])

            for _, _, entry, bit in options[:24]:
                for offset, cell in open_cells:
                    letters[cell] = entry.word[offset]
                assigned[chosen] = entry
                used[length] |= bit
                invalidate(chosen)

                if backtrack():
                    return True

                for _, cell in open_cells:
                    del letters[cell]
                assigned[chosen] = None
                used[length] &= ~bit
                invalidate(chosen)
            return False

        try:
            if backtrack():
                return True, list(assigned)
        except TimeoutError:
            pass
        return False, best["assigned"]

    # ------------------------------------------------------- sortie

    def _build_result(
        self,
        layout: list[list[bool]],
        slots: list[Slot],
        assigned: list[Entry | None],
    ) -> tuple[list[list[str | None]], list[Placement]]:
        grid: list[list[str | None]] = [
            [CLUE_CELL if layout[r][c] else None for c in range(self.width)]
            for r in range(self.height)
        ]
        placements: list[Placement] = []
        for slot, entry in zip(slots, assigned):
            if entry is None:
                continue
            for i, (r, c) in enumerate(slot.cells()):
                grid[r][c] = entry.word[i]
            definition = ""
            if entry.definitions:
                definition = self.rng.choice(entry.definitions).text
            placements.append(
                Placement(
                    word=entry.word,
                    definition=definition,
                    row=slot.row,
                    col=slot.col,
                    horizontal=slot.horizontal,
                    clue_row=slot.clue_row,
                    clue_col=slot.clue_col,
                    arrow=slot.arrow,
                    display=entry.display or entry.word,
                )
            )
            entry.placed = True
        return grid, placements

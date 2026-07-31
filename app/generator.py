from __future__ import annotations

import random
import time

from app.models import Placement, WordEntry


CLUE_CELL = "#CLUE#"


class GridGenerator:
    def __init__(self, size: int = 20, seconds: float = 5.0) -> None:
        self.size = size
        self.seconds = seconds

    def generate(self, entries: list[WordEntry]) -> tuple[list[list[str | None]], list[Placement]]:
        usable = [entry for entry in entries if len(entry.word) <= self.size - 1]
        deadline = time.time() + self.seconds
        best_grid = [[None for _ in range(self.size)] for _ in range(self.size)]
        best_placements: list[Placement] = []

        while time.time() < deadline:
            grid = [[None for _ in range(self.size)] for _ in range(self.size)]
            placements: list[Placement] = []
            pool = usable[:]
            random.shuffle(pool)
            pool.sort(key=lambda entry: (len(entry.word), random.random()), reverse=True)

            for entry in pool:
                candidate = self._find_candidate(grid, placements, entry.word)
                if candidate is None:
                    continue

                row, col, horizontal = candidate
                clue_row, clue_col = self._place(grid, entry.word, row, col, horizontal)
                placements.append(
                    Placement(
                        entry.word,
                        entry.definition,
                        row,
                        col,
                        horizontal,
                        clue_row,
                        clue_col,
                    )
                )

            if self._score(grid, placements) > self._score(best_grid, best_placements):
                best_grid = [row[:] for row in grid]
                best_placements = placements[:]

        placed_words = {placement.word for placement in best_placements}
        for entry in entries:
            entry.placed = entry.word in placed_words

        return best_grid, best_placements

    def _find_candidate(self, grid, placements, word):
        if not placements:
            starts = []
            for horizontal in (True, False):
                for shift in (-2, -1, 0, 1, 2):
                    if horizontal:
                        row = self.size // 2 + shift
                        col = max(1, (self.size - len(word)) // 2)
                    else:
                        row = max(1, (self.size - len(word)) // 2)
                        col = self.size // 2 + shift
                    if self._can_place(grid, word, row, col, horizontal):
                        starts.append((row, col, horizontal))
            return random.choice(starts) if starts else None

        candidates = []
        for r in range(self.size):
            for c in range(self.size):
                existing = grid[r][c]
                if not existing or existing == CLUE_CELL:
                    continue

                for index, letter in enumerate(word):
                    if letter != existing:
                        continue

                    for horizontal in (True, False):
                        row = r if horizontal else r - index
                        col = c - index if horizontal else c
                        if self._can_place(grid, word, row, col, horizontal):
                            candidates.append((row, col, horizontal))

        if not candidates:
            return None

        candidates = list(dict.fromkeys(candidates))
        candidates.sort(
            key=lambda item: self._candidate_score(grid, word, *item),
            reverse=True,
        )
        return random.choice(candidates[: min(8, len(candidates))])

    def _can_place(self, grid, word, row, col, horizontal):
        dr, dc = (0, 1) if horizontal else (1, 0)
        clue_row = row - dr
        clue_col = col - dc
        end_row = row + (len(word) - 1) * dr
        end_col = col + (len(word) - 1) * dc

        if (
            row < 0
            or col < 0
            or end_row >= self.size
            or end_col >= self.size
            or clue_row < 0
            or clue_col < 0
        ):
            return False

        if grid[clue_row][clue_col] not in (None, CLUE_CELL):
            return False

        crossings = 0
        for index, letter in enumerate(word):
            r = row + index * dr
            c = col + index * dc
            existing = grid[r][c]

            if existing == CLUE_CELL:
                return False
            if existing not in (None, letter):
                return False

            if existing == letter:
                crossings += 1
            elif horizontal:
                if (
                    (r > 0 and grid[r - 1][c] not in (None, CLUE_CELL))
                    or (r + 1 < self.size and grid[r + 1][c] not in (None, CLUE_CELL))
                ):
                    return False
            else:
                if (
                    (c > 0 and grid[r][c - 1] not in (None, CLUE_CELL))
                    or (c + 1 < self.size and grid[r][c + 1] not in (None, CLUE_CELL))
                ):
                    return False

        after_row = row + len(word) * dr
        after_col = col + len(word) * dc
        if (
            0 <= after_row < self.size
            and 0 <= after_col < self.size
            and grid[after_row][after_col] not in (None, CLUE_CELL)
        ):
            return False

        return not placements_exist(grid) or crossings > 0

    def _place(self, grid, word, row, col, horizontal):
        dr, dc = (0, 1) if horizontal else (1, 0)
        clue_row = row - dr
        clue_col = col - dc
        grid[clue_row][clue_col] = CLUE_CELL

        for index, letter in enumerate(word):
            grid[row + index * dr][col + index * dc] = letter

        return clue_row, clue_col

    def _candidate_score(self, grid, word, row, col, horizontal):
        dr, dc = (0, 1) if horizontal else (1, 0)
        crossings = sum(
            1
            for index, letter in enumerate(word)
            if grid[row + index * dr][col + index * dc] == letter
        )

        occupied = [
            (r, c)
            for r in range(self.size)
            for c in range(self.size)
            if grid[r][c] is not None
        ]
        added = [(row - dr, col - dc)] + [
            (row + index * dr, col + index * dc)
            for index in range(len(word))
        ]
        points = occupied + added
        min_r = min(r for r, _ in points)
        max_r = max(r for r, _ in points)
        min_c = min(c for _, c in points)
        max_c = max(c for _, c in points)
        area = (max_r - min_r + 1) * (max_c - min_c + 1)

        return crossings * 500 - area * 3

    def _score(self, grid, placements):
        occupied = [
            (r, c)
            for r in range(self.size)
            for c in range(self.size)
            if grid[r][c] is not None
        ]
        if not occupied:
            return -1

        min_r = min(r for r, _ in occupied)
        max_r = max(r for r, _ in occupied)
        min_c = min(c for _, c in occupied)
        max_c = max(c for _, c in occupied)
        area = (max_r - min_r + 1) * (max_c - min_c + 1)
        empty_inside = area - len(occupied)
        density = len(occupied) / area

        return (
            len(placements) * 100000
            + density * 10000
            - empty_inside * 120
            - area * 8
        )


def placements_exist(grid) -> bool:
    return any(cell not in (None, CLUE_CELL) for row in grid for cell in row)

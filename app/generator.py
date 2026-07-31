from __future__ import annotations

import random
import time

from app.models import Placement, WordEntry


class GridGenerator:
    def __init__(self, size: int = 20, seconds: float = 5.0) -> None:
        self.size = size
        self.seconds = seconds

    def generate(self, entries: list[WordEntry]) -> tuple[list[list[str | None]], list[Placement]]:
        usable = [entry for entry in entries if len(entry.word) <= self.size]
        deadline = time.time() + self.seconds
        best_grid = [[None for _ in range(self.size)] for _ in range(self.size)]
        best_placements: list[Placement] = []

        while time.time() < deadline:
            grid = [[None for _ in range(self.size)] for _ in range(self.size)]
            placements: list[Placement] = []
            pool = usable[:]
            random.shuffle(pool)
            pool.sort(key=lambda entry: len(entry.word), reverse=True)

            for entry in pool:
                candidate = self._find_candidate(grid, placements, entry.word)
                if candidate is None:
                    continue
                row, col, horizontal = candidate
                self._place(grid, entry.word, row, col, horizontal)
                placements.append(Placement(entry.word, entry.definition, row, col, horizontal))

            if self._score(grid, placements) > self._score(best_grid, best_placements):
                best_grid = grid
                best_placements = placements

        placed_words = {placement.word for placement in best_placements}
        for entry in entries:
            entry.placed = entry.word in placed_words

        return best_grid, best_placements

    def _find_candidate(self, grid, placements, word):
        if not placements:
            row = self.size // 2
            col = max(0, (self.size - len(word)) // 2)
            return (row, col, True) if self._can_place(grid, word, row, col, True) else None

        candidates = []
        for r in range(self.size):
            for c in range(self.size):
                existing = grid[r][c]
                if not existing:
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
        candidates.sort(key=lambda item: self._candidate_score(grid, word, *item), reverse=True)
        return random.choice(candidates[: min(4, len(candidates))])

    def _can_place(self, grid, word, row, col, horizontal):
        dr, dc = (0, 1) if horizontal else (1, 0)
        end_row = row + (len(word) - 1) * dr
        end_col = col + (len(word) - 1) * dc
        if row < 0 or col < 0 or end_row >= self.size or end_col >= self.size:
            return False

        crossings = 0
        for index, letter in enumerate(word):
            r = row + index * dr
            c = col + index * dc
            existing = grid[r][c]
            if existing not in (None, letter):
                return False
            if existing == letter:
                crossings += 1
            elif horizontal:
                if (r > 0 and grid[r - 1][c]) or (r + 1 < self.size and grid[r + 1][c]):
                    return False
            else:
                if (c > 0 and grid[r][c - 1]) or (c + 1 < self.size and grid[r][c + 1]):
                    return False

        before = (row - dr, col - dc)
        after = (row + len(word) * dr, col + len(word) * dc)
        for r, c in (before, after):
            if 0 <= r < self.size and 0 <= c < self.size and grid[r][c]:
                return False

        return not placements_exist(grid) or crossings > 0

    def _place(self, grid, word, row, col, horizontal):
        dr, dc = (0, 1) if horizontal else (1, 0)
        for index, letter in enumerate(word):
            grid[row + index * dr][col + index * dc] = letter

    def _candidate_score(self, grid, word, row, col, horizontal):
        dr, dc = (0, 1) if horizontal else (1, 0)
        crossings = sum(
            1 for index, letter in enumerate(word)
            if grid[row + index * dr][col + index * dc] == letter
        )
        center = self.size / 2
        distance = abs(row - center) + abs(col - center)
        return crossings * 100 - distance

    def _score(self, grid, placements):
        occupied = [(r, c) for r in range(self.size) for c in range(self.size) if grid[r][c]]
        if not occupied:
            return -1
        min_r = min(r for r, _ in occupied)
        max_r = max(r for r, _ in occupied)
        min_c = min(c for _, c in occupied)
        max_c = max(c for _, c in occupied)
        area = (max_r - min_r + 1) * (max_c - min_c + 1)
        density = len(occupied) / area
        return len(placements) * 1000 + density * 100 - area


def placements_exist(grid) -> bool:
    return any(cell for row in grid for cell in row)

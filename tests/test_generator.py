from pathlib import Path

import pytest

from app.dictionary import load_dictionary
from app.generator import CLUE_CELL, ArrowGridGenerator
from app.models import (
    ARROW_DOWN,
    ARROW_DOWN_RIGHT,
    ARROW_RIGHT,
    ARROW_RIGHT_DOWN,
)

DATA = Path(__file__).resolve().parent.parent / "data"
LEXICON = DATA / "lexique_foot_master.csv"
SMALL_LEXICON = DATA / "lexique_foot_v0.csv"


@pytest.fixture(scope="module")
def entries():
    if not LEXICON.exists():
        pytest.skip("lexique maître absent")
    return load_dictionary(LEXICON)


@pytest.fixture(scope="module")
def generated(entries):
    generator = ArrowGridGenerator(width=8, height=13, seconds=30.0, seed=42)
    grid, placements = generator.generate(entries)
    return generator, grid, placements


def runs_of(grid, horizontal):
    rows, cols = len(grid), len(grid[0])
    runs = []
    outer, inner = (rows, cols) if horizontal else (cols, rows)
    for a in range(outer):
        b = 0
        while b < inner:
            r, c = (a, b) if horizontal else (b, a)
            if grid[r][c] in (None, CLUE_CELL):
                b += 1
                continue
            start = b
            word = ""
            while b < inner:
                r, c = (a, b) if horizontal else (b, a)
                if grid[r][c] in (None, CLUE_CELL):
                    break
                word += grid[r][c]
                b += 1
            if len(word) >= 2:
                runs.append(((a, start) if horizontal else (start, a), word))
    return runs


def test_grid_is_complete(generated):
    generator, grid, placements = generated
    assert generator.last_stats["complete"], (
        "la grille devrait être pleine avec le dictionnaire complet : "
        f"{generator.last_stats}"
    )
    for row in grid:
        for value in row:
            assert value is not None


def test_small_dictionary_still_fills():
    """Le repli adaptatif doit préserver le remplissage même avec un
    dictionnaire pauvre (337 mots)."""
    if not SMALL_LEXICON.exists():
        pytest.skip("lexique de développement absent")
    small = load_dictionary(SMALL_LEXICON)
    generator = ArrowGridGenerator(width=8, height=13, seconds=30.0, seed=42)
    generator.generate(small)
    assert generator.last_stats["complete"], generator.last_stats


def test_every_run_is_a_placed_word(generated, entries):
    _, grid, placements = generated
    words = {entry.word for entry in entries}
    placed = {
        ((p.row, p.col) if p.horizontal else (p.row, p.col), p.word, p.horizontal)
        for p in placements
    }
    for horizontal in (True, False):
        for (r, c), word in runs_of(grid, horizontal):
            assert word in words, f"suite {word} absente du dictionnaire"
            assert ((r, c), word, horizontal) in placed


def test_no_duplicate_words(generated):
    _, _, placements = generated
    words = [p.word for p in placements]
    assert len(words) == len(set(words))


def test_clue_cells_hold_at_most_two_clues(generated):
    _, _, placements = generated
    counts = {}
    for p in placements:
        key = (p.clue_row, p.clue_col)
        counts[key] = counts.get(key, 0) + 1
    assert counts and max(counts.values()) <= 2


def test_arrows_point_from_clue_to_word(generated):
    _, grid, placements = generated
    for p in placements:
        assert grid[p.clue_row][p.clue_col] == CLUE_CELL
        if p.arrow == ARROW_RIGHT:
            assert p.horizontal and (p.clue_row, p.clue_col) == (p.row, p.col - 1)
        elif p.arrow == ARROW_DOWN_RIGHT:
            assert p.horizontal and (p.clue_row, p.clue_col) == (p.row - 1, p.col)
        elif p.arrow == ARROW_DOWN:
            assert not p.horizontal and (p.clue_row, p.clue_col) == (p.row - 1, p.col)
        elif p.arrow == ARROW_RIGHT_DOWN:
            assert not p.horizontal and (p.clue_row, p.clue_col) == (p.row, p.col - 1)
        else:
            pytest.fail(f"flèche inconnue : {p.arrow}")


def test_every_placement_has_definition(generated):
    _, _, placements = generated
    for p in placements:
        assert p.definition.strip()

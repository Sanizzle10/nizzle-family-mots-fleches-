from pathlib import Path

import pytest

from app.dictionary import load_dictionary
from app.generator import CLUE_CELL
from app.parallel import generate_batch, generate_best, worker_count

LEXICON = Path(__file__).resolve().parent.parent / "data" / "lexique_foot_master.csv"


@pytest.fixture(scope="module")
def entries():
    if not LEXICON.exists():
        pytest.skip("lexique maître absent")
    return load_dictionary(LEXICON)


def test_worker_count_respects_cap():
    assert worker_count(1) == 1
    assert worker_count(5) == 5
    assert worker_count() >= 1
    assert worker_count(cap=4) <= 4


def test_generate_best_single_worker(entries):
    grid, placements, stats = generate_best(
        entries, seconds=10.0, workers=1, seed_base=3
    )
    assert stats["complete"], stats
    assert placements
    for row in grid:
        for value in row:
            assert value is not None


def test_generate_best_marks_placed_entries(entries):
    grid, placements, stats = generate_best(
        entries, seconds=10.0, workers=2, seed_base=11
    )
    placed_words = {placement.word for placement in placements}
    marked = {entry.word for entry in entries if entry.placed}
    assert marked == placed_words
    assert placed_words


def test_generate_batch_returns_distinct_grids(entries):
    results = generate_batch(entries, count=3, seconds=8.0, seed_base=5)
    assert len(results) == 3
    signatures = {
        "".join(str(value) for row in grid for value in row)
        for grid, _, _ in results
    }
    assert len(signatures) == 3, "les grilles d'un lot doivent différer"
    for grid, placements, stats in results:
        assert placements
        letters = {
            value
            for row in grid
            for value in row
            if value not in (None, CLUE_CELL)
        }
        assert letters

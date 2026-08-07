"""Critères « grille parfaite », mesurés sur le chemin réel de l'application
(génération parallèle) avec le dictionnaire complet.

Une grille est acceptée si elle est pleine, valide au sens du score de
masque, et si son profil éditorial approche celui d'une grille de magazine.
Les seuils laissent une marge sur les valeurs mesurées (médiane 5,5k de
pénalité et 25 % de mots courts en 8x13) pour absorber la variance.
"""

from pathlib import Path

import pytest

from app.dictionary import load_dictionary
from app.generator import CLUE_CELL, WordIndex
from app.mask_score import score_mask
from app.parallel import generate_best

LEXICON = (
    Path(__file__).resolve().parent.parent / "data" / "lexique_foot_master.csv"
)


@pytest.fixture(scope="module")
def entries():
    if not LEXICON.exists():
        pytest.skip("lexique maître absent")
    return load_dictionary(LEXICON)


@pytest.fixture(scope="module")
def grille_8x13(entries):
    return generate_best(
        entries, width=8, height=13, seconds=25.0, seed_base=7
    )


def layout_of(grid):
    return [[value == CLUE_CELL for value in row] for row in grid]


def test_8x13_pleine_et_valide(grille_8x13, entries):
    grid, placements, stats = grille_8x13
    assert stats.get("complete"), stats
    index = WordIndex(entries, 13)
    score = score_mask(layout_of(grid), index.lengths)
    assert score.valid, score.details


def test_8x13_profil_magazine(grille_8x13):
    grid, placements, stats = grille_8x13
    courts = sum(1 for p in placements if len(p.word) <= 3)
    assert courts / len(placements) <= 0.38, (
        f"{courts}/{len(placements)} mots de 2-3 lettres"
    )
    longs = sum(1 for p in placements if len(p.word) >= 6)
    assert longs >= 2, "il faut des mots vedettes de 6 lettres et plus"


def test_8x13_penalite_sous_le_seuil(grille_8x13, entries):
    grid, placements, stats = grille_8x13
    index = WordIndex(entries, 13)
    score = score_mask(layout_of(grid), index.lengths)
    assert score.total <= 13_000, score.details


def test_8x13_peu_de_cases_mortes(grille_8x13):
    grid, placements, stats = grille_8x13
    clue_cells = {
        (r, c)
        for r, row in enumerate(grid)
        for c, value in enumerate(row)
        if value == CLUE_CELL
    }
    used = {(p.clue_row, p.clue_col) for p in placements}
    assert len(clue_cells - used) <= 3, "trop de cases définitions vides"


def test_10x15_pleine(entries):
    grid, placements, stats = generate_best(
        entries, width=10, height=15, seconds=25.0, seed_base=31
    )
    assert stats.get("complete"), stats
    courts = sum(1 for p in placements if len(p.word) <= 3)
    assert courts / len(placements) <= 0.45


def test_13x20_pleine(entries):
    grid, placements, stats = generate_best(
        entries, width=13, height=20, seconds=25.0, seed_base=13
    )
    assert stats.get("complete"), stats

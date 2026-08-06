from app.mask_score import (
    PENALTY_ARROW,
    PENALTY_DEAD_END,
    PENALTY_ORPHAN,
    cluster_penalty,
    score_mask,
    word_length_penalty,
)


def mask(*rows: str) -> list[list[bool]]:
    """'#' = case définition, '.' = case lettre."""
    return [[ch == "#" for ch in row] for row in rows]


def test_word_length_penalties_favor_five_and_six():
    assert word_length_penalty(5) == 0
    assert word_length_penalty(6) == 0
    assert word_length_penalty(2) == 650
    assert word_length_penalty(3) == 100
    assert word_length_penalty(2) > word_length_penalty(9)
    assert word_length_penalty(18) > word_length_penalty(15)


def test_orphan_letter_is_invalid():
    score = score_mask(mask(
        "###",
        "#.#",
        "###",
    ))
    assert not score.valid
    assert score.details["orphelines"] == PENALTY_ORPHAN


def test_two_letter_word_costs_650():
    score = score_mask(mask("#.."))
    assert score.details["longueurs"] == 650
    # lettres couvertes une seule fois, en bord haut : 75 chacune
    assert score.details["couverture"] == 150
    assert score.valid


def test_five_letter_word_costs_nothing_in_lengths():
    score = score_mask(mask("#....."))
    assert score.details["longueurs"] == 0


def test_unavailable_length_is_invalid():
    score = score_mask(mask("#....."), available_lengths={2, 3, 4})
    assert score.details["longueurs_indisponibles"] > 0
    assert not score.valid


def test_cluster_block_penalized_more_than_scattered():
    # Bloc 2x2 loin des bords : amas de taille 4, étendue 2 -> 542.
    block = score_mask(mask(
        "......",
        "......",
        "..##..",
        "..##..",
        "......",
        "......",
    ))
    scattered = score_mask(mask(
        "......",
        "..#...",
        "......",
        "....#.",
        ".#....",
        "......",
    ))
    assert block.details["amas"] == 542
    assert scattered.details["amas"] == 0
    assert block.details["amas"] > scattered.details["amas"]


def test_border_cluster_cells_count_half():
    # Amas de 2 collé au bord gauche : taille comptée 1,0 -> pas de pénalité.
    border = score_mask(mask(
        "......",
        "#.....",
        "#.....",
        "......",
    ))
    inland = score_mask(mask(
        "......",
        "..#...",
        "..#...",
        "......",
    ))
    assert border.details["amas"] == 0
    assert inland.details["amas"] == 150


def test_cluster_penalty_interpolates_fractional_sizes():
    assert cluster_penalty(1.0, 1) == 0
    assert 0 < cluster_penalty(1.5, 2) < cluster_penalty(2.0, 2)
    assert cluster_penalty(8, 8) > cluster_penalty(7, 7)


def test_dead_end_detected():
    # La lettre en (2, 2) a trois voisines non-lettre (bas, gauche, droite).
    score = score_mask(mask(
        "#....",
        "#....",
        ".#.#.",
        "..#..",
    ))
    assert score.details["culs_de_sac"] >= PENALTY_DEAD_END


def test_overloaded_clue_cell_is_invalid():
    # (0,0) sert trois mots : deux horizontaux (lignes 0 et 1 via flèche
    # coudée) et un vertical (colonne 1).
    score = score_mask(mask(
        "#..",
        "...",
    ))
    assert score.details["fleches"] >= PENALTY_ARROW
    assert not score.valid


def test_crossed_cells_cost_nothing():
    # Bloc 3x3 de lettres bordé de cases définitions : chaque lettre est
    # couverte horizontalement ET verticalement -> zéro pénalité couverture.
    score = score_mask(mask(
        "####",
        "#...",
        "#...",
        "#...",
    ))
    assert score.details["orphelines"] == 0
    assert score.details["couverture"] == 0

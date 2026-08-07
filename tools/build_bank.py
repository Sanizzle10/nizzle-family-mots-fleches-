# -*- coding: utf-8 -*-
"""Fabrique la banque de grilles JSON de la webapp (V3).

Usage :
    python tools/build_bank.py [--out web/public/data] [--seed 20260807]
        [--mix 8x13:150,10x15:35,13x20:15] [--seconds 25]

Chaque grille est un fichier JSON autonome (solution + cases définitions),
plus un index `index.json` (catalogue + ordre de la grille du jour).

Les définitions sont RE-tirées ici, pas reprises du moteur : la banque
équilibre leur usage global (chaque variante d'un mot sert à tour de rôle)
et préfère le registre « joueur » à égalité — deux grilles qui partagent un
mot n'affichent donc pas la même définition, tant qu'il y a des variantes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from app.dictionary import load_dictionary  # noqa: E402
from app.generator import CLUE_CELL, WordIndex  # noqa: E402
from app.mask_score import score_mask  # noqa: E402
from app.models import Entry, Placement  # noqa: E402
from app.parallel import generate_batch, generate_best  # noqa: E402

LEXICON = REPO / "data" / "lexique_foot_master.csv"

# Au-delà : la grille est écartée même pleine (structure ratée).
PENALTY_CAP = {104: 13_000, 150: 20_000, 260: 60_000}


def parse_mix(text: str) -> list[tuple[int, int, int]]:
    """"8x13:150,10x15:35" -> [(8, 13, 150), (10, 15, 35)]."""
    result = []
    for part in text.split(","):
        size, _, count = part.strip().partition(":")
        width, _, height = size.partition("x")
        result.append((int(width), int(height), int(count)))
    return result


def pick_definitions(
    placements: list[Placement],
    by_word: dict[str, Entry],
    usage: Counter,
    rng: random.Random,
) -> list[dict]:
    """Choisit une définition par mot en équilibrant l'usage sur la banque."""
    chosen = []
    for placement in placements:
        entry = by_word[placement.word]
        floor = min(usage[(entry.word, i)] for i in range(len(entry.definitions)))
        candidates = [
            i
            for i in range(len(entry.definitions))
            if usage[(entry.word, i)] == floor
        ]
        joueur = [
            i for i in candidates if entry.definitions[i].register == "joueur"
        ]
        index = rng.choice(joueur or candidates)
        usage[(entry.word, index)] += 1
        definition = entry.definitions[index]
        chosen.append(
            {
                "placement": placement,
                "text": definition.text,
                "level": definition.level,
                "display": entry.display,
            }
        )
    return chosen


def grid_to_json(
    grid_id: str,
    grid: list[list[str | None]],
    placements: list[Placement],
    chosen: list[dict],
    penalty: int,
) -> dict:
    height, width = len(grid), len(grid[0])
    solution = [
        "".join("#" if cell == CLUE_CELL else cell for cell in row)
        for row in grid
    ]

    cells: dict[tuple[int, int], list[dict]] = {}
    for item in chosen:
        p: Placement = item["placement"]
        cells.setdefault((p.clue_row, p.clue_col), []).append(
            {
                "text": item["text"],
                "arrow": p.arrow,
                "row": p.row,
                "col": p.col,
                "horizontal": p.horizontal,
                "len": len(p.word),
                "word": p.word,
                "display": item["display"],
            }
        )

    clues = []
    for (row, col), slots in sorted(cells.items()):
        # Convention maquette : l'indice du mot horizontal en premier (haut).
        slots.sort(key=lambda s: not s["horizontal"])
        clues.append({"row": row, "col": col, "slots": slots})

    levels = [item["level"] for item in chosen]
    mean = sum(levels) / len(levels)
    difficulty = 1 if mean <= 1.4 else (2 if mean <= 2.1 else 3)

    return {
        "id": grid_id,
        "width": width,
        "height": height,
        "difficulty": difficulty,
        "penalty": penalty,
        "words": len(placements),
        "solution": solution,
        "clues": clues,
    }


def collect_format(
    entries: list[Entry],
    lengths: set[int],
    width: int,
    height: int,
    wanted: int,
    seconds: float,
    seed: int,
    seen_hashes: set[str],
) -> list[tuple[list[list[str | None]], list[Placement], int]]:
    """Génère `wanted` grilles pleines, valides et toutes différentes."""
    cells_total = width * height
    cap = PENALTY_CAP.get(cells_total, 60_000)
    kept: list = []
    round_no = 0
    # Lots larges d'abord (les recherches indépendantes réussissent souvent),
    # complément grille par grille en parallèle pour les récalcitrantes.
    while len(kept) < wanted and round_no < 12:
        missing = wanted - len(kept)
        batch_size = max(missing, 8) if round_no < 6 else 0
        round_seed = seed + round_no * 100_003
        if batch_size:
            results = generate_batch(
                entries, batch_size, width=width, height=height,
                seconds=seconds, seed_base=round_seed,
            )
        else:
            results = [
                generate_best(
                    entries, width=width, height=height,
                    seconds=seconds, seed_base=round_seed + i * 7919,
                )
                for i in range(missing)
            ]
        for grid, placements, stats in results:
            if len(kept) >= wanted or not stats.get("complete"):
                continue
            digest = hashlib.sha1(
                "".join(
                    "".join("#" if c == CLUE_CELL else c for c in row)
                    for row in grid
                ).encode()
            ).hexdigest()
            if digest in seen_hashes:
                continue
            layout = [[c == CLUE_CELL for c in row] for row in grid]
            score = score_mask(layout, lengths)
            if not score.valid or score.total > cap:
                continue
            seen_hashes.add(digest)
            kept.append((grid, placements, score.total))
        round_no += 1
        print(
            f"  {width}x{height} : {len(kept)}/{wanted} après le tour {round_no}",
            flush=True,
        )
    return kept


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO / "web" / "public" / "data"))
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--mix", default="8x13:150,10x15:35,13x20:15")
    parser.add_argument("--seconds", type=float, default=25.0)
    args = parser.parse_args()

    out = Path(args.out)
    grids_dir = out / "grilles"
    grids_dir.mkdir(parents=True, exist_ok=True)

    entries = load_dictionary(LEXICON)
    by_word = {entry.word: entry for entry in entries}
    rng = random.Random(args.seed)
    usage: Counter = Counter()
    seen_hashes: set[str] = set()

    catalogue = []
    for width, height, wanted in parse_mix(args.mix):
        lengths = WordIndex(entries, max(width, height)).lengths
        print(f"Format {width}x{height} : objectif {wanted}", flush=True)
        produced = collect_format(
            entries, lengths, width, height, wanted,
            args.seconds, args.seed + width * 31 + height, seen_hashes,
        )
        for seq, (grid, placements, penalty) in enumerate(produced, start=1):
            grid_id = f"{width}x{height}-{seq:03d}"
            chosen = pick_definitions(placements, by_word, usage, rng)
            data = grid_to_json(grid_id, grid, placements, chosen, penalty)
            path = grids_dir / f"{grid_id}.json"
            path.write_text(
                json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            catalogue.append(
                {
                    "id": grid_id,
                    "file": f"grilles/{grid_id}.json",
                    "width": width,
                    "height": height,
                    "difficulty": data["difficulty"],
                    "words": data["words"],
                }
            )

    daily = [item["id"] for item in catalogue]
    rng.shuffle(daily)
    index = {
        "version": 1,
        "generated": dt.date.today().isoformat(),
        "dailyStart": dt.date.today().isoformat(),
        "dailyOrder": daily,
        "grids": catalogue,
    }
    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    reuse = Counter()
    for (word, _), count in usage.items():
        reuse[word] += count
    top = reuse.most_common(5)
    print(f"\n{len(catalogue)} grilles écrites dans {out}")
    print("Mots les plus réutilisés :",
          ", ".join(f"{w} ({n})" for w, n in top))


if __name__ == "__main__":
    main()

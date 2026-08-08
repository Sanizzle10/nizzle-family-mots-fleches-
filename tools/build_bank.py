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


from app.definitions import (  # noqa: E402
    appliquer_exclusions,
    charger_exclusions,
    nettoyer_definition,
)

def parse_mix(text: str) -> list[tuple[int, int, int]]:
    """"8x13:150,10x15:35" -> [(8, 13, 150), (10, 15, 35)]."""
    result = []
    for part in text.split(","):
        size, _, count = part.strip().partition(":")
        width, _, height = size.partition("x")
        result.append((int(width), int(height), int(count)))
    return result


# Répartition des grilles par niveau visé : surtout du facile (retour
# joueur : le niveau 2 est déjà très dur).
CIBLES_NIVEAU = [1] * 6 + [2] * 3 + [3]

# Lisibilité : capacité approximative d'une case définition à l'écran
# (~3 lignes de ~12 caractères par moitié de case). Une définition seule
# dispose de toute la case, deux définitions se la partagent.
MAX_CHARS_SIMPLE = 70
MAX_CHARS_DOUBLE = 32


def pick_definitions(
    placements: list[Placement],
    by_word: dict[str, Entry],
    usage: Counter,
    rng: random.Random,
    cible: int = 1,
) -> list[dict]:
    """Choisit une définition par mot : niveau visé d'abord, puis équilibre
    d'usage sur la banque, puis registre « joueur » à égalité."""
    charge = Counter((p.clue_row, p.clue_col) for p in placements)
    chosen = []
    for placement in placements:
        entry = by_word[placement.word]
        budget = (
            MAX_CHARS_DOUBLE
            if charge[(placement.clue_row, placement.clue_col)] >= 2
            else MAX_CHARS_SIMPLE
        )
        textes = [
            nettoyer_definition(d.text, entry.word) for d in entry.definitions
        ]
        # 1. Lisibilité d'abord : la définition doit tenir dans la case.
        tous = [i for i in range(len(textes)) if len(textes[i]) <= budget]
        if not tous:
            tous = [min(range(len(textes)), key=lambda i: len(textes[i]))]
        # 2. Le niveau le plus proche de la cible (en dessous de préférence).
        def ecart_niveau(i):
            level = entry.definitions[i].level
            return abs(level - cible) + (0.5 if level > cible else 0)

        ecart = min(ecart_niveau(i) for i in tous)
        du_niveau = [i for i in tous if ecart_niveau(i) == ecart]
        # 3. Grilles faciles : la clarté prime — registre factuel (pays,
        # club, grammaire) AVANT la rotation d'usage. Grilles relevées :
        # rotation d'abord, humour « joueur » à égalité.
        if cible == 1:
            factuels = [
                i for i in du_niveau
                if entry.definitions[i].register == "factuel"
            ]
            bassin = factuels or du_niveau
            floor = min(usage[(entry.word, i)] for i in bassin)
            candidates = [i for i in bassin if usage[(entry.word, i)] == floor]
            index = rng.choice(candidates)
        else:
            floor = min(usage[(entry.word, i)] for i in du_niveau)
            candidates = [
                i for i in du_niveau if usage[(entry.word, i)] == floor
            ]
            joueur = [
                i for i in candidates
                if entry.definitions[i].register == "joueur"
            ]
            index = rng.choice(joueur or candidates)
        usage[(entry.word, index)] += 1
        chosen.append(
            {
                "placement": placement,
                "text": textes[index],
                "level": entry.definitions[index].level,
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
    difficulty: int,
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

    # La difficulté affichée est la CIBLE du tirage, pas la moyenne obtenue :
    # 39 % des mots n'ont pas de définition de niveau 1, la moyenne d'une
    # grille facile plafonne donc vers 1,5 — mais c'est bien la grille la
    # plus facile possible avec le lexique actuel.
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
    surplus: float = 1.25,
) -> list[tuple[list[list[str | None]], list[Placement], int]]:
    """Génère un excédent de grilles pleines, valides et toutes
    différentes, puis ne garde que les `wanted` mieux notées."""
    if wanted <= 0:
        return []
    cells_total = width * height
    cap = PENALTY_CAP.get(cells_total, 60_000)
    # Sur les grands formats la génération est lente : pas d'excédent.
    objectif = wanted if cells_total > 200 else max(wanted, int(wanted * surplus))
    kept: list = []
    round_no = 0
    tours_secs = 0
    # Lots de taille bornée : la progression s'affiche régulièrement et un
    # crash machine ne coûte qu'un tour (relancé avec une autre graine).
    while len(kept) < objectif and round_no < 80 and tours_secs < 3:
        missing = objectif - len(kept)
        batch_size = min(max(missing, 8), 200)
        round_seed = seed + round_no * 100_003
        avant = len(kept)
        try:
            if round_no < 40:
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
                    for i in range(min(missing, 24))
                ]
        except Exception as exc:
            print(f"  {width}x{height} : tour {round_no + 1} perdu "
                  f"({type(exc).__name__}), on relance", flush=True)
            round_no += 1
            continue
        for grid, placements, stats in results:
            if len(kept) >= objectif or not stats.get("complete"):
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
        tours_secs = tours_secs + 1 if len(kept) == avant else 0
        round_no += 1
        print(
            f"  {width}x{height} : {len(kept)}/{objectif} après le tour "
            f"{round_no}",
            flush=True,
        )
    # Sélection qualité : pénalité croissante, on garde les meilleures.
    kept.sort(key=lambda item: item[2])
    return kept[:wanted]


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

    charge = load_dictionary(LEXICON)
    defs_avant = sum(len(e.definitions) for e in charge)
    entries = appliquer_exclusions(charge)
    print(f"Exclusions : "
          f"{defs_avant - sum(len(e.definitions) for e in entries)} "
          f"définitions écartées, {len(charge) - len(entries)} mots sans "
          "définition restante")
    # Grilles faciles : uniquement des mots ayant une définition niveau 1
    # (joueurs, équipes et termes connus).
    connus = [e for e in entries if any(d.level == 1 for d in e.definitions)]
    by_word = {entry.word: entry for entry in entries}
    rng = random.Random(args.seed)
    usage: Counter = Counter()
    seen_hashes: set[str] = set()
    part_facile = CIBLES_NIVEAU.count(1) / len(CIBLES_NIVEAU)
    cycle_dur = [c for c in CIBLES_NIVEAU if c != 1]

    catalogue = []
    for width, height, wanted in parse_mix(args.mix):
        lengths = WordIndex(entries, max(width, height)).lengths
        lengths_connus = WordIndex(connus, max(width, height)).lengths
        objectif_facile = round(wanted * part_facile)
        print(f"Format {width}x{height} : objectif {wanted} "
              f"(dont {objectif_facile} faciles)", flush=True)
        faciles = collect_format(
            connus, lengths_connus, width, height, objectif_facile,
            args.seconds, args.seed + width * 31 + height, seen_hashes,
        )
        # Si les mots connus ne suffisent pas (grands formats), le manque
        # est produit avec le dictionnaire complet, en difficulté 2.
        durs = collect_format(
            entries, lengths, width, height, wanted - len(faciles),
            args.seconds, args.seed + width * 131 + height, seen_hashes,
        )
        produced = [(g, p, pen, 1) for g, p, pen in faciles] + [
            (g, p, pen, cycle_dur[i % len(cycle_dur)])
            for i, (g, p, pen) in enumerate(durs)
        ]
        for seq, (grid, placements, penalty, cible) in enumerate(
            produced, start=1
        ):
            grid_id = f"{width}x{height}-{seq:03d}"
            chosen = pick_definitions(placements, by_word, usage, rng, cible)
            data = grid_to_json(
                grid_id, grid, placements, chosen, penalty, cible
            )
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

    # Grille du jour : format magazine (8 colonnes), jamais « difficile ».
    daily = [
        item["id"]
        for item in catalogue
        if item["width"] == 8 and item["difficulty"] <= 2
    ] or [item["id"] for item in catalogue]
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

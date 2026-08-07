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
import re
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


# « Trois lettres qui... » : redondant à l'écran, la case donne déjà le
# nombre de lettres. On retire le préfixe et la cheville qui le suit.
_NOMBRES = (
    "deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize"
    "|quatorze|quinze"
)
_PREFIXE_LETTRES = re.compile(
    rf"^\s*(?:{_NOMBRES})\s+lettres\s*(?:qui\s+|qu[''`]\s*|que\s+|et\s+|,\s*|:\s*)?",
    re.IGNORECASE,
)


# Ces définitions étaient accordées avec « X lettres » (féminin pluriel) :
# une fois le préfixe retiré, il faut ré-accorder au mot-réponse (masculin
# par convention, pluriel si le mot finit par S). Dans le doute, on garde le
# libellé d'origine : un préfixe vaut mieux qu'une faute.
_VERBES_IRREGULIERS = {
    "viennent": "vient", "reviennent": "revient", "deviennent": "devient",
    "tiennent": "tient", "retiennent": "retient", "servent": "sert",
    "sortent": "sort", "partent": "part", "sentent": "sent",
    "mentent": "ment", "battent": "bat", "mettent": "met",
    "permettent": "permet", "font": "fait", "vont": "va", "sont": "est",
    "ont": "a", "peuvent": "peut", "veulent": "veut", "doivent": "doit",
    "savent": "sait", "voient": "voit", "croient": "croit",
    "prennent": "prend", "apprennent": "apprend",
    "comprennent": "comprend", "perdent": "perd", "rendent": "rend",
    "vendent": "vend", "attendent": "attend", "descendent": "descend",
    "repondent": "répond", "répondent": "répond", "entendent": "entend",
    "defendent": "défend", "défendent": "défend", "courent": "court",
    "meurent": "meurt", "suivent": "suit", "vivent": "vit",
    "dorment": "dort", "ecrivent": "écrit", "écrivent": "écrit",
    "decrivent": "décrit", "décrivent": "décrit", "disent": "dit",
    "lisent": "lit", "conduisent": "conduit", "produisent": "produit",
    "traduisent": "traduit", "construisent": "construit",
    "plaisent": "plaît", "connaissent": "connaît",
    "paraissent": "paraît", "naissent": "naît", "recoivent": "reçoit",
    "reçoivent": "reçoit", "boivent": "boit", "envoient": "envoie",
    "essaient": "essaie", "paient": "paie", "emploient": "emploie",
    "appellent": "appelle", "jettent": "jette", "achetent": "achète",
    "achètent": "achète", "esperent": "espère", "espèrent": "espère",
    "precedent": "précède", "précèdent": "précède",
    "possedent": "possède", "possèdent": "possède", "rient": "rit",
    "fuient": "fuit",
}


def _singulier_verbe(mot: str) -> str | None:
    if mot in _VERBES_IRREGULIERS:
        return _VERBES_IRREGULIERS[mot]
    if mot.endswith("issent"):
        return mot[:-6] + "it"
    if mot.endswith("ent") and len(mot) > 4:
        return mot[:-3] + "e"  # 1er groupe : jouent -> joue
    return None


def _accorder(mot: str, pluriel: bool) -> str | None:
    """Ré-accorde un premier mot marqué au féminin pluriel ; None = on ne
    sait pas faire proprement."""
    if mot.endswith("ées"):
        return mot[:-3] + ("és" if pluriel else "é")
    if mot.endswith("ée"):
        return mot[:-2] + "é"
    if mot.endswith("és"):
        return mot if pluriel else mot[:-1]
    if mot.endswith("aient"):
        return mot if pluriel else mot[:-5] + "ait"  # imparfait
    if mot.endswith("ent"):
        return mot if pluriel else _singulier_verbe(mot)
    if mot.endswith("s"):
        # rouges, bourguignonnes, mises, suivies... : la mise au masculin
        # singulier d'un adjectif est trop incertaine
        return None
    return mot  # aucune marque d'accord


# Noms communs en -ées/-ues/-ies : leur présence dans la suite de la
# définition n'est PAS un accord avec « lettres ».
_NOMS_ANODINS = {
    "années", "journées", "soirées", "idées", "allées", "arrivées",
    "montées", "remontées", "échappées", "chevauchées", "percées",
    "tournées", "vues", "revues", "issues", "recrues", "statues",
    "banlieues", "lieues", "rues", "tribunes", "parties", "séries",
    "sorties", "demies", "pénalties", "manies", "écuries",
}


def nettoyer_definition(text: str, word: str = "") -> str:
    reste = _PREFIXE_LETTRES.sub("", text, count=1).strip()
    if not reste or reste == text:
        return text
    pluriel = bool(word) and word.endswith("S")
    mots = reste.split(" ")
    cible = 0
    if mots[0].lower() in ("se", "s'") and len(mots) > 1:
        cible = 1  # « se creusent » : l'accord porte sur le verbe
    accorde = _accorder(mots[cible].lower(), pluriel)
    if accorde is None:
        return text  # on garde le libellé d'origine plutôt qu'une faute
    # Un accord en chaîne plus loin dans la phrase (« devenues
    # londoniennes ») ? Trop risqué : libellé d'origine. Un mot précédé
    # d'un article est un nom, pas un accord.
    _ARTICLES = {
        "le", "la", "les", "des", "du", "un", "une", "ses", "leurs",
        "aux", "quelques", "plusieurs", "bien",
    }
    for i in range(cible + 1, len(mots)):
        bas = mots[i].lower().strip(",.()'")
        if not bas.endswith(("ées", "ues", "ies")) or bas in _NOMS_ANODINS:
            continue
        if mots[i - 1].lower().strip(",.()'") in _ARTICLES:
            continue
        return text
    mots[cible] = accorde
    reste = " ".join(mots)
    return reste[0].upper() + reste[1:]


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
            cible = CIBLES_NIVEAU[(seq - 1) % len(CIBLES_NIVEAU)]
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

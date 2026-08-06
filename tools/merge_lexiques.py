# -*- coding: utf-8 -*-
"""Consolide plusieurs fichiers de collecte CSV en un lexique maître.

Usage :
    python tools/merge_lexiques.py <fichiers ou dossiers...> [-o sortie.csv]

- accepte des fichiers .csv ou des dossiers (motifs motsfleches_foot_*.csv) ;
- déduplique : même mot + même définition = une seule ligne ; même mot avec
  des définitions différentes = union des définitions ;
- valide chaque ligne (8 champs, mot A-Z, longueur recalculée, registre) ;
- écrit le lexique maître trié + un rapport d'anomalies à côté.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.dictionary import normalize_word  # noqa: E402

HEADER = [
    "mot", "affichage", "longueur", "categorie",
    "definition", "registre", "niveau", "verif",
]
MAX_DEF_WARN = 55
MAX_DEF_REJECT = 80


def collect_files(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(path.glob("motsfleches_foot_*.csv")))
        elif path.suffix.lower() == ".csv":
            files.append(path)
    seen = set()
    unique = []
    for path in files:
        key = path.resolve()
        if key not in seen and "master" not in path.name.lower():
            seen.add(key)
            unique.append(path)
    return unique


def merge(files: list[Path]):
    entries: dict[str, dict] = {}
    rejects: list[str] = []
    warnings: list[str] = []
    stats = {"lines": 0, "dupes": 0, "kept": 0}

    for path in files:
        file_lines = 0
        with open(path, encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter=";")
            for n, row in enumerate(reader, start=1):
                if not row or all(not cell.strip() for cell in row):
                    continue
                if [c.strip().lower() for c in row[:2]] == ["mot", "affichage"]:
                    continue  # en-tête (répété en cas de concaténation)
                stats["lines"] += 1
                file_lines += 1

                if len(row) != 8:
                    rejects.append(
                        f"{path.name}:{n} — {len(row)} champs au lieu de 8"
                    )
                    continue
                raw_mot, affichage, _, cat, definition, registre, niveau, verif = (
                    cell.strip() for cell in row
                )
                mot = normalize_word(raw_mot)
                definition = definition.strip().rstrip(".")
                if len(mot) < 2:
                    rejects.append(f"{path.name}:{n} — mot invalide {raw_mot!r}")
                    continue
                if not definition:
                    rejects.append(f"{path.name}:{n} — définition vide pour {mot}")
                    continue
                if len(definition) > MAX_DEF_REJECT:
                    rejects.append(
                        f"{path.name}:{n} — définition de {len(definition)} car. "
                        f"pour {mot}"
                    )
                    continue
                if len(definition) > MAX_DEF_WARN:
                    warnings.append(
                        f"{path.name}:{n} — définition longue "
                        f"({len(definition)} car.) pour {mot}"
                    )
                if registre not in ("factuel", "joueur"):
                    warnings.append(
                        f"{path.name}:{n} — registre {registre!r} remplacé "
                        f"par factuel ({mot})"
                    )
                    registre = "factuel"
                try:
                    level = max(1, min(3, int(niveau or 1)))
                except ValueError:
                    level = 1

                entry = entries.setdefault(
                    mot,
                    {
                        "affichage": affichage or raw_mot,
                        "categories": Counter(),
                        "defs": {},
                    },
                )
                entry["categories"][cat or "divers"] += 1
                key = definition.lower()
                if key in entry["defs"]:
                    stats["dupes"] += 1
                    continue
                entry["defs"][key] = (definition, registre, level, verif)
                stats["kept"] += 1
        print(f"  {path.name}: {file_lines} lignes")

    return entries, rejects, warnings, stats


def best_category(categories: Counter) -> str:
    # fillfoot en dernier recours : c'est la catégorie dépriorisée du moteur.
    ranked = [
        (count, cat != "fillfoot", cat)
        for cat, count in categories.items()
    ]
    ranked.sort(reverse=True)
    themed = [item for item in ranked if item[1]]
    return (themed[0] if themed else ranked[0])[2]


def write_master(entries: dict, output: Path) -> int:
    rows = 0
    with open(output, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(HEADER)
        for mot in sorted(entries, key=lambda m: (len(m), m)):
            entry = entries[mot]
            category = best_category(entry["categories"])
            for definition, registre, level, verif in entry["defs"].values():
                writer.writerow([
                    mot, entry["affichage"], len(mot), category,
                    definition, registre, level, verif,
                ])
                rows += 1
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+")
    parser.add_argument(
        "-o", "--output",
        default=str(Path(__file__).resolve().parent.parent
                    / "data" / "lexique_foot_master.csv"),
    )
    args = parser.parse_args()

    files = collect_files(args.inputs)
    if not files:
        parser.error("aucun fichier CSV trouvé")
    print(f"{len(files)} fichiers :")
    entries, rejects, warnings, stats = merge(files)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = write_master(entries, output)

    lengths = Counter(len(mot) for mot in entries)
    multi = sum(1 for e in entries.values() if len(e["defs"]) >= 2)
    print(f"\n{stats['lines']} lignes lues, {stats['dupes']} doublons ignorés")
    print(f"{len(entries)} mots uniques, {rows} définitions "
          f"({multi} mots avec 2+ définitions)")
    print("par longueur :", dict(sorted(lengths.items())))
    print(f"écrit : {output}")

    report = output.with_suffix(".rapport.txt")
    with open(report, "w", encoding="utf-8") as handle:
        handle.write(f"Fichiers : {[f.name for f in files]}\n\n")
        handle.write(f"REJETS ({len(rejects)}):\n")
        handle.write("\n".join(rejects) or "aucun")
        handle.write(f"\n\nAVERTISSEMENTS ({len(warnings)}):\n")
        handle.write("\n".join(warnings) or "aucun")
    print(f"rapport : {report} ({len(rejects)} rejets, "
          f"{len(warnings)} avertissements)")


if __name__ == "__main__":
    main()

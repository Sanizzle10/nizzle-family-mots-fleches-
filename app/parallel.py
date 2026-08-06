"""Génération répartie sur plusieurs cœurs.

Deux usages :
- `generate_best` : plusieurs recherches indépendantes pour UNE grille, la
  première qui aboutit gagne — c'est ce qui rend la génération fiable sur
  les machines lentes ;
- `generate_batch` : N grilles différentes en parallèle (fabrication d'un
  livre).

Python n'exécute qu'un thread à la fois : il faut de vrais processus. Le
dictionnaire est transmis une seule fois par processus (via l'initialiseur du
pool) et non à chaque tâche. Ce module n'importe aucune dépendance graphique,
pour que les processus enfants démarrent vite.
"""

from __future__ import annotations

import multiprocessing as mp
import os

from app.generator import ArrowGridGenerator
from app.models import Entry, Placement

Result = tuple[list[list[str | None]], list[Placement], dict]


def worker_count(requested: int | None = None, cap: int = 4) -> int:
    """Nombre de processus à utiliser, en laissant l'interface respirer.

    Le plafond compte : au-delà de quatre recherches concurrentes pour une
    même grille, le temps de démarrage des processus sous Windows dépasse le
    gain (mesuré : 0,8 s à 4 processus contre 2,1 s à 8).
    """
    if requested is not None:
        return max(1, requested)
    cpus = os.cpu_count() or 1
    if cpus <= 2:
        return 1  # le surcoût des processus dépasserait le gain
    return max(2, min(cpus - 1, cap))


def _search(task) -> Result:
    entries, width, height, seconds, seed = task
    generator = ArrowGridGenerator(
        width=width, height=height, seconds=seconds, seed=seed
    )
    grid, placements = generator.generate(entries)
    return grid, placements, generator.last_stats


def _solo(
    entries: list[Entry],
    width: int,
    height: int,
    seconds: float,
    seed: int | None,
) -> Result:
    generator = ArrowGridGenerator(
        width=width, height=height, seconds=seconds, seed=seed
    )
    grid, placements = generator.generate(entries)
    return grid, placements, generator.last_stats


def mark_placed(entries: list[Entry], placements: list[Placement]) -> None:
    """Reporte le résultat sur le dictionnaire local.

    Les processus enfants travaillent sur une copie : sans cela, l'appelant
    ne verrait aucun mot marqué comme placé.
    """
    placed = {placement.word for placement in placements}
    for entry in entries:
        entry.placed = entry.word in placed


def generate_best(
    entries: list[Entry],
    width: int = 8,
    height: int = 13,
    seconds: float = 8.0,
    workers: int | None = None,
    seed_base: int = 0,
) -> Result:
    """Lance plusieurs recherches en parallèle, renvoie la première réussie.

    À défaut de réussite, renvoie la grille la plus remplie obtenue.
    """
    count = worker_count(workers)
    if count == 1:
        result = _solo(entries, width, height, seconds, seed_base)
        mark_placed(entries, result[1])
        return result

    tasks = [
        (entries, width, height, seconds, seed_base + offset)
        for offset in range(count)
    ]

    best: Result | None = None
    pool = None
    try:
        pool = mp.Pool(processes=count)
        for result in pool.imap_unordered(_search, tasks):
            stats = result[2]
            if stats.get("complete"):
                best = result
                break
            if best is None or stats.get("fill", 0) > best[2].get("fill", 0):
                best = result
    except Exception:
        # Un incident dans un processus enfant ne doit pas perdre la main.
        best = None
    finally:
        if pool is not None:
            pool.terminate()
            pool.join()

    if best is None:
        best = _solo(entries, width, height, seconds, seed_base)
    mark_placed(entries, best[1])
    return best


def generate_batch(
    entries: list[Entry],
    count: int,
    width: int = 8,
    height: int = 13,
    seconds: float = 8.0,
    workers: int | None = None,
    seed_base: int = 0,
) -> list[Result]:
    """Fabrique `count` grilles distinctes, réparties sur les cœurs."""
    if count <= 0:
        return []

    # Ici toutes les tâches doivent aboutir : on occupe largement la machine.
    processes = min(worker_count(workers, cap=8), count)
    tasks = [
        (entries, width, height, seconds, seed_base + offset * 1013)
        for offset in range(count)
    ]

    if processes == 1:
        return [_search(task) for task in tasks]

    with mp.Pool(processes=processes) as pool:
        return pool.map(_search, tasks)

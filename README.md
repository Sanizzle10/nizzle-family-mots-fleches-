# Mots Fléchés Studio

Application de bureau pour créer des grilles de mots fléchés thématiques
(football) et exporter des livres en PDF.

## Fonctionnement

Le moteur génère des grilles **pleines**, façon magazine : chaque case est
soit une lettre, soit une case définition (avec 1 ou 2 indices et une flèche,
droite ou coudée). Génération en deux phases :

1. structure : positions des cases définitions, validées (chaque suite de
   2+ lettres est un mot atteignable par une flèche, au plus 2 indices par
   case, aucune lettre orpheline) ;
2. remplissage : backtracking sur l'emplacement le plus contraint, priorité
   aux mots thématiques, puis choix d'une définition parmi les variantes.

Le dictionnaire est indexé en masques binaires (`WordIndex`) : trouver les
mots compatibles avec un motif est un ET binaire, pas un parcours de liste.
Plusieurs recherches tournent en parallèle (`app/parallel.py`), la première
qui aboutit gagne.

Taille par défaut : 8 × 13 (format magazine).

### Performances mesurées

Dictionnaire de 3 187 mots / 9 329 définitions, 10 essais par format,
station i9 :

| Format | Cases | Grilles pleines | Remplissage | Mots | Temps |
|---|---|---|---|---|---|
| 8 × 13 | 104 | 10/10 | 100 % | 31 | 0,2 s |
| 10 × 15 | 150 | 10/10 | 100 % | 45 | 1,2 s |
| 13 × 20 | 260 | 10/10 | 100 % | 76 | 6,5 s |

Sur machines plus modestes (grille 8 × 13, 6 essais) : 6/6 grilles pleines
partout, de 6,3 s sur un 2 cœurs ancien à 0,9 s sur la station.

Empreinte : **1,5 Mo de RAM**. Le budget de temps (25 s) est un plafond, pas
un coût : la recherche s'arrête dès qu'une grille est pleine.

Les seuils de validation d'une structure (nombre d'emplacements de 2 lettres,
cases définitions inutilisées) sont **proportionnels à la surface** : des
constantes absolues rejetaient 100 % des structures au-delà du 8 × 13.

> **Attention Windows** : tout script qui appelle `app.parallel` doit placer
> son code sous `if __name__ == "__main__":`. Les processus enfants
> réimportent le module principal ; sans cette garde, il est réexécuté.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Dictionnaire

Format recommandé : CSV séparé par des points-virgules, une ligne par
définition (un même mot peut avoir plusieurs définitions — une est tirée au
sort à chaque grille) :

```csv
mot;affichage;longueur;categorie;definition;registre;niveau;verif
NUL;nul;3;vocab;Score de parité;factuel;1;
NUL;nul;3;vocab;Vous êtes pas contents ?;joueur;2;
```

- `mot` : MAJUSCULES A-Z (accents et tirets retirés automatiquement) ;
- `categorie` : libre ; `fillfoot` est traité en priorité basse (mots de
  remplissage) ;
- `registre` : `factuel` ou `joueur` ; `niveau` : 1 à 3.

L'ancien format Excel (colonnes `Mot` / `Définition` / `Thème`) reste accepté,
avec une définition par mot.

Un lexique de développement est fourni : `data/lexique_foot_v0.csv`.

## Tests

```bash
python -m pytest
```

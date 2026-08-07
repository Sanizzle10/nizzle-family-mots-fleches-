# Format de la banque de grilles (webapp V3)

Produit par `tools/build_bank.py`, consommé par le site statique (`web/`).

## `web/public/data/index.json`

```json
{
  "version": 1,
  "generated": "2026-08-07",
  "dailyStart": "2026-08-07",
  "dailyOrder": ["8x13-042", "10x15-003", "..."],
  "grids": [
    {"id": "8x13-001", "file": "grilles/8x13-001.json",
     "width": 8, "height": 13, "difficulty": 2, "words": 30}
  ]
}
```

La grille du jour se calcule côté client, sans serveur :
`dailyOrder[(jours écoulés depuis dailyStart) % longueur]`.

## `web/public/data/grilles/<id>.json`

```json
{
  "id": "8x13-001",
  "width": 8, "height": 13,
  "difficulty": 1,
  "penalty": 5820,
  "words": 30,
  "solution": ["#PARIS#B", "..."],
  "clues": [
    {"row": 0, "col": 0, "slots": [
      {"text": "Capitale du PSG", "arrow": "right",
       "row": 0, "col": 1, "horizontal": true, "len": 5,
       "word": "PARIS", "display": "Paris"}
    ]}
  ]
}
```

- `solution` : une chaîne par ligne, `#` = case définition, sinon la lettre.
- `clues` : une entrée par case définition **utilisée** (1 ou 2 `slots`).
  Les cases `#` absentes de `clues` sont décoratives (flamme, image).
- `slots[i].arrow` : `right`, `down`, `down_right` (coudée depuis le haut
  vers un mot horizontal), `right_down` (coudée depuis la gauche vers un mot
  vertical) — mêmes valeurs que `app/models.py`.
- `slots[i].row/col` : première lettre du mot ; l'indice horizontal est
  toujours en premier dans `slots` (convention maquette : moitié haute).
- `difficulty` : 1 à 3, moyenne des niveaux des définitions choisies.

## Choix des définitions

La banque re-tire les définitions en équilibrant leur usage global : chaque
variante d'un mot sert à tour de rôle (registre « joueur » préféré à
égalité). Deux grilles partageant un mot montrent donc des définitions
différentes tant qu'il existe des variantes.

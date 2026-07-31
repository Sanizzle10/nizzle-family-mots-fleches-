# Mots Fléchés Studio

Application de bureau pour créer des grilles de mots fléchés illustrées et exporter des livres en PDF.

## Version actuelle

Cette première base propre comprend :

- import d'un dictionnaire Excel ;
- génération d'une grille compacte ;
- affichage moderne en PySide6 ;
- préparation des exports PDF ;
- architecture séparée entre moteur, interface et données.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Format Excel

Colonnes reconnues :

- `Mot`
- `Définition`
- `Thème` facultatif

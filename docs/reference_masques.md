# Référence — génération de masques de mots fléchés (état de l'art)

Synthèse des meilleures pratiques publiées, à recopier dans notre moteur.
Sources principales :

- J. Engel, *Generating Swedish-style Crossword Puzzle Masks*, thèse (masques
  de grilles suédoises = mots fléchés) — barèmes chiffrés ci-dessous.
- J.-S. Gonsette, *Insanely Fast Crosswords Generation* + moteur **Wizium**
  (GPL-3.0) — remplissage par « scaffolding » avec vérification continue de
  faisabilité verticale.
- MDPI Algorithms 2022, *Tries-Based Parallel Solutions for Generating
  Perfect Crosswords Grids* — tries de préfixes, construction ligne à ligne.

## Architecture de référence

1. **Masque** (positions des cases définitions) : problème d'**optimisation**
   avec une fonction de pénalité graduée — jamais de seuils binaires
   accepter/rejeter. Optimiseur : algorithme génétique ou hill-climbing.
2. **Remplissage** : backtracking avec index (tries ou masques binaires),
   variable la plus contrainte d'abord, vérification de faisabilité continue.

Notre acquis : le remplissage (WordIndex en masques binaires + MRV) est déjà
conforme. C'est la partie masque qu'il faut refondre.

## Fonction de pénalité du masque (barèmes de la thèse, à recopier)

Score d'un masque = somme des pénalités. Plus bas = meilleur. Un masque
« valide » est un masque sans pénalité de validité ; la qualité se joue sur le
reste.

### 1. Couverture de chaque case lettre

| Situation de la case | Pénalité |
|---|---|
| Couverte horizontalement ET verticalement | 0 |
| Couverte une fois, coincée entre deux cases non-lettre | 75 |
| Couverte une seule fois | 200 |
| Couverte deux fois dans la même direction (invalide) | 600 |
| Non couverte (invalide) | 1500 |

### 2. Longueur des mots

| Longueur | Pénalité | | Longueur | Pénalité |
|---|---|---|---|---|
| 0 | 1800 | | 7 | 30 |
| 1 | 1500 | | 8 | 50 |
| 2 | **650** | | 9 | 150 |
| 3 | 100 | | 10 | 250 |
| 4 | 10 | | 11 | 400 |
| 5 | **0** | | 12 | 550 |
| 6 | **0** | | 13+ | 750 → 1300 |

L'optimum est **5-6 lettres**. Les mots de 2 lettres sont presque aussi
pénalisés qu'une case invalide — tout l'inverse de nos grilles actuelles où
ils sont la norme (~50 % des mots).

En plus : chaque croisement de deux mots **tous deux > 6 lettres** coûte le
produit des longueurs (9×9 → 81 pts) — trouver des mots compatibles y est
trop dur.

### 3. Groupements de cases définitions

Les amas 8-connexes (diagonales comprises) de cases définitions sont
pénalisés, d'autant plus que leur étendue max (horizontale ou verticale) est
grande. Les cases collées au bord haut/gauche comptent moitié.

### 4. Culs-de-sac

Case lettre entourée de trois cases non-lettre (hors bords haut/gauche) :
400 pts.

## Optimiseur (thèse, chapitre mutation)

- **Mutation centralisée** : choisir un point central, muter k cases proches
  (distribution normale σ=3 autour du centre). **k tiré au hasard dans
  {2, 3}** = meilleur réglage mesuré.
- **Mutation guidée** : le point central est choisi par tournoi (α=2) sur la
  **pénalité locale** — on mute là où ça pénalise le plus. (La pénalité de
  chaque critère se répartit sur les cases concernées.)
- **Probabilités de type** : en remplacement, ~2/3 lettre, ~1/3 case
  définition (répartie selon la fréquence naturelle des types de flèches).
- **Mutations prédéfinies** : « décaler » une case définition d'une case ;
  « couper » un mot long en deux en insérant une case définition.
- Un simple **hill-climber** avec ces opérateurs donne déjà de bons masques
  (la thèse compare : GA complet surtout utile pour les grandes grilles).
- Ordre de grandeur : masque 20×20 correct en ~1 M d'évaluations de la
  fonction de pénalité (elle doit donc être incrémentale ou très rapide).

## Remplissage (Gonsette / MDPI, pour mémoire)

- « Scaffolding » : poser les mots horizontaux en garantissant en permanence
  qu'un mot vertical compatible existe sur chaque colonne croisée (index de
  préfixes). 8×8 parfait : ~10^8,5 pas contre ~10^35 en naïf.
- Notre remplissage bitmask + MRV joue dans la même catégorie ; si les
  masques optimisés le mettent en difficulté, ajouter la vérification de
  préfixes verticaux comme lookahead.

## Ce que cela remplace chez nous

| Chez nous aujourd'hui | Référence |
|---|---|
| Seuils binaires (≤10 emplacements de 2 lettres, ≤78-95 % de croisement, ≤N cases mortes) | Pénalités graduées, un seul score |
| Dispersion aléatoire + réparation | Optimisation du score par mutations guidées |
| `min_word`, `max_crossing`, couloirs réservés (proxys fragiles) | Barème de longueurs (optimum 5-6) directement dans le score |
| Croisement plafonné | Croisement récompensé (0 pénalité), sauf entre deux mots longs |

Licence : Wizium est GPL-3.0 — s'inspirer de la méthode (les algorithmes ne
sont pas protégés) plutôt que de copier le code, notre base étant
propriétaire.

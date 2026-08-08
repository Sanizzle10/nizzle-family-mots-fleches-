# Changelog — NiZZLE Family Mots Fléchés Foot

Toutes les évolutions notables du projet. L'historique git détaillé fait
foi ; ce fichier en est la version lisible.

## 08/08/2026 — mise en ligne et banque de masse

### Nouveautés
- **Site en ligne** : https://nizzle-family-mots-fleches.netlify.app
  (déploiement automatique à chaque mise à jour).
- **Banque de 2 454 grilles** : 2 000 en 8×13, 400 en 10×15, 54 en 13×20 —
  1 443 faciles (mots connus), 759 moyennes, 252 difficiles. Sur-génération
  de 25 % et sélection des grilles les mieux notées.
- **Validation des grilles terminées** : à la dernière lettre juste, une
  fenêtre « Bravo ! » propose de valider la grille — elle passe alors en
  vert ✓ au catalogue.
- **Grille du jour** mise en avant (une nouvelle chaque jour, format
  magazine 8×13, jamais difficile) + **catalogue** des grilles par
  difficulté avec états (en cours / terminée) et affichage par tranches.
- **Jeu complet sur téléphone** : saisie au clavier virtuel, vérification
  des lettres (fautes barrées), bouton indice, progression sauvegardée
  par grille dans le navigateur.
- **App de bureau** : démarrage autonome (lexique chargé + première grille
  générée automatiquement), sélecteur de difficulté (Facile mots connus /
  Moyen / Difficile), trois exports PDF (grille vide, solution, livret
  2 pages), raccourci de lancement.

### Qualité éditoriale
- **Revue complète des 9 329 définitions** : 84 définitions inutilisables
  écartées (opaques, erreurs factuelles, phrases à trou).
- Grilles faciles générées **uniquement avec des mots connus** (au moins
  une définition grand public).
- Corrections d'accord : « Font entrer dans l'histoire » → « Fait entrer
  dans l'histoire » ; les mots-réponses en -S (noms propres) gardent le
  libellé d'origine plutôt qu'un accord risqué.

### Corrections
- **Android : le clavier réduit désormais la page** (`interactive-widget`)
  — sans cela, la page ne pouvait pas défiler vers la case active et le
  recentrage restait sans effet.
- **Intégrité des sauvegardes** : chaque sauvegarde porte l'empreinte du
  contenu de sa grille ; une sauvegarde qui ne correspond plus (banque
  régénérée sous les mêmes numéros) est écartée au lieu de mélanger les
  lettres. Les sauvegardes d'avant cette protection sont purgées —
  progression remise à zéro une unique fois.
- **Téléphone : recentrage automatique sur la case où l'on écrit** — au
  clic, à chaque lettre et à l'ouverture du clavier virtuel, la page
  défile pour garder la case active visible au-dessus du clavier (et ne
  bouge pas pendant un simple swipe).
- **Téléphone : l'écran ne « remonte » plus à chaque lettre** (le champ
  du clavier virtuel suit désormais la case où l'on écrit).
- Le catalogue restait affiché en permanence par-dessus la page (bloquant
  sur mobile).

## 07/08/2026 — la webapp naît

### Nouveautés
- **Grille jouable dans le navigateur** : look fidèle à la maquette (fond
  bleu roi, cadre rouge, cases roses, flèches droites et coudées), saisie
  clavier, sens de saisie au choix (horizontal/vertical), clic sur une
  définition pour sélectionner son mot, bouton Solutions.
- **Banque de grilles JSON** générée par le moteur (format documenté,
  rotation des définitions entre grilles).
- **Identité NiZZLE Family** : nouveau nom, 12 caricatures de footballeurs
  en zigzag sur les côtés (centrées entre bord d'écran et cadre rouge,
  responsive), ballon sur les cases décoratives.

### Corrections et lisibilité (retours joueur)
- Trait de séparation entre deux définitions d'une même case.
- Préfixes « Trois lettres qui… » retirés (la case donne déjà le nombre).
- Icônes directionnelles → ↴ ↓ ↳ devant chaque définition des cases
  doubles + ordre géométrique (mot vers la droite en haut).
- Budget de caractères par case : plus aucune définition coupée.
- Grilles plus faciles : 60 % de niveau 1, définitions factuelles
  directes en facile (pays, club), humour réservé aux niveaux relevés.

## 06-07/08/2026 — moteur V2 (app de bureau)

- **Nouveau moteur à grilles 100 % pleines** : structure + remplissage
  avec retour arrière, mutation guidée par l'échec, index binaire du
  dictionnaire (10× plus rapide), génération parallèle multi-cœurs.
- **Qualité état de l'art** : fonction de pénalité des structures
  (barèmes publiés), optimisation par hill-climbing guidé, sélection de
  la meilleure grille entre recherches parallèles. Pénalité divisée par 3,
  mots de 2-3 lettres de 57 % → 25-30 %.
- Mesuré : 30/30 grilles pleines sur les 3 formats (8×13 : 3,7 s ;
  10×15 : 5,3 s ; 13×20 : 7,9 s), 33 tests automatiques.
- Lexique maître : 3 187 mots, 9 329 définitions collectées.

## 31/07/2026 — premiers pas

- Générateur initial, interface de bureau, import de dictionnaires
  (Excel puis CSV multi-définitions), export PDF A4 thématisé.

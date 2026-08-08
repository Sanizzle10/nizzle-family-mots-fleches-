"""Nettoyage éditorial des définitions, partagé entre l'app de bureau et
la fabrique de banque web.

Deux traitements :
- retrait des préfixes « X lettres qui... » (la case donne déjà le nombre
  de lettres) avec ré-accord grammatical au mot-réponse ;
- exclusion des définitions écartées par la revue éditoriale
  (data/definitions_exclues.csv) — le lexique maître reste intact.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.models import Entry

EXCLUSIONS = Path(__file__).resolve().parents[1] / "data" / "definitions_exclues.csv"

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

# Noms communs en -ées/-ues/-ies : leur présence dans la suite de la
# définition n'est PAS un accord avec « lettres ».
_NOMS_ANODINS = {
    "années", "journées", "soirées", "idées", "allées", "arrivées",
    "montées", "remontées", "échappées", "chevauchées", "percées",
    "tournées", "vues", "revues", "issues", "recrues", "statues",
    "banlieues", "lieues", "rues", "tribunes", "parties", "séries",
    "sorties", "demies", "pénalties", "manies", "écuries", "trophées",
}

_ARTICLES = {
    "le", "la", "les", "des", "du", "un", "une", "ses", "leurs",
    "aux", "quelques", "plusieurs", "bien",
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
    sait pas faire proprement.

    Un mot-réponse finissant par S (pluriel probable) peut aussi être un
    nom propre singulier (EARPS) : impossible de trancher, donc devant
    toute marque d'accord on renonce et on garde le libellé d'origine.
    """
    if mot in _VERBES_IRREGULIERS:
        # avant les règles de suffixe : « font », « ont », « sont »,
        # « vont » finissent en -ont, pas en -ent
        return None if pluriel else _VERBES_IRREGULIERS[mot]
    if mot.endswith("ées"):
        return None if pluriel else mot[:-3] + "é"
    if mot.endswith("ée"):
        return mot[:-2] + "é"
    if mot.endswith("és"):
        return None if pluriel else mot[:-1]
    if mot.endswith("aient"):
        return None if pluriel else mot[:-5] + "ait"  # imparfait
    if mot.endswith("ent"):
        return None if pluriel else _singulier_verbe(mot)
    if mot.endswith("s"):
        # rouges, bourguignonnes, mises, suivies... : la mise au masculin
        # singulier d'un adjectif est trop incertaine
        return None
    return mot  # aucune marque d'accord


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


def charger_exclusions() -> set[tuple[str, str]]:
    """Paires (MOT, définition brute) écartées par la revue éditoriale."""
    exclues: set[tuple[str, str]] = set()
    if not EXCLUSIONS.exists():
        return exclues
    for ligne in EXCLUSIONS.read_text(encoding="utf-8").splitlines()[1:]:
        champs = ligne.split(";")
        if len(champs) < 2:
            continue
        # mot;definition;raison — la définition peut contenir des « ; » :
        # tout sauf le premier et le dernier champ.
        mot = champs[0].strip().upper()
        definition = ";".join(champs[1:-1]).strip() if len(champs) > 2 \
            else champs[1].strip()
        if mot and definition:
            exclues.add((mot, definition))
    return exclues


def appliquer_exclusions(entries: list[Entry]) -> list[Entry]:
    """Retire les définitions écartées ; un mot qui n'en a plus disparaît."""
    exclues = charger_exclusions()
    gardes = []
    for entry in entries:
        entry.definitions = [
            d for d in entry.definitions if (entry.word, d.text) not in exclues
        ]
        if entry.definitions:
            gardes.append(entry)
    return gardes


def mots_connus(entries: list[Entry]) -> list[Entry]:
    """Mots grand public : au moins une définition de niveau 1."""
    return [e for e in entries if any(d.level == 1 for d in e.definitions)]


def choisir_definition(entry: Entry, cible: int, rng) -> str:
    """Définition adaptée au niveau visé : niveau le plus proche (en
    dessous de préférence), registre factuel en facile, joueur sinon."""
    def ecart(d):
        return abs(d.level - cible) + (0.5 if d.level > cible else 0)

    meilleur = min(ecart(d) for d in entry.definitions)
    bassin = [d for d in entry.definitions if ecart(d) == meilleur]
    registre = "factuel" if cible == 1 else "joueur"
    prefere = [d for d in bassin if d.register == registre]
    return rng.choice(prefere or bassin).text


def preparer_lexique(entries: list[Entry]) -> list[Entry]:
    """Exclusions + nettoyage des préfixes, pour l'app de bureau."""
    entries = appliquer_exclusions(entries)
    for entry in entries:
        for definition in entry.definitions:
            definition.text = nettoyer_definition(definition.text, entry.word)
    return entries

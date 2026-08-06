import textwrap

import pytest

from app.dictionary import load_dictionary, normalize_word


def write_csv(tmp_path, content):
    path = tmp_path / "dico.csv"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def test_normalize_word():
    assert normalize_word("Mbappé") == "MBAPPE"
    assert normalize_word("Di María") == "DIMARIA"
    assert normalize_word("Saint-Étienne") == "SAINTETIENNE"
    assert normalize_word(" allez les bleus ") == "ALLEZLESBLEUS"


def test_csv_multiple_definitions_grouped(tmp_path):
    path = write_csv(
        tmp_path,
        """\
        mot;affichage;longueur;categorie;definition;registre;niveau;verif
        NUL;nul;3;vocab;Score de parité;factuel;1;match sans vainqueur
        NUL;nul;3;vocab;Vous êtes pas contents ?;joueur;2;
        COUPE;coupe;5;competitions;On espère la ramener à la maison;joueur;1;
        """,
    )
    entries = load_dictionary(path)
    by_word = {entry.word: entry for entry in entries}

    assert set(by_word) == {"NUL", "COUPE"}
    assert len(by_word["NUL"].definitions) == 2
    registers = {d.register for d in by_word["NUL"].definitions}
    assert registers == {"factuel", "joueur"}
    assert by_word["COUPE"].category == "competitions"


def test_csv_skips_bad_rows_and_duplicate_definitions(tmp_path):
    path = write_csv(
        tmp_path,
        """\
        mot;affichage;longueur;categorie;definition;registre;niveau;verif
        BUT;but;3;vocab;Objectif de tout attaquant;factuel;1;
        BUT;but;3;vocab;Objectif de tout attaquant;factuel;1;
        X;x;1;vocab;Trop court;factuel;1;
        VIDE;vide;4;vocab;;factuel;1;
        """,
    )
    entries = load_dictionary(path)
    assert len(entries) == 1
    assert entries[0].word == "BUT"
    assert len(entries[0].definitions) == 1


def test_excel_legacy_format(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "dico.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Mot", "Définition", "Thème"])
    sheet.append(["Zidane", "Numéro dix légendaire", "foot"])
    sheet.append(["Mbappé", "Capitaine des Bleus", "foot"])
    workbook.save(path)

    entries = load_dictionary(path)
    by_word = {entry.word: entry for entry in entries}
    assert set(by_word) == {"ZIDANE", "MBAPPE"}
    assert by_word["ZIDANE"].definitions[0].text == "Numéro dix légendaire"


def test_empty_file_raises(tmp_path):
    path = tmp_path / "vide.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        load_dictionary(path)

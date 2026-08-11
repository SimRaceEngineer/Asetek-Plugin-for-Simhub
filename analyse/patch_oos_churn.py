#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_oos_churn.py -- apprend a oos_v9.py le vrai nom du champ churn

CE QU ON A ETABLI LE 11/08
    oos_v9.py --champs annonce churn a 0 pour cent. Ce n est pas que le
    champ manque : il s appelle churn_entry, et CLEFS_CHURN ne connait que
    churn, churn_verdict, verdict_churn et churn_at_entry.

    Une ligne a changer, donc, et au bon endroit : l en-tete de oos_v9.py
    dit explicitement que les listes CLEFS_* sont LE SEUL endroit a
    corriger quand la couverture est faible. Le fichier de regles gelees
    reste intouchable -- son empreinte SHA-256 est posee.

POURQUOI UN SCRIPT POUR UNE LIGNE
    Parce que la corriger a la main a echoue : la ligne collee dans
    PowerShell a ete prise pour un cmdlet. Un fichier qu on execute ne
    laisse pas ce doute.

    Et parce que oos_v9.py contient huit octets non-ASCII : un
    Get-Content / Set-Content de PowerShell devinerait l encodage et
    pourrait les abimer. Python, lui, le lit et le reecrit dans le meme
    encodage, verifie explicitement.

CE QUE CA NE REGLE PAS
    La famille Y du gel V9 seulement. La famille X -- X1, X3, X4, X6 --
    repose sur le biais des rails M1/M3/M5, et ces champs ne sont ecrits
    dans AUCUN fichier. Aucune correction de nom ne peut les faire
    apparaitre. Voir la fin de la sortie.

IDEMPOTENT.
"""
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "oos_v9.py"
MARQUEUR = "churn_entry"
ANCRE = '"churn", "churn_verdict"'
NEUF = '"churn", "churn_entry", "churn_verdict"'


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable -- lance depuis le dossier de la stack." % CIBLE)
        return 1

    src, enc = lire(CIBLE)
    print("%s : %d lignes, encodage %s" % (CIBLE, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Deja corrige -- rien a faire.")
        return 0

    if src.count(ANCRE) != 1:
        print("KO : %d occurrence(s) de l ancre, il en faut 1 :" % src.count(ANCRE))
        print("    " + ANCRE)
        print()
        print("Ouvre oos_v9.py, cherche CLEFS_CHURN, et ajoute \"churn_entry\"")
        print("dans la liste. C est tout ce que ce patch fait.")
        return 1

    neuf = src.replace(ANCRE, NEUF, 1)
    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    sauve = "%s.bak-%s" % (CIBLE, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(CIBLE, sauve)
    io.open(CIBLE, "w", encoding=enc).write(neuf)
    print("Sauvegarde : %s" % sauve)
    print("CLEFS_CHURN connait maintenant churn_entry.")
    print()
    print("Verifie :   python oos_v9.py --champs")
    print("La ligne churn doit passer de 0% a pres de 100%.")
    print()
    print("MAIS CELA NE SUFFIT PAS POUR LE VERDICT DU 01/09")
    print("  La famille X du gel V9 -- X1, X3, X4, X6, dont la tete X1 --")
    print("  repose sur le biais des rails M1, M3 et M5. Ces champs ne sont")
    print("  ecrits dans aucun fichier : le panel 8095 les calcule a")
    print("  l affichage et ne les persiste pas.")
    print("  Aucune correction de nom ne peut les faire apparaitre. Il faut")
    print("  que le module qui ecrit churn_trades*.jsonl ajoute quatre")
    print("  champs a chaque enregistrement. Pour trouver ce module :")
    print()
    print("    Get-ChildItem -Recurse -Filter *.py |")
    print("      Select-String -Pattern 'churn_entry' |")
    print("      Select-Object Path, LineNumber, Line")
    return 0


if __name__ == "__main__":
    sys.exit(main())

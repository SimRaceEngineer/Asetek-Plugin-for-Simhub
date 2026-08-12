# -*- coding: utf-8 -*-
"""
patch_entete_range.py -- aligner l entete de rails_range.py sur ses colonnes

  python patch_entete_range.py --essai
  python patch_entete_range.py

LE DEFAUT

    bloc() ecrivait ses deux lignes d entete avec des largeurs posees a
    la main :

        "%-*s %21s %21s"
        "%-*s %9s %4s %4s   %9s %4s %4s"

    alors que duo() ecrit ses donnees ainsi :

        "%-*s" puis, par regime, "%9.2f %4d %3.0f%%" + 2 caracteres

    Soit 21 caracteres par regime pour la donnee, mais 22 puis 23 pour
    l entete : celle-ci flotte de 1 caractere sur le premier regime et de
    2 sur le second.

POURQUOI CA COMPTE MAINTENANT

    A l oeil, personne ne l avait vu -- et personne n avait tort, la
    lecture reste juste. Mais le rendu HTML (panel_texte.py) deduit les
    colonnes de la GEOMETRIE du texte : il cherche les positions ou
    toutes les lignes ont un espace. Avec l entete decalee, la colonne N
    et la colonne WR n avaient plus aucune position libre en commun, et
    restaient collees dans une seule case.

    On corrige donc la cause -- l entete -- plutot que d apprendre au
    rendu a deviner ou couper. Un rendu qui devine finit par se tromper
    sur un tableau qu on ne relira pas.

CE QUE CA NE CHANGE PAS

    Aucun chiffre, aucun calcul, aucune selection. Seulement l espacement
    de deux lignes d entete. rails_trois.py etait deja ecrit de cette
    facon ; c est sa forme qu on reprend.

IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
Le patch IMPRIME les lignes reconnues avant d ecrire.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "rails_range.py"
MARQUEUR = '2 * ("%9s %4s %4s%2s"'

RE_ANCRE = re.compile(
    r'^([ \t]*)print\("%-\*s %21s %21s"[^\n]*\n'
    r'[ \t]*% \(largeur, "", "TENDANCE 28/07-04/08", "RANGE depuis 05/08"\)\)'
    r'[ \t]*\n'
    r'[ \t]*print\("%-\*s %9s %4s %4s   %9s %4s %4s"[ \t]*\n'
    r'[ \t]*% \(largeur, "", "EUR/tr", "N", "WR", "EUR/tr", "N", "WR"\)\)'
    r'[ \t]*$', re.M)

# Variante sur une seule ligne : le fichier a deja ete reformate ailleurs.
RE_SOUPLE = re.compile(
    r'^([ \t]*)print\("%-\*s %21s %21s".*?"RANGE depuis 05/08"\)\)[ \t]*\n'
    r'[ \t]*print\("%-\*s %9s %4s %4s   %9s %4s %4s".*?"WR"\)\)[ \t]*$',
    re.M | re.S)

NEUF = '''%(i)s# Les largeurs sont celles de duo() -- 21 caracteres par regime -- et
%(i)s# non des espaces poses a la main. L entete flottait de 1 puis 2
%(i)s# caracteres contre ses colonnes : invisible a l oeil, mais le rendu
%(i)s# HTML deduit les colonnes de la geometrie du texte et ne pouvait pas
%(i)s# separer N de WR. Meme forme que rails_trois.py.
%(i)sprint("%%-*s%%21s%%21s"
%(i)s      %% (largeur, "", "TENDANCE 28/07-04/08", "RANGE depuis 05/08"))
%(i)sprint("%%-*s%%s" %% (largeur, "", 2 * ("%%9s %%4s %%4s%%2s"
%(i)s                                        %% ("EUR/tr", "N", "WR", ""))))'''


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1

    src, enc = lire(a.fichier)
    print("%s : %d lignes, encodage %s" % (a.fichier, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    rx = RE_ANCRE if len(RE_ANCRE.findall(src)) == 1 else RE_SOUPLE
    n = len(rx.findall(src))
    if n != 1:
        print("KO : %d occurrence(s) des deux lignes d entete, il en faut 1."
              % n)
        print("Attendu, dans bloc() :")
        print('    print("%-*s %21s %21s" ...')
        print('    print("%-*s %9s %4s %4s   %9s %4s %4s" ...')
        print("Rien n a ete ecrit.")
        return 1

    m = rx.search(src)
    for l in m.group(0).split("\n"):
        print("  remplace : %s" % l.strip()[:74])

    ind = m.group(1)
    neuf = src[:m.start()] + (NEUF % {"i": ind}) + src[m.end():]

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Apres patch, entete et donnees ont les memes largeurs :")
    print("  21 caracteres par regime, comme duo().")
    print("Aucun chiffre ne change -- seulement l espacement.")
    print("Il faut ensuite relancer l export :")
    print("  python export_panels.py --dest panels")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc).write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

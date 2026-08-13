# -*- coding: utf-8 -*-
"""
patch_x60_atomique.py -- ecrire le panneau x60 sans jamais le laisser a moitie

  python patch_x60_atomique.py --essai
  python patch_x60_atomique.py

POURQUOI MAINTENANT

    Le panneau x60 va avoir DEUX ecrivains :

      panels_auto        toutes les 15 minutes, dans son cycle
      rafraichir_x60     toutes les 30 secondes, pour le direct

    Aujourd hui x60_onset ecrit ainsi :

        io.open(PANNEAU, "w", encoding="utf-8").write("\\n".join(...))

    `open(..., "w")` VIDE le fichier immediatement, puis le remplit. Si
    un lecteur -- le 8095 qui sert la page, ou le REPL qui charge ses
    documents -- lit pendant cet intervalle, il recoit un panneau vide
    ou tronque. Avec un ecrivain toutes les 30 secondes et un panneau
    de 15 ko, la fenetre est courte mais elle existe, et le symptome
    serait un panneau mysterieusement coupe une fois sur mille.

CE QUE LE PATCH FAIT

    Ecrire dans PANNEAU + ".tmp", puis renommer. Le renommage est
    atomique : un lecteur voit soit l ancien panneau complet, soit le
    nouveau complet, jamais un entre-deux.

    Sur Windows, os.rename echoue si la cible existe -- d ou le
    os.replace, qui ecrase atomiquement et fonctionne aussi sur Unix.

    C est le meme motif que ecrire_etat() dans papier_tf, pour la meme
    raison.

CE QU IL NE CHANGE PAS

    Le contenu du panneau, pas d un caractere. Ni le rapport, ni la
    boucle d observation, ni les evenements.

UNE ANCRE, verifiee unique. IDEMPOTENT. Sauvegarde horodatee.
ast.parse avant ecriture.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "x60_onset.py"
MARQUEUR = "os.replace"

RE_ECRITURE = re.compile(
    r'^([ \t]*)io\.open\(PANNEAU, "w", encoding="utf-8"\)\.write\(\n'
    r'[ \t]*"\\n"\.join\(\["# panel_x60_onset\.txt",\n'
    r'[ \t]*"# ecrit le %s" % maintenant\(\),\n'
    r'[ \t]*"# via x60_onset\.py --rapport", ""\] \+ L\) \+ "\\n"\)$', re.M)

NEUF = '''@I@# Ecriture ATOMIQUE : le fichier temporaire puis un renommage.
@I@# open(..., "w") vide le fichier avant de le remplir, et deux
@I@# ecrivains -- panels_auto toutes les 15 min, rafraichir_x60 toutes
@I@# les 30 s -- exposeraient un lecteur a un panneau tronque. Avec le
@I@# renommage, il voit l ancien complet ou le nouveau complet.
@I@_tmp = PANNEAU + ".tmp"
@I@io.open(_tmp, "w", encoding="utf-8").write(
@I@    "\\n".join(["# panel_x60_onset.txt",
@I@               "# ecrit le %s" % maintenant(),
@I@               "# via x60_onset.py --rapport", ""] + L) + "\\n")
@I@# os.replace et pas os.rename : sur Windows, rename echoue si la
@I@# cible existe. replace ecrase atomiquement, et marche partout.
@I@os.replace(_tmp, PANNEAU)'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    n = len(RE_ECRITURE.findall(src))
    if n != 1:
        print("KO : %d occurrence(s) de l ecriture du panneau, il en faut 1."
              % n)
        print("Rien n a ete ecrit.")
        return 1

    m = RE_ECRITURE.search(src)
    neuf = (src[:m.start()] + NEUF.replace("@I@", m.group(1))
            + src[m.end():])

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Le panneau sera ecrit dans un .tmp puis renomme.")
    print("Un lecteur verra toujours un fichier complet -- l ancien ou")
    print("le nouveau, jamais un panneau coupe en deux.")
    print()
    print("Necessaire avant de lancer rafraichir_x60 : il ecrit toutes")
    print("les 30 s pendant que panels_auto ecrit toutes les 15 min.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. C est le --rapport qui ecrit : rien a redemarrer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

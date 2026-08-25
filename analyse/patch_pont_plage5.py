#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_pont_plage5.py -- le pont voit la branche 5.

POURQUOI C EST INDISPENSABLE, ET PAS COSMETIQUE
-----------------------------------------------
Le lecteur du pont ne retient que les positions dont le magic tombe
dans `PLAGES`. La branche 5 porte des magics prefixes d un 5 --
5240004 pour 240004 -- qui n y sont pas.

Sans cette ligne, la branche 5 ouvrirait demain sur le compte du
moteur et ne serait JAMAIS copiee sur le compte dedie. L experience
existerait sans qu on puisse la lire : le miroir 1 et le miroir 2
apparaitraient dans cartes_live, le miroir 5 nulle part.

    220000 - 249999      miroir 1
   4220000 - 4249999     miroir 2
   5220000 - 5249999     miroir 5    <- ajoute ici

LE PONT DOIT ETRE RELANCE POUR EN TENIR COMPTE
    Le lecteur et l envoyeur chargent ce module au demarrage. Tant
    qu ils tournent, ils appliquent l ancienne liste. Le gardien les
    relance chaque matin -- si le pont est arrete ce soir, la plage
    sera en place demain sans rien faire de plus.

USAGE
-----
    python patch_pont_plage5.py                 <- simulation
    python patch_pont_plage5.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\pont_miroirs.py"
SUFFIXE_BAK = ".bak_plage5"

VIEUX = '''# Les deux plages de magics des miroirs paper.
PLAGES = ((220000, 249999), (4220000, 4249999))'''

NEUF = '''# Les trois plages de magics des miroirs paper.
#   220000 - 249999    miroir 1, le magic du paper lui-meme
#  4220000 - 4249999   miroir 2, ancien regime de sortie
#  5220000 - 5249999   miroir 5, meme entree filtree par le CVD
# Sans la troisieme, la branche 5 ouvrirait sur le compte du moteur
# sans jamais etre copiee ici : elle existerait sans etre lisible.
PLAGES = ((220000, 249999), (4220000, 4249999), (5220000, 5249999))'''


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 66)
    print("patch_pont_plage5 -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 66)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))

    if "5220000" in s:
        print("")
        print("Deja corrige : la plage 5 est presente.")
        return 0
    n = s.count(VIEUX)
    if n != 1:
        print("")
        print("REFUS : PLAGES attendu 1 fois, trouve %d." % n)
        print("La ligne a change. Me la montrer plutot que de la deviner :")
        print("c est elle qui decide de ce que le compte dedie voit.")
        return 1
    print("        PLAGES est unique.")
    print("")
    print("a faire :")
    print("   + (5220000, 5249999) -- le pont copiera la branche 5")

    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer.")
        return 0

    bak = a.cible + SUFFIXE_BAK
    if not os.path.exists(bak):
        shutil.copy2(a.cible, bak)
        print("")
        print("sauvegarde : %s" % bak)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(s.replace(VIEUX, NEUF, 1))
    print("ecrit : %s" % a.cible)

    relu = lire(a.cible)
    if "5220000" not in relu:
        print("relu   : INCOMPLET -- restaurer %s" % bak)
        return 1
    try:
        compile(relu, a.cible, "exec")
    except SyntaxError as e:
        print("syntaxe: ERREUR ligne %s -- restaurer %s" % (e.lineno, bak))
        return 1
    print("relu   : la plage est la, le fichier compile.")
    print("")
    print("-" * 66)
    print("Le pont doit etre RELANCE pour en tenir compte. S il est arrete")
    print("ce soir, le gardien le relancera demain matin avec la plage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

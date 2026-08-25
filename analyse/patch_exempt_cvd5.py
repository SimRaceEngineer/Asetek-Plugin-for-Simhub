#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_exempt_cvd5.py -- la branche 5 sort comme le miroir 1.

POURQUOI CELUI-CI PASSE AVANT L AUTRE
-------------------------------------
`papers_exempt.PLAGES` dit quels magics ne sortent QUE par leur parent,
exemptes de M154_FOLLOW, IGN_COVER et PREOPEN_75. Le miroir 1
(220000-249999) y est ; le miroir 2 (4220000-4249999) en est dehors
VOLONTAIREMENT, c est toute sa raison d etre.

La branche 5, elle, doit y ETRE. Son objet est de mesurer un filtre d
ENTREE : si elle sortait comme le miroir 2, l ecart entre 1 et 5
melangerait le filtre d entree et le regime de sortie, et ne mesurerait
plus rien du tout.

C est pour ca que patch_miroir_cvd5.py refuse de s appliquer tant que
cette plage n est pas la.

    5220000 - 5250000     miroir 5, exempte comme le miroir 1

Le module expose deja `ajoute_plage(debut, fin)` -- on s en sert au lieu
de reecrire le tuple : la fonction existe, elle est faite pour ca.

USAGE
-----
    python patch_exempt_cvd5.py                 <- simulation
    python patch_exempt_cvd5.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\papers_exempt.py"
SUFFIXE_BAK = ".bak_cvd5"
MARQUEUR = "5220000"

VIEUX = "PLAGES = ((220000, 250000),)"
NEUF = '''PLAGES = ((220000, 250000),
          # La branche 5 -- meme entree filtree par le CVD -- sort COMME
          # le miroir 1. Elle mesure un filtre d ENTREE : si elle sortait
          # comme le miroir 2, l ecart entre 1 et 5 melangerait entree et
          # sortie et ne mesurerait plus rien.
          (5220000, 5250000),)'''


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 66)
    print("patch_exempt_cvd5 -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 66)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))
    if MARQUEUR in s:
        print("")
        print("Deja corrige : la plage 5 est presente.")
        return 0
    n = s.count(VIEUX)
    if n != 1:
        print("")
        print("REFUS : PLAGES attendu 1 fois, trouve %d." % n)
        print("Le tuple a change de forme. Me montrer la ligne : je ne")
        print("devine pas ce qui decide des sorties.")
        return 1
    print("        PLAGES est unique.")
    print("")
    print("a faire :")
    print("   + (5220000, 5250000) -- le miroir 5 sort comme le miroir 1")

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
    if MARQUEUR not in relu:
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
    print("Ce module est LU par ceux qui decident des sorties : il prend")
    print("effet a leur prochain demarrage, pas maintenant.")
    print("Puis patch_miroir_cvd5.py, qui refusait tant que ceci manquait.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

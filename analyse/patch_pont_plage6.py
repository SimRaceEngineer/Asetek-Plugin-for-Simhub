#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_pont_plage6.py -- le pont apprend la quatrieme plage.

Sans elle, la branche 6 ouvrirait sur le compte du moteur sans jamais
etre copiee sur 18**09 : elle existerait sans etre lisible. C est
exactement ce que le commentaire de PLAGES dit deja de la branche 5.

Une seule ligne change, plus le commentaire qui la documente.

USAGE
-----
    python patch_pont_plage6.py                 <- simulation
    python patch_pont_plage6.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys
import time

CIBLE_DEFAUT = "pont_miroirs.py"
MARQUEUR = "6220000"

R = [(
'''# Les trois plages de magics des miroirs paper.
#   220000 - 249999    miroir 1, le magic du paper lui-meme
#  4220000 - 4249999   miroir 2, ancien regime de sortie
#  5220000 - 5249999   miroir 5, meme entree filtree par le CVD
# Sans la troisieme, la branche 5 ouvrirait sur le compte du moteur
# sans jamais etre copiee ici : elle existerait sans etre lisible.
PLAGES = ((220000, 249999), (4220000, 4249999), (5220000, 5249999))''',
'''# Les quatre plages de magics des miroirs paper.
#   220000 - 249999    miroir 1, le magic du paper lui-meme
#  4220000 - 4249999   miroir 2, ancien regime de sortie
#  5220000 - 5249999   miroir 5, meme entree filtree par le CVD
#  6220000 - 6249999   miroir 6, sortie en trailing 0.50R
# Sans sa plage, une branche ouvrirait sur le compte du moteur sans
# jamais etre copiee ici : elle existerait sans etre lisible.
PLAGES = ((220000, 249999), (4220000, 4249999), (5220000, 5249999),
          (6220000, 6249999))''')]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.cible):
        print("ABANDON : %s introuvable." % a.cible)
        return 2
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    if MARQUEUR in src:
        print("DEJA POSE : la plage 6220000 est presente.")
        return 0

    neuf = src
    for i, (old, new) in enumerate(R, 1):
        n = neuf.count(old)
        if n != 1:
            print("REFUS : ancre %d attendue 1 fois, trouvee %d." % (i, n))
            return 3
        neuf = neuf.replace(old, new, 1)
    try:
        compile(neuf, a.cible, "exec")
    except SyntaxError as e:
        print("REFUS : le resultat ne compile pas -- ligne %s : %s"
              % (e.lineno, e.msg))
        return 4

    print("1 ancre posee, resultat compile.")
    print("  %d -> %d octets  (+%d)" % (len(src), len(neuf),
                                        len(neuf) - len(src)))
    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancez avec --appliquer.")
        return 0

    sauve = "%s.avant_plage6_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.cible, sauve)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        relu = f.read()
    ok = MARQUEUR in relu
    print("")
    print("sauvegarde  : %s" % os.path.basename(sauve))
    print("VERIFICATION : %s" % ("ok" if ok else "ECHEC"))
    if not ok:
        shutil.copy2(sauve, a.cible)
        print("Le fichier a ete REMIS dans son etat d origine.")
        return 5
    print("")
    print("Les DEUX roles du pont doivent etre redemarres : lecteur et")
    print("envoyeur portent chacun leur copie compilee de PLAGES.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

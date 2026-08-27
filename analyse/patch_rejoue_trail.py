#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_rejoue_trail.py -- mon trailing posait son stop SOUS l entree.

LE DEFAUT
---------
Le trailing s armait a +0.50R et posait son niveau a `pic - d.R`. Avec
une distance de 1.50R, au moment de l armement le pic vaut 0.50R et le
niveau vaut donc :

    0.50R - 1.50R = -1.00R

Un stop a MOINS UN R. Ce n est pas une protection, c est une perte
inventee que le trade n a jamais subie -- et comme le rejeu ne
modelise pas le stop d origine, rien ne la bornait.

Trois des quatre colonnes de trailing etaient dans ce cas :

    TR 0.50R  arme a 0.50R -> premier niveau  0.00R   correct
    TR 0.75R  arme a 0.50R -> premier niveau -0.25R   invente
    TR 1.00R  arme a 0.50R -> premier niveau -0.50R   invente
    TR 1.50R  arme a 0.50R -> premier niveau -1.00R   invente

Ce seul defaut explique que TOUTES les colonnes de trailing perdent
dans l essai du 27/08, et que la perte croisse avec la distance.

Les colonnes BE ne sont pas touchees : leur niveau est l entree, par
definition. Les colonnes combinees non plus : le BE y declenche avant
l armement et le trail ne remplace un niveau que s il est MEILLEUR.

LA CORRECTION
-------------
Le trailing ne s arme pas avant que son premier niveau soit au moins a
l entree -- soit un armement a max(arme, distance). Et une ceinture :
meme arme au bon moment, le niveau est borne a l entree.

Un TR d.R est donc desormais un vrai trailing pur : il ne fait rien
tant que le pic n a pas atteint d.R, puis il suit a d.R sous le pic
sans jamais redescendre. Le couple break-even + trailing reste teste a
part, dans la troisieme table.

Quatorze cas verifies a la main, dont les quatre du defaut.

USAGE
-----
    python patch_rejoue_trail.py                 <- simulation
    python patch_rejoue_trail.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys
import time

CIBLE_DEFAUT = "rejoue_sorties.py"
MARQUEUR = "seuil_arme"
TAILLE_AVANT = 28005
TAILLE_APRES = 28647

R = []

R.append((
'''        avance = (best - entree) * sens
        if not arme_ok and arme is not None and avance >= arme * r_pts:
            arme_ok = True

        niveau = None
        if be is not None and avance >= be * r_pts:
            niveau = entree
        if trail is not None and arme_ok:
            t = best - sens * trail * r_pts
            if niveau is None or (t - niveau) * sens > 0:
                niveau = t''',
'''        avance = (best - entree) * sens
        # Le trailing ne s arme pas avant que son PREMIER niveau soit au
        # moins a l entree. Arme a 0.50R avec une distance de 1.50R, il
        # posait son stop a -1.00R : ce n est pas une protection, c est
        # une perte inventee que le trade n a jamais subie. Ce defaut
        # expliquait a lui seul que toutes les colonnes de trailing
        # perdent, le 27/08.
        seuil_arme = arme if arme is None else max(arme, trail or 0.0)
        if not arme_ok and seuil_arme is not None \\
                and avance >= seuil_arme * r_pts:
            arme_ok = True

        niveau = None
        if be is not None and avance >= be * r_pts:
            niveau = entree
        if trail is not None and arme_ok:
            t = best - sens * trail * r_pts
            # Ceinture : meme arme au bon moment, un stop ne descend
            # jamais sous l entree.
            if (t - entree) * sens < 0:
                t = entree
            if niveau is None or (t - niveau) * sens > 0:
                niveau = t'''))

R.append((
'''    table("TRAILING SEUL -- arme a +%.2fR, suit a d.R sous le plus haut"
          % TR_ARME,''',
'''    table("TRAILING SEUL -- arme au plus tard a +d.R, suit a d.R sous le pic",'''))


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
        print("DEJA POSE : le marqueur %s est present." % MARQUEUR)
        return 0
    if len(src) != TAILLE_AVANT:
        print("REFUS : %s fait %d octets, %d attendus."
              % (a.cible, len(src), TAILLE_AVANT))
        print("Pose d abord patch_rejoue_diag.py, ou verifie la copie.")
        return 3

    neuf = src
    for i, (old, new) in enumerate(R, 1):
        n = neuf.count(old)
        if n != 1:
            print("REFUS : ancre %d attendue 1 fois, trouvee %d." % (i, n))
            return 4
        neuf = neuf.replace(old, new, 1)
    try:
        compile(neuf, a.cible, "exec")
    except SyntaxError as e:
        print("REFUS : le resultat ne compile pas -- ligne %s : %s"
              % (e.lineno, e.msg))
        return 5
    if len(neuf) != TAILLE_APRES:
        print("REFUS : le resultat fait %d octets, %d attendus."
              % (len(neuf), TAILLE_APRES))
        return 6

    print("%d ancre(s) posee(s), resultat compile, taille exacte." % len(R))
    print("  %d -> %d octets" % (len(src), len(neuf)))
    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancez avec --appliquer.")
        return 0

    sauve = "%s.avant_trail_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.cible, sauve)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        relu = f.read()
    ok = (MARQUEUR in relu) and (len(relu) == TAILLE_APRES)
    print("")
    print("sauvegarde  : %s" % os.path.basename(sauve))
    print("VERIFICATION : %s" % ("ok" if ok else "ECHEC"))
    if not ok:
        shutil.copy2(sauve, a.cible)
        print("Le fichier a ete REMIS dans son etat d origine.")
        return 7
    return 0


if __name__ == "__main__":
    sys.exit(main())

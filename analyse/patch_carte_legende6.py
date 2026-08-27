#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_carte_legende6.py -- la legende BR nomme enfin la branche 6.

CE QU IL CORRIGE
----------------
patch_carte_branche6 a rendu la ligne lisible dans le tableau :

    240003  ACCORD M15 HAUSSIER [MR]  6  |  n 27  70%  52%  +4.32  +116.61

mais la legende du bas ne decrit toujours que les branches 1, 2 et 5.
Qui cherche ce que vaut la colonne BR n y trouve pas le 6 : la ligne
passe alors pour du bruit, et c est exactement ce qui s est produit.

Une colonne dont une valeur n est expliquee nulle part est une colonne
qu on ne lit pas.

CE QU IL AJOUTE
---------------
Quatre lignes, a la suite de celles de la branche 5, dans la meme forme
et avec le meme retrait : ce que la branche 6 partage avec la 1 (meme
entree, meme lot, meme instant, sur les seuls accords M15), ce qui la
distingue (la sortie suit un trailing a 0.50R), et donc ce que l ecart
entre les deux lignes mesure -- ce trailing, et rien d autre.

C est la meme phrase de fin que pour les branches 2 et 5, parce que
c est la meme idee : chaque branche isole UNE variable.

USAGE
-----
    python patch_carte_legende6.py                 <- simulation
    python patch_carte_legende6.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import time

CIBLE_DEFAUT = "cartes_live.py"
MARQUEUR = "6 = miroir 6"

# La derniere ligne de la legende de la branche 5. Le retrait du texte
# est repris de la ligne trouvee, pas suppose : c est lui qui aligne la
# suite sous "BR".
RE_FIN5 = re.compile(
    r"^(?P<i>[ \t]*)a\(\"(?P<p>[^\"]*ne mesure donc que ce filtre\.)\"\)",
    re.M)

SUITE = ('{i}a("{pad}6 = miroir 6, le magic prefixe d un 6 : MEME entree")\n'
         '{i}a("{pad}que la 1, MEME lot, MEME instant, sur les seuls")\n'
         '{i}a("{pad}accords M15 -- mais la sortie suit un trailing a")\n'
         '{i}a("{pad}0.50R. L ecart entre la 1 et la 6 ne mesure donc")\n'
         '{i}a("{pad}que ce trailing.")')


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
        print("DEJA POSE : la legende de la branche 6 est presente.")
        return 0

    trouves = RE_FIN5.findall(src)
    if len(trouves) != 1:
        print("REFUS : la fin de la legende de la branche 5 attendue 1 fois,"
              " trouvee %d." % len(trouves))
        print("        Envoyez-moi le bloc 'BR      1 = miroir 1' tel qu il")
        print("        est ecrit dans cartes_live.py.")
        return 3

    m = RE_FIN5.search(src)
    p = m.group("p")
    pad = p[:len(p) - len(p.lstrip())]
    bloc = SUITE.format(i=m.group("i"), pad=pad)
    if "\r\n" in src:
        bloc = bloc.replace("\n", "\r\n")
    neuf = src[:m.end()] + ("\r\n" if "\r\n" in src else "\n") + bloc \
        + src[m.end():]

    try:
        compile(neuf, a.cible, "exec")
    except SyntaxError as e:
        print("REFUS : le resultat ne compile pas -- ligne %s : %s"
              % (e.lineno, e.msg))
        return 4

    print("1 ancre posee, resultat compile.")
    print("  retrait du texte repris : %d espace(s)" % len(pad))
    print("  %d -> %d octets  (+%d)" % (len(src), len(neuf),
                                        len(neuf) - len(src)))
    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancez avec --appliquer.")
        return 0

    sauve = "%s.avant_leg6_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.cible, sauve)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        relu = f.read()
    ok = MARQUEUR in relu
    print("")
    print("sauvegarde   : %s" % os.path.basename(sauve))
    print("VERIFICATION : %s" % ("ok" if ok else "ECHEC"))
    if not ok:
        shutil.copy2(sauve, a.cible)
        print("Le fichier a ete REMIS dans son etat d origine.")
        return 5
    print("")
    print("boucle_cartes_live relit le module a chaque tour : la prochaine")
    print("generation portera la legende. Rien a redemarrer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

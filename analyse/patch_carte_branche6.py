#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_carte_branche6.py -- le panneau apprend a lire la branche 6.

CE QU IL CORRIGE
----------------
base_et_branche() connait le prefixe 4 (miroir 2) et le prefixe 5
(miroir 5). Pas le 6. Un magic 6240003 retombe donc dans le cas par
defaut et le panneau l affiche ainsi :

    6240003  (non repertorie) [?]   1  |  n 16   +4.10/tr   +65.63

Trois erreurs dans une seule ligne : la base est donnee comme 6240003 au
lieu de 240003, la branche comme 1 au lieu de 6, et la strategie passe
pour inconnue alors que c est ACCORD M15 HAUSSIER.

Et cette ligne est celle qui compte aujourd hui. Sur le meme signal :

    240003   miroir 1   n 29   -11.95/tr   -346.60
    240003   miroir 2   n 32    -1.51/tr    -48.20
    240003   miroir 5   n 10    -3.54/tr    -35.41
    6240003  branche 6  n 16    +4.10/tr    +65.63

La seule des quatre en positif, et le panneau ne la rattache pas a son
signal -- donc la comparaison ne saute pas aux yeux, alors que c est
exactement la question posee le 27/08 : le trailing 0.50R sauve-t-il les
accords M15 ?

Seize prises ne prouvent rien. Mais elles doivent au moins etre lisibles
en face des trois autres branches du meme signal.

USAGE
-----
    python patch_carte_branche6.py                 <- simulation
    python patch_carte_branche6.py --appliquer
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
MARQUEUR = "6220000"

# Ancre tolerante aux espaces, exigee exactement une fois : le bloc de la
# branche 5 suivi du retour par defaut.
RE_BR5 = re.compile(
    r"(?P<i>[ \t]*)if 5220000 <= m <= 5249999:[ \t]*\r?\n"
    r"[ \t]*return m - 5000000, 5[ \t]*\r?\n"
    r"(?P<j>[ \t]*)return m, 1")

NEUF = '''{i}if 5220000 <= m <= 5249999:
{i}    return m - 5000000, 5
{i}if 6220000 <= m <= 6249999:
{i}    # La branche 6 prend la MEME entree que la 1, sur les seuls accords
{i}    # M15, et la suit en trailing 0.50R. L ecart entre les deux ne
{i}    # mesure donc que ce trailing.
{i}    return m - 6000000, 6
{j}return m, 1'''


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
        print("DEJA POSE : la plage 6220000 est presente dans %s." % a.cible)
        return 0

    crlf = "\r\n" in src
    trouves = RE_BR5.findall(src)
    if len(trouves) != 1:
        print("REFUS : le bloc de la branche 5 attendu 1 fois, trouve %d."
              % len(trouves))
        print("        Envoyez-moi base_et_branche telle qu elle est.")
        return 3

    m = RE_BR5.search(src)
    bloc = NEUF.format(i=m.group("i"), j=m.group("j"))
    if crlf:
        bloc = bloc.replace("\n", "\r\n")
    neuf = src[:m.start()] + bloc + src[m.end():]

    try:
        compile(neuf, a.cible, "exec")
    except SyntaxError as e:
        print("REFUS : le resultat ne compile pas -- ligne %s : %s"
              % (e.lineno, e.msg))
        return 4

    print("1 ancre posee, resultat compile.")
    print("  %d -> %d octets  (+%d)" % (len(src), len(neuf),
                                        len(neuf) - len(src)))
    print("  fins de ligne : %s" % ("CRLF" if crlf else "LF"))
    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancez avec --appliquer.")
        return 0

    sauve = "%s.avant_br6_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
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
    print("Le panneau est regenere par boucle_cartes_live.py, qui relit")
    print("cartes_live a chaque tour : la prochaine generation portera")
    print("deja la branche 6. Rien a redemarrer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

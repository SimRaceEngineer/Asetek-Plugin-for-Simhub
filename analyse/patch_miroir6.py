#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_miroir6.py -- la branche 6, posee DESARMEE.

CE QU ELLE EST
--------------
Meme entree, meme lot, meme instant que les branches 1 et 2. Le magic
porte un 6 en prefixe -- 240004 devient 6240004 -- et sa SORTIE est
confiee a trail_miroir6.py, qui avance le stop a 0.50R sous le plus
haut sans jamais le faire reculer.

RESERVEE AUX DEUX ACCORD M15, ET A EUX SEULS
--------------------------------------------
Le rejeu barre par barre du 27/08 a passe treize politiques de sortie
sur un mois. Toutes detruisent la queue -- les 5 % de gagnants qui
portent 31 % du gain brut. Deux lignes seulement echappent au verdict :

    240004 ACCORD M15 BAISSIER   TR 0.50R   +1286 sur 59 prises
    240003 ACCORD M15 HAUSSIER   TR 0.50R      +4 sur 59 prises

59 prises sur 983, parce que l essai s etait arrete a --limite 300.
C est peu, et la branche 6 existe pour porter cette mesure en reel sur
ces deux magics -- pas pour generaliser un resultat qui, ailleurs,
s effondre.

ELLE EST POSEE DESARMEE, ET C EST VOULU
---------------------------------------
    MIROIR6 = False

Le prefixe 6 n est connu d AUCUN module de sortie existant. Une
position de la branche 6 ouverte alors que trail_miroir6.py ne tourne
pas resterait sans surveillance jusqu au stop-placeholder -- lequel
est a 200 points sur SPX500 quand la perte moyenne y vaut 5.5 points.

L ordre de pose est donc : le gardien d abord, la branche ensuite.
Pour armer, une fois trail_miroir6.py en marche :

    (Get-Content miroir_papers.py) -replace '^MIROIR6 = False$',
        'MIROIR6 = True' | Set-Content miroir_papers.py

OU ELLE S INSERE, ET POURQUOI LA
--------------------------------
Juste apres la branche 2 et AVANT le bloc de la branche 5. Ce dernier
porte un `continue` quand le CVD refuse : place apres lui, la branche
6 serait sautee chaque fois que le CVD dit non, sans que rien ne le
signale.

USAGE
-----
    python patch_miroir6.py                 <- simulation
    python patch_miroir6.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys
import time

CIBLE_DEFAUT = "miroir_papers.py"
MARQUEUR = "magic_trail"

R = []

R.append((
'''def magic_cvd(magic):
    """240004 -> 5240004. DANS la plage exemptee, comme le miroir 1."""
    return int("5%d" % int(magic))
''',
'''def magic_cvd(magic):
    """240004 -> 5240004. DANS la plage exemptee, comme le miroir 1."""
    return int("5%d" % int(magic))


# --- MIROIR 6 : la meme entree, une sortie en trailing 0.50R ---------------
# Le magic porte un 6 en prefixe -- 240004 -> 6240004. Sa sortie n est
# geree par AUCUN module existant : elle appartient a trail_miroir6.py,
# qui avance le stop a 0.50R sous le plus haut sans jamais le faire
# reculer.
#
# DESARMEE PAR DEFAUT. Le prefixe 6 est inconnu du reste de la stack :
# une position ouverte ici alors que le gardien ne tourne pas resterait
# sans surveillance jusqu au stop-placeholder. Le gardien d abord.
MIROIR6 = False

# Reservee aux deux ACCORD M15. Le rejeu du 27/08 a montre qu un
# trailing a 0.50R est nettement positif sur 240004 et neutre sur
# 240003, et destructeur a peu pres partout ailleurs.
ACCORDS_M15 = (240003, 240004)


def magic_trail(magic):
    """240004 -> 6240004. Meme entree que le miroir 2, sortie en trailing."""
    return int("6%d" % int(magic))
'''))

R.append((
'''                else:
                    dit("    M%s REFUSE : %s  -- paire incomplete,"
                        " ce parent ne comptera pas" % (m2, e2))
                if not MIROIR5:
                    continue''',
'''                else:
                    dit("    M%s REFUSE : %s  -- paire incomplete,"
                        " ce parent ne comptera pas" % (m2, e2))
                # La branche 6 est posee ICI, avant le bloc du CVD : ce
                # dernier porte un `continue` quand il refuse, et la
                # branche 6 serait alors sautee sans que rien ne le dise.
                if MIROIR6 and int(magic) in ACCORDS_M15:
                    m6 = magic_trail(magic)
                    tm6, e6 = self.envoie(pos, rec, m6, nom, t_signal, 1)
                    if tm6:
                        self.liens.setdefault(tk, []).append((m6, tm6))
                        dit("    M%s envoye, ticket %s  (trailing 0.50R)"
                            % (m6, tm6))
                    else:
                        dit("    M%s REFUSE : %s" % (m6, e6))
                if not MIROIR5:
                    continue'''))


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

    neuf = src
    for i, (old, new) in enumerate(R, 1):
        n = neuf.count(old)
        if n != 1:
            print("REFUS : ancre %d attendue 1 fois, trouvee %d." % (i, n))
            print("Le voisinage a change. Je ne vise pas a l aveugle dans")
            print("un fichier qui ouvre des positions.")
            return 3
        neuf = neuf.replace(old, new, 1)
    try:
        compile(neuf, a.cible, "exec")
    except SyntaxError as e:
        print("REFUS : le resultat ne compile pas -- ligne %s : %s"
              % (e.lineno, e.msg))
        return 4

    print("2 ancre(s) posee(s), resultat compile.")
    print("  %d -> %d octets  (+%d)" % (len(src), len(neuf),
                                        len(neuf) - len(src)))
    print("  branche 6 : DESARMEE (MIROIR6 = False)")
    print("  magics vises : 240003, 240004 -> 6240003, 6240004")
    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancez avec --appliquer.")
        return 0

    sauve = "%s.avant_miroir6_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.cible, sauve)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        relu = f.read()
    ok = (MARQUEUR in relu) and ("MIROIR6 = False" in relu)
    print("")
    print("sauvegarde  : %s" % os.path.basename(sauve))
    print("VERIFICATION : %s" % ("ok" if ok else "ECHEC"))
    if not ok:
        shutil.copy2(sauve, a.cible)
        print("Le fichier a ete REMIS dans son etat d origine.")
        return 5
    print("")
    print("miroir_papers.py doit etre redemarre pour que la branche")
    print("existe -- et elle restera DESARMEE tant que MIROIR6 vaut False.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_miroir_lasterror.py -- faire dire au miroir POURQUOI l envoi echoue.

LE DEFAUT
---------
Depuis 14:53 le 27/08, chaque envoi du miroir revient :

    M240004 REFUSE : retcode=None sans reponse

`order_send` a rendu None. Le message le constate et jette la seule
chose qui l explique : `mt5.last_error()`. On tourne donc en rond sur
des hypotheses -- le cliquet, un conflit de threads, la marge -- alors
que le terminal a la reponse et qu on ne la lui demande pas.

Le code fautif, ligne 652 :

    return None, "retcode=%s %s" % (rc, res.comment if res else "sans reponse")

Quand `res` vaut None il n y a ni retcode ni commentaire : la branche
"sans reponse" ne dit rien de plus que ce qu on voit deja.

CE QU ON AJOUTE
---------------
Deux choses, et seulement dans le cas None :

    last_error()  le code et le libelle du terminal. C est lui qui
                  distingue une IPC coupee d une requete malformee.
    la requete    chaque cle et sa valeur, telles qu envoyees. Si un
                  champ est du mauvais type, il se voit.

Le cas normal -- res present avec un retcode -- n est pas touche.

Ce patch ne change AUCUN comportement : il ne modifie ni la requete,
ni la decision, ni le retour. Il ajoute du texte a un message d erreur.

USAGE
-----
    python patch_miroir_lasterror.py                 <- simulation
    python patch_miroir_lasterror.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys
import time

CIBLE_DEFAUT = "miroir_papers.py"
MARQUEUR = "last_error"

AVANT = ('        return None, "retcode=%s %s" '
         '% (rc, res.comment if res else "sans reponse")')

APRES = '''        if res is None:
            # order_send a rendu None : ni retcode ni commentaire. La
            # seule explication est dans le terminal, et le message
            # d origine la jetait.
            try:
                _err = mt5.last_error()
            except Exception as _e:
                _err = "indisponible : %s" % _e
            try:
                _cles = ", ".join("%s=%r" % (k, v)
                                  for k, v in sorted(req.items()))
            except Exception:
                _cles = repr(req)[:400]
            return None, ("retcode=None sans reponse"
                          " -- last_error %s -- req %s" % (_err, _cles))
        return None, "retcode=%s %s" % (rc, res.comment)'''


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
        print("DEJA POSE : last_error est deja demande.")
        return 0

    n = src.count(AVANT)
    if n != 1:
        print("REFUS : ancre attendue 1 fois, trouvee %d." % n)
        print("Ligne cherchee :")
        print("  " + AVANT.strip())
        return 3
    neuf = src.replace(AVANT, APRES, 1)
    try:
        compile(neuf, a.cible, "exec")
    except SyntaxError as e:
        print("REFUS : le resultat ne compile pas -- ligne %s : %s"
              % (e.lineno, e.msg))
        return 4

    print("1 ancre posee, resultat compile.")
    print("  %d -> %d octets  (+%d)" % (len(src), len(neuf), len(neuf) - len(src)))
    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        return 0

    sauve = "%s.avant_lasterror_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
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
    print("miroir_papers.py doit etre redemarre pour que le message change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

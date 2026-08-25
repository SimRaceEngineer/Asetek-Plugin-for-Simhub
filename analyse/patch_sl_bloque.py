#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_sl_bloque.py -- l arbitre des stops passe d observer a refuser.

CE QU IL A MESURE, ET CE QUE CA COUTE
-------------------------------------
sl_arbitre.py enveloppe mt5.order_send au demarrage du moteur et
applique une regle unique : un stop ne recule jamais. Pour un achat il
ne descend pas, pour une vente il ne monte pas. Rien d autre n est
arbitre.

Depuis le 24/08 il tourne en OBSERVATION -- il journalise et laisse
passer. Le 25/08 a 16:28 son bilan tenait en une ligne :

    [SL-ARBITRE] sl_freeze_176 = 190800 (159 reculs, 8368.6 pts)

Un seul module, 159 reculs, huit mille trois cent soixante-huit points
rendus au marche. Une ligne typique :

    sl_freeze_176 ticket 172652664 SELL 29195.30 -> 29297.55
                                          RECUL 102.2 pts (observe)

Cent deux points de gain deja securise, repousses. C est exactement le
defaut signale : "on ne securise pas de gains alors qu on pourrait le
faire".

POURQUOI MAINTENANT ET PAS AVANT
    Le module est charge en memoire par le moteur. Basculer
    l interrupteur ne change rien tant que le processus tourne. Ce
    correctif n a de sens qu applique JUSTE AVANT un redemarrage --
    sinon il dort des jours.

CE QUE BLOQUE = True CHANGE, ET CE QU IL NE CHANGE PAS
    Il REFUSE les reculs averes. Il ne touche ni aux ouvertures, ni aux
    fermetures, ni aux TP, ni aux volumes. Et il reste FAIL-OPEN
    partout : action autre que SLTP, champ manquant, position
    introuvable, exception, stop pas encore pose -- la requete passe.
    Un arbitre en panne laisse jouer.

    Le risque n est donc pas d empecher un stop de se poser, c est
    qu un module qui ELARGIT deliberement un stop se voie refuser. La
    liste EXEMPTS existe pour ca, et elle reste vide : elargir un stop
    augmente le risque de la position, ce qui demande un argument.

    Si sl_freeze_176 se met a boucler sur ses refus, ca se verra dans
    le journal -- et le retour arriere est d une ligne.

USAGE
-----
    python patch_sl_bloque.py                 <- simulation
    python patch_sl_bloque.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\sl_arbitre.py"
SUFFIXE_BAK = ".bak_bloque"

VIEUX = ("BLOQUE = False          # False = observe et laisse passer."
         " True = refuse.")
NEUF = ("BLOQUE = True           # mesure faite le 25/08 : sl_freeze_176,"
        " 159\n"
        "                        # reculs, 8368.6 points rendus. On refuse.")


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 66)
    print("patch_sl_bloque -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 66)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))

    if "BLOQUE = True" in s:
        print("")
        print("Deja corrige : l arbitre refuse deja les reculs.")
        return 0
    n = s.count(VIEUX)
    if n != 1:
        print("")
        print("REFUS : la ligne BLOQUE attendue 1 fois, trouvee %d." % n)
        print("Elle a change de forme. Me la montrer : je ne devine pas")
        print("l interrupteur qui decide des stops.")
        return 1
    print("        la ligne BLOQUE est unique.")
    print("")
    print("a faire :")
    print("   ~ BLOQUE False -> True : les reculs de stop sont REFUSES")
    print("")
    print("   La regle ne touche ni aux ouvertures, ni aux fermetures, ni")
    print("   aux TP, ni aux volumes. Elle reste fail-open : une lecture")
    print("   manquante laisse passer.")

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
    if "BLOQUE = True" not in relu:
        print("relu   : INCOMPLET -- restaurer %s" % bak)
        return 1
    try:
        compile(relu, a.cible, "exec")
    except SyntaxError as e:
        print("syntaxe: ERREUR ligne %s -- restaurer %s" % (e.lineno, bak))
        return 1
    print("relu   : BLOQUE = True, le fichier compile.")
    print("")
    print("-" * 66)
    print("N A D EFFET QU AU PROCHAIN DEMARRAGE DU MOTEUR. Le module est")
    print("charge en memoire : tant que le processus tourne, il applique")
    print("la version d avant.")
    print("")
    print("Au redemarrage, l arbitre annoncera OBSERVATION ou BLOQUE dans")
    print("sa premiere ligne de journal. C est la qu on verifie.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

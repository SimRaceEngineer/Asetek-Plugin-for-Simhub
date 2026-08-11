#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_sar_appel.py -- suivre une position meme sans signal actif

A poser APRES patch_sar_couverture.py.

LE TROISIEME VERROU, ET LE PLUS SERRE DES TROIS
    Dans la boucle des motifs :

        with _lock:
            sig = _active_signals.get(asset)
        if sig and _has_position(asset):
            _update_trailing(asset, sig)

    _update_trailing n est appelee QUE s il existe un signal actif pour
    l actif. Une position ouverte il y a une heure, dont le signal a
    expire ou a ete remplace depuis, n est jamais suivie : la fonction
    n est meme pas appelee.

    C est en amont des deux defauts corriges le 10/08 au soir. On avait
    reparé la maniere dont la fonction choisit ses positions, sans voir
    qu elle n etait pas appelee du tout la plupart du temps. Cela explique
    les 8 a 20 pour cent de tickets avec trajectoire de stop bien mieux
    que le filtre de magic.

POURQUOI LE CORRECTIF EST SUR
    Depuis patch_sar_couverture.py, _update_trailing n utilise plus
    "signal" : les deux branches lisent p.type. Le parametre est devenu
    inutile, donc la condition qui le protege aussi. On passe sig tel
    quel -- il peut valoir None, la fonction ne le regarde pas.

    Le risque reste borne comme avant : le trail SAR est monotone
    (sar_val > p.sl a l achat, sar_val < p.sl a la vente) et la garde de
    patch_sl_garde.py refuse tout recul. Elargir l appel ne peut que
    RESSERRER des stops.

CE QU IL FAUT SURVEILLER APRES
    Le taux de tickets avec trajectoire de stop, dans monitor_export.py.
    Il etait a 20 pour cent le 10/08 et 8 pour cent le 11/08 au matin.
    S il ne monte pas franchement apres ce patch, alors le filtre de magic
    pese davantage qu on ne le croit et c est lui qu il faut ouvrir --
    mais avec les chiffres de SAR-COUVERTURE, pas a l intuition.

IDEMPOTENT.
"""
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "price_action.py"

ANCRE = """        if sig and _has_position(asset):
            _update_trailing(asset, sig)"""

NEUF = """        # 11/08 : le suivi ne dependait de l existence d un signal actif que
        # par accident -- _update_trailing lisait signal["direction"]. Elle
        # lit p.type depuis le 10/08, donc une position se suit qu un signal
        # soit en cours ou non. C etait le verrou le plus serre des trois.
        if _has_position(asset):
            _update_trailing(asset, sig)"""


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable -- lance depuis le dossier de la stack." % CIBLE)
        return 1

    src, enc = lire(CIBLE)
    print("%s : %d lignes, encodage %s" % (CIBLE, src.count("\n") + 1, enc))

    if "_sar_trail_autorise" not in src:
        print("KO : patch_sar_couverture.py n a pas ete pose.")
        print("Sans lui _update_trailing lit encore signal[\"direction\"], et")
        print("l appeler sans signal actif ne servirait a rien.")
        return 1
    if NEUF in src or "le verrou le plus serre des trois" in src:
        print("Deja pose -- rien a faire.")
        return 0

    n = src.count(ANCRE)
    if n != 1:
        print("KO : %d occurrence(s) de l ancre, il en faut 1 :" % n)
        print()
        for l in ANCRE.split("\n"):
            print("    " + l)
        return 1

    neuf = src.replace(ANCRE, NEUF, 1)
    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    sauve = "%s.bak-%s" % (CIBLE, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(CIBLE, sauve)
    io.open(CIBLE, "w", encoding=enc).write(neuf)
    print("Sauvegarde : %s" % sauve)
    print()
    print("Le suivi est desormais appele des qu une position existe, qu un")
    print("signal soit actif ou non. Redemarre price_action.py SEUL.")
    print()
    print("A surveiller dans deux heures :")
    print("  (Invoke-WebRequest http://localhost:8081 -UseBasicParsing).Content")
    print("      | python monitor_export.py --champs")
    print("Le taux 'trajectoire de stop' doit monter franchement au-dessus")
    print("des 8 pour cent de ce matin. Sinon, c est le filtre de magic.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

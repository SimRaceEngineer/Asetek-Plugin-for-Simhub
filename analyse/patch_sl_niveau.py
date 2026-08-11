#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_sl_niveau.py -- [SL-ECRIT] en warning, parce que info n arrive pas

A poser APRES patch_sl_journal.py.

CE QU ON A CONSTATE LE 11/08 A 11h
    Les trois releves etaient vides. Le test decisif : le marqueur
    "[TRAIL]", qui existe dans _update_trailing DEPUIS TOUJOURS et bien
    avant nos patchs, n apparait dans AUCUN journal -- alors que le panel
    montrait des evenements (TRAIL) le 10/08 a 15:26 et 17:05, et que
    price_action_20260810.log pese 366 Ko.

    Conclusion : le fichier de journal ne recoit pas le niveau info. Tout
    ce que la stack ecrit en log.info est perdu, y compris le [SL-ECRIT]
    pose cette nuit.

    C etait une erreur de ma part : avoir choisi info sans verifier ce que
    le logger ecrit reellement. Le symptome est le pire qui soit -- pas
    d erreur, pas d avertissement, juste un journal vide qu on aurait pu
    lire comme "il ne se passe rien".

CE QUE FAIT CE PATCH
    Une ligne. log.info -> log.warning sur le [SL-ECRIT]. Les reculs
    etaient deja en warning et n avaient donc pas ce probleme.

VOLUME, ET COMMENT REVENIR EN ARRIERE
    Une ligne par ecriture de stop. Si c est trop bruyant apres une
    journee, remettre log.warning a log.info : on perdra le detail mais on
    gardera les reculs, qui sont l essentiel.

    Ce patch est un instrument de mesure, pas un reglage definitif. Une
    fois la question tranchee -- l ancre defait-elle le trail tous les
    jours ou une fois par mois -- il faudra le retirer.

IDEMPOTENT.
"""
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "price_action.py"

ANCRE = '''        log.info("  [SL-ECRIT] %s ticket %s %s %.2f -> %.2f %s",'''
NEUF = '''        log.warning("  [SL-ECRIT] %s ticket %s %s %.2f -> %.2f %s",'''


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

    if NEUF in src:
        print("Deja en warning -- rien a faire.")
        return 0
    n = src.count(ANCRE)
    if n != 1:
        print("KO : %d occurrence(s) de l ancre, il en faut 1 :" % n)
        print("    " + ANCRE.strip())
        print()
        print("Si patch_sl_journal.py n a pas ete passe, lance-le d abord.")
        return 1

    neuf = src.replace(ANCRE, NEUF, 1)
    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        return 1

    sauve = "%s.bak-%s" % (CIBLE, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(CIBLE, sauve)
    io.open(CIBLE, "w", encoding=enc).write(neuf)
    print("Sauvegarde : %s" % sauve)
    print("[SL-ECRIT] passe en warning. Redemarre price_action.py SEUL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

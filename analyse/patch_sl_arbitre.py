#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_sl_arbitre.py -- pose l arbitre des stops dans trading_engine.py

Prerequis : sl_arbitre.py a cote de trading_engine.py.

OU, ET POURQUOI LA
    Juste avant le PREMIER _start_module. A cet instant, MetaTrader5 est
    importe (ligne 3264, au niveau module) mais aucun ecrivain de stop n a
    encore demarre. L enveloppe est donc en place avant la premiere ecriture,
    ce qui est la seule position correcte : posee plus tard, elle laisserait
    passer tout ce qui precede.

CE QUE CA COUVRE
    Tous les modules qui font "import MetaTrader5 as mt5" puis
    "mt5.order_send(...)". Python met le module en cache, donc ils partagent
    le meme objet et l enveloppe vaut pour tous -- y compris les alias
    _mt5raw, _mt5raw251, _mt5raw175 et les autres, qui designent le meme
    objet.

    Echapperait un module qui ferait "from MetaTrader5 import order_send" :
    il aurait capture la fonction d origine avant le remplacement. Aucun ne
    le fait dans ce depot, mais c est la limite a connaitre.

MODE OBSERVATION
    sl_arbitre.BLOQUE vaut False : l arbitre journalise et laisse passer.
    Une journee dira qui recule, combien de fois, de combien de points.
    Passer a True ensuite, en connaissance de cause -- et le passage se fait
    dans sl_arbitre.py, sans retoucher au moteur.

IDEMPOTENT.
"""
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "trading_engine.py"
BESOIN = "sl_arbitre.py"
# Le marqueur doit etre une chaine REELLEMENT presente dans le bloc pose.
# Premier jet : "sl_arbitre.install", introuvable puisque le code ecrit
# "_sl_arb.install" -- le patch se serait applique deux fois.
MARQUEUR = "import sl_arbitre as _sl_arb"

RE_ANCRE = re.compile(
    r'^([ \t]*)_start_module\("stall_watchdog", launch_stall_watchdog\)', re.M)

BLOC = '''# 11/08 : arbitre unique des ecritures de stop. Pose ICI, avant le
# premier _start_module, donc avant qu un seul ecrivain ne tourne.
# Une trentaine de modules ecrivent des stops sur les memes positions
# sans se consulter ; le 10/08 a 15:27, trois stops deja verrouilles
# ont ete ramenes au prix d entree, 105,7 points rendus. Voir
# sl_arbitre.py. Mode observation : il journalise, il ne bloque pas.
try:
    import sl_arbitre as _sl_arb
    _sl_arb.install(mt5, globals().get("log"))
except Exception as _e_arb:
    print("[SL-ARBITRE] pose impossible : %s" % _e_arb, flush=True)'''


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
    if not os.path.isfile(BESOIN):
        print("KO : %s introuvable. Copie-le a cote de %s avant de relancer."
              % (BESOIN, CIBLE))
        print("Le patch poserait un import mort.")
        return 1

    try:
        ast.parse(lire(BESOIN)[0])
    except SyntaxError as e:
        print("KO : %s ne compile pas (ligne %s) : %s" % (BESOIN, e.lineno, e.msg))
        return 1

    src, enc = lire(CIBLE)
    print("%s : %d lignes, encodage %s" % (CIBLE, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Arbitre deja pose -- rien a faire.")
        return 0

    trouve = RE_ANCRE.findall(src)
    if len(trouve) != 1:
        print("KO : %d occurrence(s) de l ancre, il en faut 1 :" % len(trouve))
        print('    _start_module("stall_watchdog", launch_stall_watchdog)')
        print()
        print("Si ce premier module a change de nom, dis-le : il faut poser")
        print("l arbitre AVANT le premier _start_module, pas ailleurs.")
        return 1

    ind = trouve[0]
    print("ancre trouvee : indentation %d espaces" % len(ind))
    bloc = "\n".join(ind + l if l else "" for l in BLOC.split("\n"))
    neuf = RE_ANCRE.sub(lambda m: bloc + "\n" + m.group(0), src, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : le fichier patche ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    sauve = "%s.bak-%s" % (CIBLE, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(CIBLE, sauve)
    io.open(CIBLE, "w", encoding=enc).write(neuf)
    print("Sauvegarde : %s" % sauve)
    print()
    print("Arbitre pose, en MODE OBSERVATION. Il prendra effet au prochain")
    print("demarrage du moteur.")
    print()
    print("Une ligne le confirmera au demarrage :")
    print("    [SL-ARBITRE] v1.0 pose sur mt5.order_send -- mode OBSERVATION")
    print()
    print("Puis, toutes les 200 ecritures de stop, une synthese :")
    print("    [SL-ARBITRE] preopen_protect=12(3 reculs, 44.1 pts) · us30_trail=98 ...")
    print()
    print("Pour relever :")
    print("    Get-ChildItem -Recurse -Filter *.log | Select-String 'SL-ARBITRE'")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_sl_garde.py -- pose la garde "un stop ne recule jamais" dans price_action.py

Meme forme que patch_rails_jauge.py et les cinq autres : une ancre, une
verification d unicite, un ast.parse avant d ecrire, une sauvegarde.
Rien d invente, la convention de la maison est reprise telle quelle.

CE QUE CE PATCH CORRIGE, ET COMMENT ON LE SAIT
    Le 10/08, trois tickets ont vu leur stop RECULER a 15:27 :

        #171930748  TRAIL 29744,45 -> BE 29805,45   61,0 points rendus
        #171937209  TRAIL 53944,70 -> BE 53967,25   22,6 points rendus
        #171937213  TRAIL 53944,20 -> BE 53966,25   22,1 points rendus

    price_action.py contient DEUX systemes qui ecrivent le stop des memes
    positions : _update_trailing (SAR M5) et l ancre (_anchor_manage,
    _tighten_anchor_sl). Le premier est deja monotone -- il ne pose que si
    sar_val > p.sl a l achat, sar_val < p.sl a la vente. Le second ne l est
    pas. Aucun des deux ne consulte l autre.

    Les CINQ points d ecriture SLTP du fichier passent par _pa_order_send,
    qui fait trois lignes. La garde se pose donc a UN endroit et couvre tout,
    sans toucher a la logique de l un ni de l autre.

MODE OBSERVATION PAR DEFAUT
    _SL_GARDE_BLOQUE = False : la garde JOURNALISE et laisse passer. Une
    journee de mesure dira combien de reculs par jour et lesquels. On ne
    bloque qu ensuite, en connaissance de cause. C est la meme discipline
    que les gels : on mesure avant de trancher.

    Pour compter, le lendemain :
        Select-String -Path <le .log> -Pattern 'SL-GARDE'

FAIL-OPEN, ET C EST ESSENTIEL
    Au moindre doute -- champ absent, position introuvable, exception -- la
    requete passe. Cette garde ne doit JAMAIS empecher la pose d un premier
    stop ni bloquer sur une erreur transitoire. Elle ne sait faire qu une
    chose : refuser un recul avere.

IDEMPOTENT : relancer le script ne fait rien si la garde est deja la.
"""
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "price_action.py"
MARQUEUR = "_sl_jamais_en_arriere"

# L ancre est le corps COMPLET de _pa_order_send tel qu il est aujourd hui.
# Si une seule ligne a change, le patch refuse de s appliquer plutot que de
# poser la garde a cote de la plaque.
ANCRE = '''def _pa_order_send(req):
    if not _PA_ORDERS_ENABLED:
        return None
    return getattr(mt5, "order_send")(req)'''

REMPLACEMENT = '''_SL_GARDE_BLOQUE = False      # False = on observe. True = on refuse.


def _sl_jamais_en_arriere(req):
    """Un stop ne recule jamais, quel que soit le systeme qui le demande.

    Pose ici et pas ailleurs : les cinq points d ecriture SLTP du fichier
    passent tous par _pa_order_send. _update_trailing est deja monotone ;
    l ancre ne l est pas, et c est elle qui a ramene un stop de 53944,2 a
    53966,25 le 10/08 a 15:27 -- 22 points de verrou rendus, sur trois
    tickets a la meme minute.

    FAIL-OPEN : au moindre doute on laisse passer. Cette garde ne doit
    jamais empecher la pose d un premier stop.
    """
    try:
        if req.get("action") != mt5.TRADE_ACTION_SLTP:
            return req
        tk = req.get("position")
        sl_neuf = req.get("sl")
        if tk is None or not sl_neuf:
            return req
        pos = mt5.positions_get(ticket=tk)
        if not pos or not pos[0].sl:
            return req                      # pas encore de stop : on pose
        p = pos[0]
        if p.type == mt5.POSITION_TYPE_BUY:
            recule = sl_neuf < p.sl
        else:
            recule = sl_neuf > p.sl
        if not recule:
            return req
        log.warning("  [SL-GARDE] ticket %s %s : %.2f -> %.2f RECUL%s",
                    tk, "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                    p.sl, sl_neuf,
                    " (refuse)" if _SL_GARDE_BLOQUE else " (observe)")
        return None if _SL_GARDE_BLOQUE else req
    except Exception:
        return req


def _pa_order_send(req):
    if not _PA_ORDERS_ENABLED:
        return None
    req = _sl_jamais_en_arriere(req)
    if req is None:
        return None
    return getattr(mt5, "order_send")(req)'''


def lire(chemin):
    """Rend (texte, encodage). price_action.py peut etre en utf-8 ou cp1252."""
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

    if MARQUEUR in src:
        print("Garde deja presente dans %s -- rien a faire." % CIBLE)
        return 0

    n = src.count(ANCRE)
    if n == 0:
        print("KO : _pa_order_send n a pas la forme attendue.")
        print()
        print("Le patch cherche exactement ces quatre lignes :")
        print()
        for l in ANCRE.split("\n"):
            print("    " + l)
        print()
        print("Verifie avec :")
        print("    Select-String -Path %s -Pattern '_pa_order_send' -Context 0,4" % CIBLE)
        print("Si le corps a change, ne force rien : dis-le, on refait l ancre.")
        return 1
    if n > 1:
        print("KO : %d occurrences de l ancre. Le patch serait ambigu." % n)
        return 1

    neuf = src.replace(ANCRE, REMPLACEMENT)

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
    print("Garde posee dans %s, en MODE OBSERVATION." % CIBLE)
    print()
    print("Elle journalise les reculs de stop et ne bloque rien.")
    print("Redemarre price_action.py pour qu elle prenne effet.")
    print()
    print("Demain, pour compter ce qu elle a vu :")
    print("    Select-String -Path <le .log> -Pattern 'SL-GARDE'")
    print()
    print("Si le compte est net et les cas homogenes, passe")
    print("_SL_GARDE_BLOQUE a True et redemarre. Pas avant.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

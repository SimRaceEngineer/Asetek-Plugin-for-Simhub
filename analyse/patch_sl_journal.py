#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_sl_journal.py -- QUI ecrit le stop, pas seulement qu il a bouge

A poser APRES patch_sl_garde.py, dont il complete la garde.

LE MANQUE QU IL COMBLE
    La garde posee le 10/08 journalise les RECULS. Elle ne dit pas qui les
    demande. Or price_action.py a deux systemes qui ecrivent le stop des
    memes positions -- _update_trailing (SAR M5) et l ancre
    (_anchor_manage, _tighten_anchor_sl) -- et _pa_order_send les recoit
    identiques : une requete anonyme.

    Tant qu on ne sait pas QUI ecrit, on ne peut ni attribuer un recul, ni
    comparer quoi que ce soit. Ce patch ajoute le nom de la fonction
    appelante a chaque ecriture de stop, reculs ET avances.

CE QUE LE JOURNAL PERMETTRA DE DIRE
    - combien d ecritures par jour, et par systeme
    - lequel des deux produit les reculs, et sur quels tickets
    - si les deux se disputent les memes positions ou se partagent le
      terrain

CE QU IL NE PERMETTRA PAS DE DIRE, ET IL FAUT ETRE NET LA-DESSUS
    Lequel des deux est le plus RENTABLE. Un journal d ecritures ne mesure
    pas une rentabilite : les deux systemes agissent sur les MEMES tickets,
    souvent l un apres l autre, et le resultat d un ticket ne se decoupe
    pas entre eux. Attribuer le P&L a celui qui a ecrit en dernier serait
    un artefact, pas une mesure.

    Pour trancher la rentabilite il faudrait un partage CONTROLE -- des
    magics tires au sort confies a l un, les autres a l autre, sur
    plusieurs semaines. C est une experience, pas une observation. Le
    dispositif en a deja une, l appariement 206/207, et c est exactement ce
    qui la rend interpretable.

    En attendant, ce journal sert a autre chose et c est deja beaucoup :
    savoir si l ancre defait le trail tous les jours ou une fois par mois.

VOLUME
    Une ligne par ecriture de stop, en info. Avec la couverture elargie du
    10/08 cela peut faire quelques centaines de lignes par seance. Si c est
    trop, passer log.info a log.debug sur la ligne [SL-ECRIT] : les reculs
    resteront en warning et donc visibles.

IDEMPOTENT.
"""
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "price_action.py"
MARQUEUR = "_sl_appelant"

ANCRE_FN = "def _sl_jamais_en_arriere(req):"

BLOC_FN = '''def _sl_appelant():
    """Nom de la fonction qui a reellement demande l ecriture du stop.

    Trois cadres plus haut : _sl_appelant <- _sl_jamais_en_arriere <-
    _pa_order_send <- le demandeur. Sans ce nom le journal dit QUE le stop
    a bouge et jamais QUI l a bouge, et on ne peut pas separer le trailing
    SAR de l ancre.
    """
    try:
        import sys as _s
        return _s._getframe(3).f_code.co_name
    except Exception:
        return "?"


def _sl_jamais_en_arriere(req):'''

ANCRE_LOG = '''        if p.type == mt5.POSITION_TYPE_BUY:
            recule = sl_neuf < p.sl
        else:
            recule = sl_neuf > p.sl
        if not recule:
            return req'''

BLOC_LOG = '''        if p.type == mt5.POSITION_TYPE_BUY:
            recule = sl_neuf < p.sl
        else:
            recule = sl_neuf > p.sl
        log.info("  [SL-ECRIT] %s ticket %s %s %.2f -> %.2f %s",
                 _sl_appelant(), tk,
                 "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                 p.sl, sl_neuf, "RECUL" if recule else "avance")
        if not recule:
            return req'''


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

    if "_sl_jamais_en_arriere" not in src:
        print("KO : la garde n est pas posee. Lance d abord patch_sl_garde.py.")
        return 1
    if MARQUEUR in src:
        print("Journal deja pose dans %s -- rien a faire." % CIBLE)
        return 0

    ancres = [(ANCRE_FN, BLOC_FN), (ANCRE_LOG, BLOC_LOG)]
    for a, _ in ancres:
        n = src.count(a)
        if n != 1:
            print("KO : %d occurrence(s) de cette ancre, il en faut 1 :" % n)
            print()
            for l in a.split("\n"):
                print("    " + l)
            return 1

    neuf = src
    for a, r in ancres:
        neuf = neuf.replace(a, r, 1)

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
    print("Journal pose. Chaque ecriture de stop portera desormais le nom")
    print("de la fonction qui l a demandee.")
    print()
    print("Redemarre price_action.py SEUL -- pas toute la stack.")
    print()
    print("Demain :")
    print("    Get-ChildItem -Recurse -Filter *.log | Select-String 'SL-ECRIT'")
    print("      | Group-Object {($_ -split ' ')[2]} | Select-Object Count,Name")
    print()
    print("Cela dira combien d ecritures par systeme. Les reculs restent")
    print("en warning sous l etiquette SL-GARDE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

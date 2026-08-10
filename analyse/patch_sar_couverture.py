#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_sar_couverture.py -- les deux defauts de couverture de _update_trailing

Meme forme que patch_sl_garde.py et les six autres : des ancres uniques
verifiees, un ast.parse avant d ecrire, une sauvegarde, idempotent.

CE QU ON A MESURE LE 10/08
    Sur 358 tickets lus dans le Trade Monitor, 20 POUR CENT seulement ont
    une trajectoire de stop. Quatre positions sur cinq n ont jamais ete
    touchees par le suivi. Ce n est pas un reglage du BE : c est de la
    couverture, et _update_trailing en donne deux causes distinctes.

DEFAUT 1 -- LE SUIVI DEPEND DU SIGNAL, PAS DE LA POSITION
        if signal["direction"] == "BUY" and sar_dir == "BUY" ...
        elif signal["direction"] == "SELL" and sar_dir == "SELL" ...

    signal["direction"] est la direction du signal EN COURS. La verite
    d une position, c est p.type. Une position acheteuse cesse donc d etre
    suivie des que le signal du moment passe vendeur -- et le panel montre
    des grappes qui alternent BUY et SELL en quelques minutes.

    C est un defaut de conception, pas un parametre : une position se suit
    d apres ce qu elle EST. Corrige en p.type.

    Consequence : le suivi agira plus souvent. C est le but. Le risque est
    borne par construction -- le trail SAR est monotone (sar_val > p.sl a
    l achat, sar_val < p.sl a la vente) et la garde posee par
    patch_sl_garde.py refuse tout recul. Ce patch ne peut donc que
    RESSERRER des stops, jamais les relacher.

    Au passage, "and p.sl > 0" est ajoute a la branche vente, qui ne
    l avait pas. C est sans effet -- sar_val est un prix, toujours positif,
    donc la branche ne pouvait deja pas partir avec p.sl a zero -- mais
    l asymetrie entre les deux branches etait une invitation a l erreur.

DEFAUT 2 -- UN SEUL MAGIC PAR ACTIF, ET ON NE SAIT PAS CE QU ON PERD
        magic = ASSETS[asset]["magic"]
        if p.magic != magic: continue

    Le panel montre au moins 206102, 207102, 206302, 207302, 206105,
    207105, 208103, 2403, 2411, 2423. Une seule famille passe.

    CE PATCH NE CHANGE PAS CE COMPORTEMENT. Il le rend explicite et
    MESURABLE : _SAR_TRAIL_MAGICS vaut None, donc exactement le magic de
    l actif comme aujourd hui, et un compteur dit desormais combien de
    positions sont ecartees et de quel magic.

    Elargir est une DECISION, pas une correction, et elle ne se prend pas
    sans les chiffres. Deux raisons de ne pas la prendre a l aveugle :

      - les magics 208xxx sont le leader-hold, qui tient sa position tant
        que L n est pas casse. Un trail SAR l en sortirait avant, et
        detruirait exactement ce que cette famille mesure.
      - les 206/207 sont l A/B apparie hold contre trail. Y appliquer un
        trail supplementaire brouillerait la seule randomisation controlee
        du dispositif.

    Demain, apres quelques heures :
        Get-ChildItem -Recurse -Filter *.log | Select-String 'SAR-COUVERTURE'
    puis on choisit ce qu on met dans _SAR_TRAIL_MAGICS.

IDEMPOTENT : relancer ne fait rien si le patch est deja pose.
"""
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "price_action.py"
MARQUEUR = "_sar_trail_autorise"

ANCRE_BLOC = "def _update_trailing(asset, signal):"

BLOC = '''# --------------------------------------------------------------------------
# Couverture du suivi SAR : quelles positions _update_trailing a le droit
# de toucher. Pose le 10/08.
#
# None = comportement d origine, strictement inchange : le seul magic
# declare pour l actif. Pour elargir, mettre un ensemble, par exemple
#     _SAR_TRAIL_MAGICS = {206102, 207102}
# NE PAS y mettre les 208xxx : le leader-hold tient tant que L n est pas
# casse, un trail SAR l en sortirait avant.
# --------------------------------------------------------------------------
_SAR_TRAIL_MAGICS = None
_SAR_TRAIL_IGNORES = {}
_SAR_TRAIL_DERNIER = [0]


def _sar_trail_autorise(p, magic_actif):
    """True si le suivi SAR a le droit de toucher cette position.

    Compte au passage ce qu il ecarte, par magic. Sans ce compteur on ne
    sait pas ce que coute la restriction : le 10/08, quatre tickets sur
    cinq n avaient aucune trajectoire de stop et on ignorait lesquels.
    """
    autorises = _SAR_TRAIL_MAGICS if _SAR_TRAIL_MAGICS is not None else {magic_actif}
    if p.magic in autorises:
        return True
    _SAR_TRAIL_IGNORES[p.magic] = _SAR_TRAIL_IGNORES.get(p.magic, 0) + 1
    total = sum(_SAR_TRAIL_IGNORES.values())
    if total - _SAR_TRAIL_DERNIER[0] >= 200:
        _SAR_TRAIL_DERNIER[0] = total
        log.warning("  [SAR-COUVERTURE] positions ecartees, par magic : %s",
                    ", ".join("%s=%d" % (m, n)
                              for m, n in sorted(_SAR_TRAIL_IGNORES.items())))
    return False


def _update_trailing(asset, signal):'''

# (ancre, remplacement) -- chacune doit apparaitre EXACTEMENT une fois
PAIRES = [
    ("        if p.magic != magic:\n            continue",
     "        if not _sar_trail_autorise(p, magic):\n            continue"),

    ('        if signal["direction"] == "BUY" and sar_dir == "BUY" '
     'and sar_val > p.sl and p.sl > 0:',
     '        if p.type == mt5.POSITION_TYPE_BUY and sar_dir == "BUY" '
     'and sar_val > p.sl and p.sl > 0:'),

    ('        elif signal["direction"] == "SELL" and sar_dir == "SELL" '
     'and sar_val < p.sl:',
     '        elif p.type == mt5.POSITION_TYPE_SELL and sar_dir == "SELL" '
     'and sar_val < p.sl and p.sl > 0:'),
]


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

    if MARQUEUR in src:
        print("Patch deja pose dans %s -- rien a faire." % CIBLE)
        return 0

    # Toutes les ancres sont verifiees AVANT la moindre ecriture : on ne
    # veut pas d un fichier a moitie patche.
    ancres = [(ANCRE_BLOC, BLOC)] + PAIRES
    for a, _ in ancres:
        n = src.count(a)
        if n != 1:
            print("KO : %d occurrence(s) de cette ancre, il en faut exactement 1 :"
                  % n)
            print()
            for l in a.split("\n"):
                print("    " + l)
            print()
            print("Le fichier a change depuis la lecture du 10/08. Ne force rien :")
            print("dis-le, on refait l ancre sur la version reelle.")
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
    print()
    print("Deux changements poses :")
    print("  1. le suivi se decide sur p.type, plus sur signal['direction'].")
    print("     Il agira plus souvent -- c est le but. Il ne peut que")
    print("     RESSERRER un stop : le trail SAR est monotone et la garde")
    print("     de patch_sl_garde.py refuse tout recul.")
    print("  2. le filtre de magic est inchange (_SAR_TRAIL_MAGICS = None)")
    print("     mais desormais COMPTE. Elargir est une decision, pas une")
    print("     correction, et elle attend les chiffres.")
    print()
    print("Redemarre price_action.py. Demain :")
    print("    Get-ChildItem -Recurse -Filter *.log | Select-String 'SAR-COUVERTURE'")
    return 0


if __name__ == "__main__":
    sys.exit(main())

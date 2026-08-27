#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_r7_miroirs.py -- R7 cesse de resserrer le stop des miroirs.

CE QUI EST DEJA JUSTE DANS R7
-----------------------------
Contrairement a _move_to_be, _check_auto_breakeven fait tout bien :

    if p.type == 0:                          # BUY
        new_sl = p.price_open + sl_offset_pts
        if p.sl > 0 and new_sl <= p.sl:  continue   # jamais plus lache
        if new_sl >= p.price_current:    continue   # jamais au-dessus du prix
    else:                                    # SELL
        new_sl = p.price_open - sl_offset_pts       <- soustrait bien
        if p.sl > 0 and new_sl >= p.sl:  continue
        if new_sl <= p.price_current:    continue   <- la garde existe

Le "SL only moves UP" de sa documentation n est qu une formulation
centree sur l achat. La garde du cote du prix, celle qui manquait a
_move_to_be, est deja posee lignes 804 et 812. Rien a corriger la.

CE QUI MANQUE
-------------
Sa propre documentation le dit : "Applied to ALL magics except
RANGE_PLAY". Avec l exemption ajoutee le 04/05, cela fait deux familles
ecartees -- RANGE_PLAY (3400-3402) et AUTONOMOUS_MAGICS. Les positions
miroir des papers n y sont pas.

R7 resserre donc leur stop, que miroir_papers.py:763 remet aussitot sur
celui de leur paper parent. C est le cote "resserrement" du va-et-vient
que le terminal enregistre depuis le 25/08 :

    15:28:16.897   31097.15 ->  29494.40      <- R7 et consorts
    15:28:18.975   29494.40 ->  31097.15      <- le miroir
    15:28:21.697   31097.15 ->  29494.40

Et le resserrement n est pas anodin : quand c est lui qui est en place au
moment ou le prix le touche, la position miroir se ferme sur une sortie
que le paper n a jamais demandee, et le resultat de la branche est faux.

Le commentaire du 04/05 dit deja la meme chose d une autre famille :
"M93300/M94300/M95300 had SL moved to ~entry within 3s of entry by this
function, then SL hit at +5s". Troisieme famille, meme lecon.

PREREQUIS
---------
patch_be_watchdog.py doit avoir ete applique : c est lui qui declare
PLAGES_MIROIR au niveau module. Ce patch refuse si la constante manque,
plutot que de la declarer une seconde fois.

USAGE
-----
    python patch_r7_miroirs.py                 <- simulation
    python patch_r7_miroirs.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import time

CIBLE_DEFAUT = "daily_watchdog.py"
MARQUEUR = "[R7-MIROIRS-2708]"

# Comme pour _move_to_be : on delimite la fonction avant de chercher
# l ancre. L exemption AUTONOMOUS_MAGICS existe dans les deux fonctions,
# sous deux formes differentes -- "return p.ticket, True" dans l une,
# "continue" dans l autre -- et confondre les deux serait poser la garde
# au mauvais endroit.
RE_FONCTION = re.compile(
    r"^def _check_auto_breakeven\(.*?(?=^def |^class |\Z)", re.M | re.S)

RE_AUTON = re.compile(
    r"(?P<i>[ \t]*)if p\.magic in AUTONOMOUS_MAGICS:[ \t]*\r?\n"
    r"[ \t]*continue[ \t]*\r?\n")

EXEMPTION = '''{i}# 2026-08-27 : les positions MIROIR des papers.  [R7-MIROIRS-2708]
{i}# R7 s applique a TOUS les magics sauf RANGE_PLAY et AUTONOMOUS. Il
{i}# resserre donc le stop des miroirs -- que miroir_papers.py:763 remet
{i}# aussitot sur celui de leur paper parent. Ce va-et-vient est dans le
{i}# journal du terminal depuis le 25/08, une a trois secondes d ecart, et
{i}# quand c est le stop resserre qui est en place au moment ou le prix le
{i}# touche, la position miroir se ferme sur une sortie que le paper n a
{i}# jamais demandee : le resultat de la branche devient faux.
{i}try:
{i}    if any(a <= int(p.magic) <= b for a, b in PLAGES_MIROIR):
{i}        continue
{i}except Exception:
{i}    pass
'''


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
        print("DEJA POSE : %s est present dans %s." % (MARQUEUR, a.cible))
        return 0
    if "PLAGES_MIROIR" not in src:
        print("REFUS : PLAGES_MIROIR est absente de %s." % a.cible)
        print("        Appliquez d abord patch_be_watchdog.py, qui la declare.")
        print("        Je ne la declare pas une seconde fois : deux")
        print("        definitions de la meme constante finissent toujours")
        print("        par diverger.")
        return 3

    crlf = "\r\n" in src
    def n(s):
        return s.replace("\n", "\r\n") if crlf else s

    f = RE_FONCTION.search(src)
    if f is None:
        print("REFUS : _check_auto_breakeven introuvable au niveau module.")
        return 3
    d0, d1 = f.start(), f.end()
    print("  _check_auto_breakeven : %d octets, du caractere %d au %d."
          % (d1 - d0, d0, d1))

    bloc = src[d0:d1]
    trouves = RE_AUTON.findall(bloc)
    if len(trouves) != 1:
        print("REFUS : l exemption AUTONOMOUS_MAGICS attendue 1 fois dans"
              " _check_auto_breakeven, trouvee %d." % len(trouves))
        return 3

    m = RE_AUTON.search(src, d0, d1)
    neuf = src[:m.end()] + n(EXEMPTION.format(i=m.group("i"))) + src[m.end():]

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

    sauve = "%s.avant_r7_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.cible, sauve)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f2:
        f2.write(neuf)
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f2:
        relu = f2.read()
    nb = relu.count(MARQUEUR)
    ok = nb == 1
    print("")
    print("sauvegarde   : %s" % os.path.basename(sauve))
    print("VERIFICATION : %s (%d marqueur, 1 attendu)"
          % ("ok" if ok else "ECHEC", nb))
    if not ok:
        shutil.copy2(sauve, a.cible)
        print("Le fichier a ete REMIS dans son etat d origine.")
        return 5
    print("")
    print("Effet au prochain lancement de trading_engine.py, comme le")
    print("precedent. Rien ne change dans la seance en cours.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

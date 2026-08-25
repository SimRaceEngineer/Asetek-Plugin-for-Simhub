#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""cale_ticks.py -- dans quelle base copy_ticks_range rend-il ses
                     horodatages, et pour quelle minute ?

  python cale_ticks.py
  python cale_ticks.py --symbole SPX500 --barres 4

LECTEUR SEUL. N ENVOIE AUCUN ORDRE.

LE PROBLEME
    Le 25/08, les ticks demandes pour la minute d une barre revenaient
    horodates 7200 s AVANT elle. Deux lectures sont possibles, et elles
    n ont pas du tout les memes consequences :

      a) c est la BONNE minute, mal horodatee -- il suffit d ignorer
         l horodatage rendu ;
      b) c est une AUTRE minute -- MT5 a interprete la demande dans une
         base et rendu dans une autre, et reconstruire dessus donnerait
         des chiffres coherents et faux.

    On ne tranche pas ca par le raisonnement. On balaie.

LA METHODE
    Pour une barre M1 dont on connait open, high, low et close, on
    demande les ticks de [m + decalage, m + decalage + 60) pour une
    serie de decalages, et on regarde lesquels reproduisent les QUATRE
    prix de la barre. Un seul decalage peut le faire : quatre prix qui
    coincident par hasard, ca n arrive pas.

    On essaie aussi sur le bid, l ask et le mid, parce qu on ne sait pas
    non plus sur quelle base les barres sont construites -- et la
    reponse tombera en meme temps.

    Le resultat est un nombre a mettre dans le lecteur de ticks, mesure
    et non suppose.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

RACINE = os.path.dirname(os.path.abspath(__file__))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None
try:
    import cvd_v13 as base
except Exception:
    base = None

BAR = 60
# de -4 h a +4 h par quart d heure, plus le zero
DECALAGES = [d * 900 for d in range(-16, 17)]


def ohlc(ticks, quoi):
    px = []
    for t in ticks:
        b, a = float(t["bid"]), float(t["ask"])
        p = b if quoi == "bid" else (a if quoi == "ask"
                                     else ((b + a) / 2.0 if a > 0 else b))
        if p > 0:
            px.append(p)
    if len(px) < 2:
        return None
    return px[0], max(px), min(px), px[-1], len(px)


def colle(x, o, h, l, c, tol):
    return (abs(x[0] - o) <= tol and abs(x[1] - h) <= tol
            and abs(x[2] - l) <= tol and abs(x[3] - c) <= tol)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--terminal", default=None)
    ap.add_argument("--symbole", default=None)
    ap.add_argument("--barres", type=int, default=3)
    a = ap.parse_args()

    print("=" * 76)
    print("CALE TICKS -- quel decalage reproduit les quatre prix ?")
    print("=" * 76)
    if mt5 is None or base is None:
        print("MetaTrader5 ou cvd_v13 introuvable.")
        return 2
    if not mt5.initialize(path=a.terminal or base.TERMINAL_DEDIE):
        print("initialize a echoue : %s" % (mt5.last_error(),))
        return 1
    try:
        sym = a.symbole
        if sym is None:
            for cands in base.NOMS.values():
                for c in cands:
                    if mt5.symbol_info(c) is not None:
                        sym = c
                        break
                if sym:
                    break
        if sym is None or mt5.symbol_info(sym) is None:
            print("symbole introuvable.")
            return 1
        mt5.symbol_select(sym, True)
        pas = float(getattr(mt5.symbol_info(sym), "point", 0.01) or 0.01)
        tol = max(pas * 2, 0.05)
        print("  symbole %s, tolerance sur les prix %.4f" % (sym, tol))

        r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 2, a.barres)
        if r is None or len(r) == 0:
            print("aucune barre.")
            return 1

        gagnants = {}
        for row in r:
            m = int(row["time"])
            o, h, l, c = (float(row["open"]), float(row["high"]),
                          float(row["low"]), float(row["close"]))
            print("")
            print("-" * 76)
            print("  barre %s   o %.2f  h %.2f  l %.2f  c %.2f  ticks %d"
                  % (datetime.datetime.utcfromtimestamp(m)
                     .strftime("%Y-%m-%d %H:%M"), o, h, l, c,
                     int(row["tick_volume"])))
            print("-" * 76)
            trouve = False
            for dec in DECALAGES:
                d0 = datetime.datetime.utcfromtimestamp(m + dec)
                d1 = datetime.datetime.utcfromtimestamp(m + dec + BAR)
                try:
                    tk = mt5.copy_ticks_range(sym, d0, d1,
                                              mt5.COPY_TICKS_ALL)
                except Exception:
                    tk = None
                if tk is None or len(tk) == 0:
                    continue
                for quoi in ("bid", "ask", "mid"):
                    x = ohlc(tk, quoi)
                    if x is None:
                        continue
                    if colle(x, o, h, l, c, tol):
                        trouve = True
                        cle = (dec, quoi)
                        gagnants[cle] = gagnants.get(cle, 0) + 1
                        print("     COLLE  decalage %+6d s (%+.2f h)  base %s"
                              "  %d ticks"
                              % (dec, dec / 3600.0, quoi, x[4]))
            if not trouve:
                print("     aucun decalage ne reproduit les quatre prix.")
                # de quoi comprendre : ce que rend le decalage zero
                tk = mt5.copy_ticks_range(
                    sym, datetime.datetime.utcfromtimestamp(m),
                    datetime.datetime.utcfromtimestamp(m + BAR),
                    mt5.COPY_TICKS_ALL)
                if tk is not None and len(tk):
                    x = ohlc(tk, "bid")
                    print("     a decalage 0, le bid donne o %.2f h %.2f"
                          " l %.2f c %.2f sur %d ticks"
                          % (x[0], x[1], x[2], x[3], x[4]) if x else
                          "     a decalage 0, moins de deux ticks lisibles")
                    print("     premier tick horodate %+d s de la barre"
                          % (int(tk[0]["time"]) - m))

        print("")
        print("-" * 76)
        if not gagnants:
            print("  AUCUN decalage ne reproduit les barres.")
            print("  Ne pas reconstruire de bougie au tick sur ce terminal :")
            print("  les deux sources ne se rejoignent pas, et tout chiffre")
            print("  tire d elles serait invente.")
            return 1
        print("  RESULTAT -- decalages qui reproduisent les quatre prix :")
        for (dec, quoi), n in sorted(gagnants.items(), key=lambda x: -x[1]):
            print("     %+6d s (%+.2f h)  base %-4s  sur %d barre(s)"
                  % (dec, dec / 3600.0, quoi, n))
        print("")
        print("  Le decalage retenu doit coller sur TOUTES les barres.")
        print("  S il n en couvre qu une, c est une coincidence, pas une")
        print("  regle.")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())

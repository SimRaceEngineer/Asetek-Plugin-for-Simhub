#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""diag_barres_tick.py -- pourquoi la bougie refaite au tick ne colle pas.

  python diag_barres_tick.py
  python diag_barres_tick.py --symbole US30 --minutes 6

LECTEUR SEUL. N ENVOIE AUCUN ORDRE.

CE QU ON CHERCHE
    Le 25/08, la bougie reconstruite depuis les ticks ne reproduisait
    aucune des 200 barres M1 comparees, et sur certaines le SIGNE du
    delta s inversait -- tick +21,8 contre barre -8,7. Une erreur de
    volume ne change que l amplitude ; un signe qui bascule veut dire
    que l open ou le close ne sont pas les bons.

    Plutot que de corriger sur une hypothese, on affiche les cinq
    champs cote a cote : open, high, low, close, volume. Celui qui
    diverge designe la cause.

LES QUATRE CANDIDATS, ET CE QUI LES DISTINGUE
    borne de fin   si copy_ticks_range inclut le tick de m+60, le close
                   reconstruit est le premier tick de la bougie
                   SUIVANTE. Se voit sur le close seul.
    borne de debut si la barre ouvre sur le dernier prix connu AVANT la
                   minute, l open differe alors que high et low collent.
    base des prix  si les barres ne sont pas bid mais ask ou mid, les
                   QUATRE prix sont decales du meme cote.
    volume         si seul le volume differe, les prix collent et le
                   delta n est faux que d un facteur.

Le script essaie aussi la reconstruction sur l ASK et sur le MID, et
dit laquelle des trois colle le mieux. Il ne conclut pas a votre place :
il montre.
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


def refais(ticks, base_prix, m, fin_exclue):
    """OHLCV depuis les ticks, sur une base de prix donnee."""
    px, n = [], 0
    for t in ticks:
        ts = int(t["time"])
        if ts < m or (fin_exclue and ts >= m + BAR):
            continue
        b, a = float(t["bid"]), float(t["ask"])
        p = {"bid": b, "ask": a, "mid": (b + a) / 2.0 if a > 0 else b}[base_prix]
        if p <= 0:
            continue
        px.append(p)
        n += 1
    if len(px) < 2:
        return None
    return px[0], max(px), min(px), px[-1], float(n)


def ankit(o, h, l, c, v):
    e = h - l
    if e <= 0 or v <= 0:
        return 0.0
    return v * (abs(c - o) / e) * (1.0 if c >= o else -1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--terminal", default=None)
    ap.add_argument("--symbole", default=None)
    ap.add_argument("--minutes", type=int, default=5)
    a = ap.parse_args()

    print("=" * 78)
    print("DIAG BARRES / TICKS -- quel champ ne colle pas")
    print("=" * 78)
    if mt5 is None or base is None:
        print("MetaTrader5 ou cvd_v13 introuvable.")
        return 2
    terminal = a.terminal or base.TERMINAL_DEDIE
    if not mt5.initialize(path=terminal):
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
        print("  symbole : %s" % sym)

        # Les dernieres barres closes, la ou les ticks existent surement.
        r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 1, a.minutes + 2)
        if r is None or len(r) == 0:
            print("aucune barre.")
            return 1

        collent = {"bid": 0, "ask": 0, "mid": 0}
        essais = 0
        for row in r[:a.minutes]:
            m = int(row["time"])
            o, h, l, c = (float(row["open"]), float(row["high"]),
                          float(row["low"]), float(row["close"]))
            vol = float(row["real_volume"]) or float(row["tick_volume"])
            d_barre = ankit(o, h, l, c, vol)
            tk = mt5.copy_ticks_range(
                sym, datetime.datetime.utcfromtimestamp(m),
                datetime.datetime.utcfromtimestamp(m + BAR),
                mt5.COPY_TICKS_ALL)
            print("")
            print("-" * 78)
            print("  %s  %s"
                  % (datetime.datetime.utcfromtimestamp(m)
                     .strftime("%Y-%m-%d %H:%M"), sym))
            print("-" * 78)
            if tk is None or len(tk) == 0:
                print("     aucun tick rendu sur cette minute.")
                continue
            prem, der = int(tk[0]["time"]), int(tk[-1]["time"])
            hors = sum(1 for t in tk if int(t["time"]) >= m + BAR)
            print("     %d ticks, de +%ds a +%ds, dont %d a m+60 ou au-dela"
                  % (len(tk), prem - m, der - m, hors))
            print("     %-6s %10s %10s %10s %10s %8s %10s"
                  % ("", "open", "high", "low", "close", "vol", "delta"))
            print("     %-6s %10.2f %10.2f %10.2f %10.2f %8.0f %+10.2f"
                  % ("BARRE", o, h, l, c, vol, d_barre))
            essais += 1
            for bp in ("bid", "ask", "mid"):
                for fin in (True, False):
                    x = refais(tk, bp, m, fin)
                    if x is None:
                        continue
                    d = ankit(*x)
                    marque = ""
                    if abs(d - d_barre) <= 0.02 * max(1.0, abs(d_barre)):
                        marque = "  <= COLLE"
                        if fin:
                            collent[bp] += 1
                    print("     %-6s %10.2f %10.2f %10.2f %10.2f %8.0f"
                          " %+10.2f%s"
                          % (bp + ("" if fin else "+"), x[0], x[1], x[2],
                             x[3], x[4], d, marque))
            print("     (une ligne 'bid+' inclut les ticks a m+60 et au-dela)")

        print("")
        print("-" * 78)
        print("  sur %d minute(s) : bid %d, ask %d, mid %d collent"
              % (essais, collent["bid"], collent["ask"], collent["mid"]))
        print("  Si aucune ne colle sur les PRIX, la cause n est pas la base")
        print("  de prix : comparer alors open et close ligne a ligne, et le")
        print("  nombre de ticks contre le tick_volume de la barre.")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())

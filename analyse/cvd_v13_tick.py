#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""cvd_v13_tick.py -- la regle telle qu elle se jouerait VRAIMENT :
                       la portion ECOULEE de la bougie en cours.

  python cvd_v13_tick.py --controle
  python cvd_v13_tick.py
  python cvd_v13_tick.py --pas 1

POURQUOI CE TROISIEME CADRAGE
-----------------------------
Le 25/08, la meme regle mesuree de deux facons a donne deux reponses
opposees sur les memes 328 entrees :

    deux bougies CLOSES        -543 EUR   la regle refuse les gagnantes
    bougie ENTIERE de l entree +1021 EUR  mais elle n est pas terminee
                                          quand on decide

La verite vivante est entre les deux. A l instant de l entree,
l indicateur affiche le delta de la bougie EN COURS, calcule sur ce qui
s est ecoule depuis le debut de la minute -- ni rien, ni tout.

C est exactement ce qui avait ete dit d emblee : "on devrait utiliser
le tick pour ce feature car le delta peut varier au sein meme de la
meme bougie M1."

COMMENT ON RECONSTITUE CE QUE L INDICATEUR AFFICHAIT
    Pour chaque entree, on demande a MT5 les ticks de [debut de minute,
    instant de l entree], on en refait un OHLCV partiel, et on lui
    applique la meme decomposition d Ankit :

        delta = signe(close-open) x volume x |close-open| / (high-low)

    Les barres M1 de MT5 sont construites sur le BID : on reconstruit
    donc sur le bid, et non sur le last -- un CFD n a pas de dernier
    prix negocie au sens d un future.

    Le volume suit le choix de l indicateur : volume reel s il existe,
    nombre de ticks sinon.

LE CONTROLE VIENT AVANT LA MESURE
    `--controle` reconstruit la bougie ENTIERE depuis les ticks et
    compare son delta a celui de la barre M1 rendue par copy_rates. Si
    les deux ne coincident pas, la reconstruction est fausse et tout ce
    qui suit le serait aussi. Le script le dit et s arrete plutot que
    de produire des chiffres pleins.

    C est la lecon du 18/08 : la verification avant la mesure, et si la
    verification echoue, le reste n est pas imprime.

L EMA EN COURS
    L indicateur recalcule sa derniere barre a chaque tick :

        ema_en_cours = delta_partiel x k + ema_de_la_barre_precedente
                                            x (1 - k)

    On fait pareil, donc le lisse aussi est celui qui etait affiche.
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
except Exception as _e:                    # noqa
    base = None

BAR = 60
EMA_N = 14


def ankit(o, h, l, c, vol):
    """Le delta d une bougie, forme fermee. Identique a cvd_v13."""
    etendue = h - l
    if etendue <= 0 or vol <= 0:
        return 0.0
    return vol * (abs(c - o) / etendue) * (1.0 if c >= o else -1.0)


def ohlcv(ticks, jusqu_a=None, reel=False):
    """OHLCV d une suite de ticks, sur le BID. None si trop peu.

    Les barres M1 de MT5 sont construites sur le bid : reconstruire sur
    le last donnerait une autre bougie, et un CFD n a de toute facon
    pas de dernier prix negocie au sens d un future."""
    px, vol = [], 0.0
    for t in ticks:
        ts = int(t["time"])
        if jusqu_a is not None and ts > jusqu_a:
            break
        p = float(t["bid"])
        if p <= 0:
            p = float(t["last"])
        if p <= 0:
            continue
        px.append(p)
        if reel:
            # Un tick MT5 est une ligne numpy ; un tick fabrique pour un
            # banc d essai est un dict. On ne suppose ni l un ni l autre.
            v = 0.0
            for champ in ("volume_real", "volume"):
                try:
                    v = float(t[champ])
                except Exception:
                    v = 0.0
                if v > 0:
                    break
            vol += v
    if len(px) < 2:
        return None
    return (px[0], max(px), min(px), px[-1],
            vol if reel and vol > 0 else float(len(px)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--terminal", default=None)
    ap.add_argument("--tickets", default=None)
    ap.add_argument("--pas", type=float, default=1.0)
    ap.add_argument("--controle", action="store_true",
                    help="verifie la reconstruction et s arrete la")
    ap.add_argument("--tolerance", type=float, default=0.02,
                    help="ecart relatif tolere sur le controle")
    a = ap.parse_args()

    print("=" * 74)
    print("CVD V13 AU TICK -- la portion ECOULEE de la bougie en cours")
    print("=" * 74)
    if mt5 is None:
        print("MetaTrader5 introuvable dans cet interpreteur.")
        return 2
    if base is None:
        print("REFUS : cvd_v13.py doit etre a cote. Il porte la lecture des")
        print("tickets, la decomposition et le cadrage -- on ne les recopie")
        print("pas ici.")
        return 1

    terminal = a.terminal or base.TERMINAL_DEDIE
    tickets, diag = base.lit_tickets(a.tickets or base.TICKETS)
    if tickets is None:
        print("REFUS : %s" % diag["erreur"])
        return 1
    print("  entrees retenues %d" % diag["retenus"])
    if not tickets:
        return 1

    if not mt5.initialize(path=terminal):
        print("initialize a echoue : %s" % (mt5.last_error(),))
        return 1
    try:
        sym = {}
        for actif, cands in base.NOMS.items():
            for c in cands:
                try:
                    if mt5.symbol_info(c) is not None:
                        mt5.symbol_select(c, True)
                        sym[actif] = c
                        break
                except Exception:
                    continue
        print("  symboles : %s"
              % ", ".join("%s->%s" % (k, v) for k, v in sorted(sym.items())))
        if not sym:
            print("REFUS : aucun symbole reconnu.")
            return 1

        dec, ref = base.decalage_serveur(list(sym.values()))
        if dec is None:
            print("REFUS : heure du serveur illisible.")
            return 1
        arrondi = int(round(dec / 60.0)) * 60
        print("  decalage serveur : %+d s, lu sur %s" % (arrondi, ref))

        t0 = min(t["t"] for t in tickets) + arrondi - 3 * 86400
        t1 = max(t["t"] for t in tickets) + arrondi + 86400
        series, reel = {}, {}
        for actif, s in sorted(sym.items()):
            r = mt5.copy_rates_range(s, mt5.TIMEFRAME_M1,
                                     datetime.datetime.utcfromtimestamp(t0),
                                     datetime.datetime.utcfromtimestamp(t1))
            if r is None or len(r) == 0:
                continue
            series[actif] = base.delta_bougies(r)
            reel[actif] = any(float(x["real_volume"]) > 0 for x in r[-50:])
            print("  %-6s %-8s %5d barres M1, volume reel %s"
                  % (actif, s, len(r), "oui" if reel[actif] else "non"))

        # ------------------------------------------------ le controle
        print("")
        print("-" * 74)
        print("CONTROLE -- la bougie ENTIERE refaite au tick contre la")
        print("barre M1 de MT5. Si ca ne colle pas, rien d autre ne vaut.")
        print("-" * 74)
        colle = ecart = vide = 0
        pires = []
        for t in tickets[:200]:
            s = sym.get(t["actif"])
            if not s or t["actif"] not in series:
                continue
            m = ((t["t"] + arrondi) // BAR) * BAR
            tk = mt5.copy_ticks_range(
                s, datetime.datetime.utcfromtimestamp(m),
                datetime.datetime.utcfromtimestamp(m + BAR),
                mt5.COPY_TICKS_ALL)
            att = series[t["actif"]].get(m)
            if tk is None or len(tk) == 0 or att is None:
                vide += 1
                continue
            o = ohlcv(tk, None, reel.get(t["actif"], False))
            if o is None:
                vide += 1
                continue
            mien = ankit(*o)
            ref_v = att[0]
            d = abs(mien - ref_v) / (abs(ref_v) if abs(ref_v) > 1e-9 else 1.0)
            if d <= a.tolerance:
                colle += 1
            else:
                ecart += 1
                if len(pires) < 5:
                    pires.append((t["ts"], t["actif"], mien, ref_v))
        n = colle + ecart
        print("  %d bougie(s) comparee(s), %d sans ticks" % (n, vide))
        if n:
            print("  %d collent a %.0f %% pres  (%.0f %%)"
                  % (colle, 100 * a.tolerance, 100.0 * colle / n))
            for ts, act, mien, ref_v in pires:
                print("     ecart %s %-6s tick %+9.1f  barre %+9.1f"
                      % (ts, act, mien, ref_v))
        if n == 0 or colle < 0.8 * n:
            print("")
            print("REFUS : la reconstruction ne reproduit pas les barres de")
            print("MT5. Mesurer la regle dessus donnerait des chiffres")
            print("pleins et faux. Je m arrete ici.")
            print("Pistes : le bid n est pas la base des barres, ou le")
            print("volume ne se compte pas comme je le fais.")
            return 1
        print("  La reconstruction tient. On peut mesurer.")
        if a.controle:
            print("")
            print("--controle : rien n a ete conclu au-dela.")
            return 0

        # ------------------------------------------------- la mesure
        k = 2.0 / (EMA_N + 1.0)
        brut = (base.tas(), base.tas())
        lisse = (base.tas(), base.tas())
        par_magic, sans, ecoulees = {}, base.tas(), []

        for t in tickets:
            s = sym.get(t["actif"])
            serie = series.get(t["actif"])
            if not s or not serie:
                base.ajoute(sans, t["pnl"])
                continue
            ts_serveur = t["t"] + arrondi
            m = (ts_serveur // BAR) * BAR
            prec = serie.get(m - BAR)
            if prec is None:
                base.ajoute(sans, t["pnl"])
                continue
            tk = mt5.copy_ticks_range(
                s, datetime.datetime.utcfromtimestamp(m),
                datetime.datetime.utcfromtimestamp(ts_serveur + 1),
                mt5.COPY_TICKS_ALL)
            if tk is None or len(tk) == 0:
                base.ajoute(sans, t["pnl"])
                continue
            o = ohlcv(tk, ts_serveur, reel.get(t["actif"], False))
            if o is None:
                base.ajoute(sans, t["pnl"])
                continue
            d_partiel = ankit(*o)
            ema_courant = d_partiel * k + prec[1] * (1.0 - k)
            ecoulees.append(ts_serveur - m)

            ok = base.passe(d_partiel, prec[0], t["sens"], a.pas)
            okl = base.passe(ema_courant, prec[1], t["sens"], a.pas)
            if ok is None:
                base.ajoute(sans, t["pnl"])
                continue
            base.ajoute(brut[0 if ok else 1], t["pnl"])
            base.ajoute(lisse[0 if okl else 1], t["pnl"])
            e = par_magic.setdefault(t["magic"],
                                     {"p": base.tas(), "r": base.tas()})
            base.ajoute(e["p" if ok else "r"], t["pnl"])

        base.verdict("PORTION ECOULEE contre bougie close -- delta BRUT",
                     *brut,
                     note="Le delta que l indicateur AFFICHAIT a la seconde"
                          " de l entree.")
        base.verdict("PORTION ECOULEE contre bougie close -- LISSE EMA%d"
                     % EMA_N, *lisse)

        if ecoulees:
            q = [0, 0, 0, 0]
            for x in ecoulees:
                q[min(3, int(x) // 15)] += 1
            print("")
            print("  secondes ecoulees dans la minute a l entree :")
            print("     " + "   ".join(
                "%02d-%02ds %3d (%2.0f%%)"
                % (i * 15, i * 15 + 14, c, 100.0 * c / len(ecoulees))
                for i, c in enumerate(q)))
            print("  Une entree tres tot dans la minute a peu de ticks")
            print("  derriere elle : son delta partiel est bruite, et c est")
            print("  une vraie limite de la regle, pas un defaut de mesure.")

        if par_magic:
            print("")
            print("-" * 74)
            print("PAR MAGIC -- portion ecoulee, delta brut")
            print("-" * 74)
            print("  %-8s %6s %11s %8s %6s %11s %8s"
                  % ("MAGIC", "pris", "PnL", "/trade", "refus", "PnL",
                     "/trade"))
            for mg in sorted(par_magic):
                p, r = par_magic[mg]["p"], par_magic[mg]["r"]
                print("  %-8d %6d %+11.2f %+8.2f %6d %+11.2f %+8.2f"
                      % (mg, p["n"], p["pnl"],
                         p["pnl"] / p["n"] if p["n"] else 0.0,
                         r["n"], r["pnl"],
                         r["pnl"] / r["n"] if r["n"] else 0.0))

        if sans["n"]:
            print("")
            print("  NON MESUREES : %d, PnL %+.2f -- pas de ticks ou pas de"
                  " bougie precedente. Ni prises ni refusees."
                  % (sans["n"], sans["pnl"]))
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())

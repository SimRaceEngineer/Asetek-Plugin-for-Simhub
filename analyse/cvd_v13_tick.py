#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""cvd_v13_tick.py -- la regle telle qu elle se jouerait VRAIMENT :
                       la portion ECOULEE de la bougie en cours.

  python cvd_v13_tick.py --controle
  python cvd_v13_tick.py
  python cvd_v13_tick.py --balayage 0,1,2,5,10

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

LE BALAYAGE, ET POURQUOI IL EST DANS LE SCRIPT
    Les ticks ne sont relus QU UNE FOIS : on garde les grandeurs brutes
    et le seuil ne s applique qu ensuite. Balayer dix pas ne coute alors
    rien de plus que d en mesurer un. Fait depuis le terminal, le meme
    balayage rouvrait MT5 et relisait tout a chaque pas.

L ARTEFACT D HORLOGE, SEPARE
    La repartition des secondes ecoulees est donnee separement pour les
    autorisees et pour les refusees. Une bougie en cours a plus de temps
    pour depasser la precedente a la 55e seconde qu a la 5e : si les
    autorisees se tassaient en fin de minute, la regle mesurerait
    l horloge et non le flux. Deux repartitions semblables ecartent le
    soupcon ; deux repartitions differentes le confirment.

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

# copy_ticks_range et copy_rates ne rendent pas leurs horodatages dans
# la meme base : le 25/08, les ticks d une barre revenaient 7200 s avant
# elle. Ce nombre depend du courtier ET de l heure d ete ; on le
# RECALIBRE au demarrage au lieu de le figer. Balayage de -4 h a +4 h.
DECALAGES = [d * 900 for d in range(-16, 17)]


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


def cale_decalage(sym, minimum=2):
    """Le decalage qui fait coincider ticks et barres, MESURE.

    Pour trois barres recentes dont on connait open, high, low et close,
    on demande les ticks de [m+decalage, +60) et on garde le decalage
    qui reproduit les QUATRE prix. Quatre prix qui coincident par
    hasard, ca n arrive pas -- et on exige qu il tienne sur au moins
    deux barres, sinon c est une coincidence et pas une regle.
    """
    info = mt5.symbol_info(sym)
    tol = max(float(getattr(info, "point", 0.01) or 0.01) * 2, 0.05)
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 2, 3)
    if r is None or len(r) == 0:
        return None, "aucune barre recente"
    compte = {}
    for row in r:
        m = int(row["time"])
        o, h, l, c = (float(row["open"]), float(row["high"]),
                      float(row["low"]), float(row["close"]))
        for dec in DECALAGES:
            try:
                tk = mt5.copy_ticks_range(
                    sym, datetime.datetime.utcfromtimestamp(m + dec),
                    datetime.datetime.utcfromtimestamp(m + dec + BAR),
                    mt5.COPY_TICKS_ALL)
            except Exception:
                tk = None
            if tk is None or len(tk) < 2:
                continue
            x = ohlcv(tk, None, False)
            if x is None:
                continue
            if (abs(x[0] - o) <= tol and abs(x[1] - h) <= tol
                    and abs(x[2] - l) <= tol and abs(x[3] - c) <= tol):
                compte[dec] = compte.get(dec, 0) + 1
    if not compte:
        return None, "aucun decalage ne reproduit les barres"
    dec, n = max(compte.items(), key=lambda kv: kv[1])
    if n < minimum:
        return None, ("le meilleur decalage (%+d s) ne tient que sur %d"
                      " barre(s)" % (dec, n))
    return dec, "%+d s, verifie sur %d barre(s) sur %d" % (dec, n, len(r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--terminal", default=None)
    ap.add_argument("--tickets", default=None)
    ap.add_argument("--pas", type=float, default=1.0)
    ap.add_argument("--balayage", default=None,
                    help="pas a essayer, separes par des virgules : "
                         "0,1,2,5,10. Les ticks ne sont relus qu une fois.")
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

        dtick, pourquoi = cale_decalage(sorted(sym.values())[0])
        if dtick is None:
            print("")
            print("REFUS : %s." % pourquoi)
            print("Les ticks et les barres ne se rejoignent pas sur ce")
            print("terminal. Toute bougie reconstruite serait inventee.")
            return 1
        print("  decalage ticks/barres : %s" % pourquoi)

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
                s, datetime.datetime.utcfromtimestamp(m + dtick),
                datetime.datetime.utcfromtimestamp(m + dtick + BAR),
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
        # On RELIT LES TICKS UNE SEULE FOIS et on garde les grandeurs
        # brutes. Le seuil ne s applique qu ensuite : balayer dix pas ne
        # coute alors rien de plus que d en mesurer un.
        k = 2.0 / (EMA_N + 1.0)
        mesures, sans = [], base.tas()

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
                s, datetime.datetime.utcfromtimestamp(m + dtick),
                datetime.datetime.utcfromtimestamp(ts_serveur + 1 + dtick),
                mt5.COPY_TICKS_ALL)
            if tk is None or len(tk) == 0:
                base.ajoute(sans, t["pnl"])
                continue
            o = ohlcv(tk, ts_serveur, reel.get(t["actif"], False))
            if o is None:
                base.ajoute(sans, t["pnl"])
                continue
            if t["sens"] not in ("BUY", "SELL"):
                base.ajoute(sans, t["pnl"])
                continue
            d_partiel = ankit(*o)
            mesures.append({"d": d_partiel, "dp": prec[0],
                            "e": d_partiel * k + prec[1] * (1.0 - k),
                            "ep": prec[1], "sens": t["sens"],
                            "pnl": t["pnl"], "magic": t["magic"],
                            "s": ts_serveur - m})

        if not mesures:
            print("")
            print("Aucune entree mesurable.")
            return 1

        pas_liste = [a.pas]
        if a.balayage:
            try:
                pas_liste = [float(x) for x in a.balayage.split(",")]
            except ValueError:
                print("--balayage : liste de nombres separes par des"
                      " virgules.")
                return 1

        for pas in pas_liste:
            b = (base.tas(), base.tas())
            li = (base.tas(), base.tas())
            for x in mesures:
                ok = base.passe(x["d"], x["dp"], x["sens"], pas)
                okl = base.passe(x["e"], x["ep"], x["sens"], pas)
                base.ajoute(b[0 if ok else 1], x["pnl"])
                base.ajoute(li[0 if okl else 1], x["pnl"])
            base.verdict("PAS %.1f -- PORTION ECOULEE, delta BRUT" % pas, *b,
                         note="Le delta que l indicateur AFFICHAIT a la"
                              " seconde de l entree.")
            base.verdict("PAS %.1f -- PORTION ECOULEE, LISSE EMA%d"
                         % (pas, EMA_N), *li)

        # -- l artefact d horloge, separe pris / refuses
        qp, qr = [0, 0, 0, 0], [0, 0, 0, 0]
        for x in mesures:
            ok = base.passe(x["d"], x["dp"], x["sens"], a.pas)
            (qp if ok else qr)[min(3, int(x["s"]) // 15)] += 1
        print("")
        print("-" * 74)
        print("L ARTEFACT D HORLOGE -- au pas %.1f, delta brut" % a.pas)
        print("-" * 74)
        for nom, q in (("autorisees", qp), ("refusees", qr)):
            n = float(sum(q)) or 1.0
            print("  %-11s %s" % (nom, "   ".join(
                "%02d-%02ds %3d (%2.0f%%)"
                % (i * 15, i * 15 + 14, c, 100.0 * c / n)
                for i, c in enumerate(q))))
        # -- LA QUESTION QUI PRIME : le flux, ou juste l horloge ?
        # Les refusees sont massivement en debut de minute. Si les
        # entrees precoces perdaient et les tardives gagnaient, une
        # simple regle d horloge -- ne pas entrer avant la 30e seconde
        # -- capterait l essentiel du gain, et le CVD n ajouterait rien.
        # On compare donc les deux filtres SUR LES MEMES entrees.
        print("")
        print("-" * 74)
        print("LE FLUX, OU JUSTE L HORLOGE ?")
        print("-" * 74)
        qn = [base.tas() for _ in range(4)]
        for x in mesures:
            base.ajoute(qn[min(3, int(x["s"]) // 15)], x["pnl"])
        print("  PnL par quart de minute, TOUTES entrees, sans aucun filtre :")
        for i, t in enumerate(qn):
            print("     %02d-%02ds  n %3d   PnL %+9.2f   %+6.2f / trade"
                  % (i * 15, i * 15 + 14, t["n"], t["pnl"],
                     t["pnl"] / t["n"] if t["n"] else 0.0))
        for seuil in (15, 30, 45):
            hp, hr = base.tas(), base.tas()
            for x in mesures:
                base.ajoute(hp if x["s"] >= seuil else hr, x["pnl"])
            print("")
            print("  HORLOGE SEULE, entrer a partir de la %de seconde :"
                  % seuil)
            print("     gardees %3d  PnL %+9.2f  %+6.2f/tr    refusees %3d"
                  "  PnL %+9.2f" % (hp["n"], hp["pnl"],
                                    hp["pnl"] / hp["n"] if hp["n"] else 0.0,
                                    hr["n"], hr["pnl"]))
            print("     la regle d horloge rapporterait %+.2f" % (-hr["pnl"]))
        print("")
        print("  Si l horloge seule rapporte autant que le CVD, le CVD")
        print("  n apporte rien qu une montre ne donne. Si elle rapporte")
        print("  nettement moins, le flux porte quelque chose que le temps")
        print("  ecoule n explique pas.")

        print("")
        print("  Si les autorisees se tassaient dans le dernier quart, la")
        print("  regle mesurerait l horloge : une bougie en cours a plus de")
        print("  temps pour depasser la precedente a la 55e seconde qu a la")
        print("  5e. Deux repartitions semblables ecartent ce soupcon.")

        par_magic = {}
        for x in mesures:
            ok = base.passe(x["d"], x["dp"], x["sens"], a.pas)
            e = par_magic.setdefault(x["magic"],
                                     {"p": base.tas(), "r": base.tas()})
            base.ajoute(e["p" if ok else "r"], x["pnl"])
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

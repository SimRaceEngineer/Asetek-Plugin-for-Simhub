#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""cvd_multitf.py -- la regle d expansion du CVD, en M1, M3, M5 et M15.

  python cvd_multitf.py                      les quatre unites, pas 1
  python cvd_multitf.py --pas 0,1,2,5,10     balayage du pas
  python cvd_multitf.py --sans-ticks         rapide, cadrage CLOSES seul

LA REGLE, LA MEME A TOUTES LES ECHELLES
---------------------------------------
Si le delta de la bougie precedente vaut -38, on ne vend que si le
delta courant descend sous -39. Si elle vaut +24, on n achete que si
le courant depasse +25. On ne joue pas le niveau du flux, on joue son
EXPANSION -- c est ce qui distingue un mouvement qui s installe d un
mouvement qui s essouffle.

La question posee ici : cette regle vaut-elle mieux en M15 qu en M1 ?
Une bougie longue lisse le bruit mais decide tard ; une bougie courte
decide tot mais sur presque rien.

TROIS CADRAGES, ET UN SEUL EST HONNETE
--------------------------------------
    CLOSES     delta(n-1) contre delta(n-2), decide a l ouverture de
               la bougie n. Strictement causal : ces deux bougies sont
               fermees, leurs chiffres existent. Mais la decision est
               prise avant que la bougie en cours n ait rien montre.

    ECOULEE    delta de la PORTION ECOULEE de la bougie en cours,
               reconstruite depuis les ticks jusqu a l instant exact de
               l entree, contre delta(n-1). Causal ET realiste : c est
               ce que le miroir voit en live. C EST LE SEUL CHIFFRE A
               RETENIR.

    COMPLETE   delta de la bougie d entree ENTIERE contre delta(n-1).
               NON CAUSAL : au moment d entrer, la bougie n est pas
               finie. Ce cadrage regarde l avenir. Il n est affiche que
               comme BORNE HAUTE -- ce que la regle rendrait si on
               savait deja comment la bougie va se terminer.

    L ecart entre COMPLETE et ECOULEE mesure exactement ce que la
    connaissance de l avenir apporterait. Quand il est enorme, une
    regle qui semble excellente ne l est que sur le papier.

CE QUE LE SCRIPT NE FAIT PAS
    Il ne rejoue pas les sorties. Chaque entree garde le PnL qu elle a
    reellement fait ; la regle ne fait que la retenir ou l ecarter.
    C est exactement le mecanisme de la branche 5, qui filtre l entree
    et laisse la sortie tranquille.

LE PIEGE DU BALAYAGE
    Quatre unites x trois cadrages x N pas, c est beaucoup de
    combinaisons. La meilleure sortira toujours bonne : c est la
    definition d un maximum. Le script compte les combinaisons
    essayees et le rappelle en fin de rapport. Une case qui brille
    parmi cinquante n est pas un resultat, c est un tirage.

SOURCE
    docs\rails_trades\tickets_rails.jsonl, magics 220000-249999, PM.
    Les prix viennent de MT5 : barres pour les bougies fermees, ticks
    pour la portion ecoulee.
"""

from __future__ import annotations

import argparse
import calendar
import datetime
import io
import json
import os
import sys

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

TICKETS = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
PM = (14, 19)
MAGIC_BAS, MAGIC_HAUT = 220000, 249999

NOMS = {
    "US30":  ("US30", "US30.cash", "us30", "DOW", "DJ30"),
    "US500": ("US500", "SPX500", "spx500", "US500.cash", "SPX500.cash"),
    "US100": ("US100", "NAS100", "nas100", "US100.cash", "NAS100.cash"),
}

# minutes -> constante MT5. On garde les minutes : elles servent aussi
# a calculer le debut de la bougie qui contient un instant.
UNITES = (("M1", 1), ("M3", 3), ("M5", 5), ("M15", 15))

DECALAGES = [d * 900 for d in range(-16, 17)]


# ----------------------------------------------------------------------
def epoch_local(ts):
    try:
        d = datetime.datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    return calendar.timegm(d.timetuple())


def maintenant_machine():
    return calendar.timegm(datetime.datetime.now().timetuple())


def decalage_serveur(symboles):
    for s in symboles:
        try:
            tk = mt5.symbol_info_tick(s)
        except Exception:
            tk = None
        t = int(getattr(tk, "time", 0) or 0) if tk is not None else 0
        if t > 0:
            return t - maintenant_machine(), s
    return None, None


def ankit(o, h, l, c, vol):
    """Le delta d une bougie, decomposition d Ankit. Identique a
    l indicateur V13 et a cvd_v13.py -- une seule definition, sinon
    deux mesures qui divergent en silence."""
    etendue = h - l
    if etendue <= 0 or vol <= 0:
        return 0.0
    return vol * (abs(c - o) / etendue) * (1.0 if c >= o else -1.0)


def deltas(rates):
    """{debut_bougie: delta brut}. On garde le BRUT et non l EMA14 :
    la mesure du 25/08 a montre que le lissage detruit la regle (de
    +458 a -232). Lisser une expansion, c est l effacer."""
    out = {}
    for r in rates:
        vol = (float(r["real_volume"]) if float(r["real_volume"]) > 0
               else float(r["tick_volume"]))
        out[int(r["time"])] = ankit(float(r["open"]), float(r["high"]),
                                    float(r["low"]), float(r["close"]), vol)
    return out


def ohlcv(ticks, jusqu_a=None):
    """OHLCV d une suite de ticks, sur le BID -- comme MT5 construit ses
    barres. None si moins de deux ticks."""
    px, vol = [], 0.0
    for t in ticks:
        if jusqu_a is not None and int(t["time"]) > jusqu_a:
            break
        p = float(t["bid"])
        if p <= 0:
            p = float(t["last"])
        if p <= 0:
            continue
        px.append(p)
        for champ in ("volume_real", "volume"):
            try:
                v = float(t[champ])
            except Exception:
                v = 0.0
            if v > 0:
                vol += v
                break
    if len(px) < 2:
        return None
    return (px[0], max(px), min(px), px[-1],
            vol if vol > 0 else float(len(px)))


def cale_decalage(sym, minimum=2):
    """Le decalage qui fait coincider ticks et barres, MESURE et non
    suppose. Le 25/08 il valait -7200 s, et il depend du courtier comme
    de l heure d ete."""
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
                    datetime.datetime.utcfromtimestamp(m + dec + 60),
                    mt5.COPY_TICKS_ALL)
            except Exception:
                tk = None
            if tk is None or len(tk) < 2:
                continue
            x = ohlcv(tk)
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


# ----------------------------------------------------------------------
def lit_tickets(chemin):
    out, diag = [], {"hors_plage": 0, "hors_pm": 0, "sans_pnl": 0}
    if not os.path.isfile(chemin):
        return None, {"erreur": "introuvable : %s" % chemin}
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        b = ligne.strip()
        if not b.startswith("{"):
            continue
        try:
            o = json.loads(b)
        except ValueError:
            continue
        ts = o.get("entry_ts")
        if not isinstance(ts, str) or len(ts) < 19:
            continue
        try:
            magic = int(o.get("magic") or 0)
        except (TypeError, ValueError):
            magic = 0
        if not (MAGIC_BAS <= magic <= MAGIC_HAUT):
            diag["hors_plage"] += 1
            continue
        try:
            heure = int(ts[11:13])
        except ValueError:
            continue
        if not (PM[0] <= heure < PM[1]):
            diag["hors_pm"] += 1
            continue
        if o.get("pnl_eur") is None:
            diag["sans_pnl"] += 1
            continue
        e = epoch_local(ts)
        if e is None:
            continue
        out.append({"t": e, "ts": ts, "magic": magic,
                    "sens": (o.get("dir") or "").upper(),
                    "actif": (o.get("asset") or "").upper(),
                    "pnl": float(o["pnl_eur"])})
    diag["retenus"] = len(out)
    return out, diag


def passe(courant, precedent, sens, pas):
    """courant doit DEPASSER precedent dans le sens du trade."""
    if sens == "SELL":
        return courant <= precedent - pas
    if sens == "BUY":
        return courant >= precedent + pas
    return None


def tas():
    return {"n": 0, "pnl": 0.0}


def ajoute(d, pnl):
    d["n"] += 1
    d["pnl"] += pnl


def verdict(pris, ref):
    tot = pris["n"] + ref["n"]
    if tot == 0:
        return "        aucune entree jugee."
    def tr(x):
        return x["pnl"] / x["n"] if x["n"] else 0.0
    return ("        AUTORISEES %4d (%2.0f %%) PnL %+9.2f (%+6.2f/tr)\n"
            "        REFUSEES   %4d (%2.0f %%) PnL %+9.2f (%+6.2f/tr)\n"
            "        la regle rapporte %+.2f"
            % (pris["n"], 100.0 * pris["n"] / tot, pris["pnl"], tr(pris),
               ref["n"], 100.0 * ref["n"] / tot, ref["pnl"], tr(ref),
               -ref["pnl"]))


# ----------------------------------------------------------------------
def const_tf(minutes):
    return {1: mt5.TIMEFRAME_M1, 3: mt5.TIMEFRAME_M3,
            5: mt5.TIMEFRAME_M5, 15: mt5.TIMEFRAME_M15}[minutes]


def debut_bougie(t, minutes):
    p = minutes * 60
    return (t // p) * p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickets", default=TICKETS)
    ap.add_argument("--pas", default="1",
                    help="un ou plusieurs pas separes par des virgules")
    ap.add_argument("--sans-ticks", action="store_true",
                    help="cadrage CLOSES seul : pas d appel aux ticks")
    a = ap.parse_args()

    pas_liste = []
    for x in str(a.pas).split(","):
        x = x.strip()
        if x:
            try:
                pas_liste.append(float(x))
            except ValueError:
                pass
    if not pas_liste:
        pas_liste = [1.0]

    print("=" * 74)
    print("cvd_multitf -- la regle d expansion en M1, M3, M5 et M15")
    print("=" * 74)

    if mt5 is None:
        print("MetaTrader5 n est pas importable ici.")
        return 2

    tickets, diag = lit_tickets(a.tickets)
    if tickets is None:
        print(diag.get("erreur"))
        return 2
    if not tickets:
        print("aucune entree retenue : %s" % diag)
        return 1
    print("  entrees retenues : %d  (hors magics %d, hors PM %d, sans PnL %d)"
          % (diag["retenus"], diag["hors_plage"], diag["hors_pm"],
             diag["sans_pnl"]))

    if not mt5.initialize():
        print("initialize a echoue : %s" % (mt5.last_error(),))
        return 2

    # ------------------------------------------------ les symboles
    sym = {}
    for actif, cands in NOMS.items():
        for c in cands:
            if mt5.symbol_info(c) is not None:
                sym[actif] = c
                break
    manquants = [k for k in NOMS if k not in sym]
    if manquants:
        print("  symboles introuvables : %s" % ", ".join(manquants))
    print("  symboles : %s"
          % ", ".join("%s -> %s" % (k, v) for k, v in sorted(sym.items())))

    dec, ref = decalage_serveur(list(sym.values()))
    if dec is None:
        print("  decalage serveur ILLISIBLE -- on s arrete plutot que de")
        print("  comparer deux horloges differentes.")
        mt5.shutdown()
        return 1
    print("  decalage serveur - machine : %+d s (%+.2f h), lu sur %s"
          % (dec, dec / 3600.0, ref))

    for t in tickets:
        t["ts_srv"] = t["t"] + dec

    # ------------------------------------------- les barres, par unite
    t0 = min(t["ts_srv"] for t in tickets)
    t1 = max(t["ts_srv"] for t in tickets)
    D = {}
    for nom, mn in UNITES:
        for actif, s in sorted(sym.items()):
            r = mt5.copy_rates_range(
                s, const_tf(mn),
                datetime.datetime.utcfromtimestamp(t0 - mn * 60 * 5),
                datetime.datetime.utcfromtimestamp(t1 + mn * 60 * 2))
            D[(nom, actif)] = deltas(r) if r is not None else {}
        print("  %-4s %s"
              % (nom, "  ".join("%s %d bougies" % (k, len(D[(nom, k)]))
                                for k in sorted(sym))))

    # ------------------------------------------------------ les ticks
    ecoulee = {}
    if not a.sans_ticks:
        print("")
        print("  CALAGE DES TICKS SUR LES BARRES")
        dtick = {}
        for actif, s in sorted(sym.items()):
            d, note = cale_decalage(s)
            dtick[actif] = d
            print("     %-6s %s" % (actif, note if d is not None
                                    else "ECHEC : %s" % note))
        if any(v is None for v in dtick.values()):
            print("     Au moins un actif n est pas cale : le cadrage")
            print("     ECOULEE serait faux. On ne l affichera pas.")
            a.sans_ticks = True

        if not a.sans_ticks:
            print("")
            print("  RECONSTRUCTION DE LA PORTION ECOULEE  (%d entrees)"
                  % len(tickets))
            faits = rates = 0
            for t in tickets:
                s = sym.get(t["actif"])
                if s is None:
                    continue
                dt = dtick[t["actif"]]
                d15 = debut_bougie(t["ts_srv"], 15)
                try:
                    tk = mt5.copy_ticks_range(
                        s, datetime.datetime.utcfromtimestamp(d15 + dt),
                        datetime.datetime.utcfromtimestamp(
                            t["ts_srv"] + 1 + dt),
                        mt5.COPY_TICKS_ALL)
                except Exception:
                    tk = None
                if tk is None or len(tk) < 2:
                    rates += 1
                    continue
                faits += 1
                for nom, mn in UNITES:
                    deb = debut_bougie(t["ts_srv"], mn)
                    sous = [x for x in tk if int(x["time"]) >= deb + dt]
                    x = ohlcv(sous, t["ts_srv"] + dt)
                    if x is None:
                        continue
                    ecoulee[(t["ts"], t["actif"], nom)] = ankit(*x)
            print("     reconstruites %d, sans ticks %d" % (faits, rates))

    # ------------------------------------------------------- mesure
    combinaisons = 0
    resume = []
    for pas in pas_liste:
        for nom, mn in UNITES:
            cadres = [("CLOSES  (causal, decide a l ouverture)", "closes")]
            if not a.sans_ticks:
                cadres.append(("ECOULEE (causal, ce que le miroir voit)",
                               "ecoulee"))
            cadres.append(("COMPLETE (NON CAUSAL -- borne haute)", "complete"))

            print("")
            print("=" * 74)
            print("  %s   pas = %g" % (nom, pas))
            print("=" * 74)
            for titre, quoi in cadres:
                pris, ref, sans = tas(), tas(), 0
                for t in tickets:
                    dd = D.get((nom, t["actif"]))
                    if not dd:
                        sans += 1
                        continue
                    deb = debut_bougie(t["ts_srv"], mn)
                    prec = dd.get(deb - mn * 60)
                    if quoi == "closes":
                        cour = prec
                        prec = dd.get(deb - 2 * mn * 60)
                    elif quoi == "complete":
                        cour = dd.get(deb)
                    else:
                        cour = ecoulee.get((t["ts"], t["actif"], nom))
                    if cour is None or prec is None:
                        sans += 1
                        continue
                    ok = passe(cour, prec, t["sens"], pas)
                    if ok is None:
                        sans += 1
                        continue
                    ajoute(pris if ok else ref, t["pnl"])
                combinaisons += 1
                print("")
                print("     %s" % titre)
                if sans:
                    print("        %d entree(s) sans donnee, ecartees" % sans)
                print(verdict(pris, ref))
                resume.append((pas, nom, quoi, -ref["pnl"], pris["n"],
                               pris["n"] + ref["n"]))

    # ------------------------------------------------------- resume
    print("")
    print("=" * 74)
    print("RESUME -- ce que la regle rapporte")
    print("=" * 74)
    print("  %-6s %-4s %-9s %10s %8s %8s"
          % ("pas", "TF", "cadrage", "rapporte", "prises", "jugees"))
    print("  " + "-" * 50)
    for pas, nom, quoi, gain, np_, tot in resume:
        print("  %-6g %-4s %-9s %+10.2f %8d %8d"
              % (pas, nom, quoi, gain, np_, tot))

    if not a.sans_ticks:
        print("")
        print("  LIRE LA COLONNE 'ecoulee' ET ELLE SEULE pour decider.")
        print("  'closes' decide avant que la bougie en cours n ait rien")
        print("  montre ; 'complete' regarde l avenir et n est la que")
        print("  comme borne haute. L ecart entre 'complete' et 'ecoulee'")
        print("  mesure ce que la connaissance de l avenir apporterait.")
    print("")
    print("  %d COMBINAISONS ESSAYEES. La meilleure sortira toujours" % combinaisons)
    print("  bonne : c est la definition d un maximum. Une case qui")
    print("  brille parmi %d n est pas un resultat, c est un tirage." % combinaisons)
    print("  Ce qui compte : un cadrage qui tient sur PLUSIEURS unites")
    print("  de temps et PLUSIEURS pas a la fois.")

    mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())

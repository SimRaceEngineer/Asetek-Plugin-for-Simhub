#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""cvd_v13.py -- le V13 reproduit en Python, et la regle du delta
                  croissant mesuree sur les entrees reellement prises.

  python cvd_v13.py --sonde
  python cvd_v13.py
  python cvd_v13.py --pas 1 --lisse

LE V13 N EST PAS TICK PAR TICK -- ET C EST UNE BONNE NOUVELLE
-------------------------------------------------------------
V13_CVD.mq5 travaille sur les BOUGIES, pas sur les ticks. Il decompose
chaque bougie par la methode dite d Ankit :

    body_pct = |close - open| / (high - low)
    haussiere : buy = vol x (0,5 + body_pct/2)   sell = vol x (0,5 - ...)
    baissiere : l inverse

d ou une forme fermee pour le delta d une bougie :

    delta = signe(close - open) x volume x |close - open| / (high - low)

et `vol` est le volume reel si le courtier en donne, le tick_volume
sinon -- exactement le choix de l indicateur, lignes 243 a 251.

Tout cela se reconstruit depuis les M1 OHLCV que MT5 rend par
copy_rates_range. Ni SierraChart, ni fichier de ticks, et les trois
actifs sont couverts, NAS100 compris.

BRUT OU LISSE : LES DEUX SONT MESURES
    L indicateur AFFICHE `EMA(buy) - EMA(sell)`. L EMA etant lineaire
    et les deux series partant de la meme initialisation, cela vaut
    exactement EMA14(delta brut). Le "D -34,4" du panneau est donc une
    moyenne sur quatorze barres, pas le delta d une bougie.

    La regle "-34 doit devenir -35" n a pas le meme sens sur l un et
    sur l autre : sur une EMA elle revient a peu pres a "le delta brut
    depasse sa propre moyenne". Les deux sont donc calcules et affiches
    cote a cote, et c est au lecteur de trancher.

LE CADRAGE : DEUX BOUGIES CLOSES
    A l instant de l entree, la seule chose connue avec certitude est
    l etat des bougies TERMINEES. On compare donc la derniere close a
    celle d avant :

        vente : delta[-1] <= delta[-2] - pas
        achat : delta[-1] >= delta[-2] + pas

    Le cadrage "bougie en cours contre bougie precedente" est AUSSI
    calcule, mais il utilise la bougie qui CONTIENT l entree, donc de
    l information posterieure a la decision. Il est affiche a part et
    marque comme tel : c est une reference, pas un resultat.

L HEURE, ET POURQUOI ELLE EST MESUREE
    `entry_ts` est en heure MACHINE ; les barres MT5 sont en heure
    SERVEUR. Le 25/08 le serveur avait une heure d avance, et une
    fenetre calculee en heure machine a vide une colonne entiere sans
    rien dire. Le decalage est donc LU dans un tick et AFFICHE. Une
    heure d erreur alignerait chaque entree sur la mauvaise bougie et
    donnerait un resultat plein et faux.

CE QU IL NE FAIT PAS
    Il ne rejoue pas la strategie. Refuser une entree ne change ni les
    suivantes ni les sorties : on separe les entrees REELLEMENT prises
    en deux tas et on somme leur PnL reel.
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
except ImportError:
    mt5 = None

TERMINAL_DEDIE = r"C:\Program Files\TF Global Markets MetaTrader 5 Terminal\terminal64.exe"
TICKETS = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
PM = (14, 19)
MAGIC_BAS, MAGIC_HAUT = 220000, 249999
EMA_N = 14
BAR = 60

# L actif tel qu il est ecrit dans le jsonl, et les noms possibles du
# symbole chez le courtier. On ESSAIE, on ne suppose pas : le compte dit
# spx500, le jsonl dit US500, et l indicateur a ".cash" par defaut.
NOMS = {
    "US30":  ("US30", "US30.cash", "us30", "DOW", "DJ30"),
    "US500": ("US500", "SPX500", "spx500", "US500.cash", "SPX500.cash"),
    "US100": ("US100", "NAS100", "nas100", "US100.cash", "NAS100.cash"),
}


def epoch_local(ts):
    """'AAAA-MM-JJ HH:MM:SS' -> epoch de l heure de l HORLOGE, telle
    quelle. La meme convention que celle des horodatages serveur."""
    try:
        d = datetime.datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    return calendar.timegm(d.timetuple())


def maintenant_machine():
    return calendar.timegm(datetime.datetime.now().timetuple())


def decalage_serveur(symboles):
    """(secondes, symbole) -- l avance du serveur sur la machine, LUE."""
    for s in symboles:
        try:
            tk = mt5.symbol_info_tick(s)
        except Exception:
            tk = None
        t = int(getattr(tk, "time", 0) or 0) if tk is not None else 0
        if t > 0:
            return t - maintenant_machine(), s
    return None, None


def delta_bougies(rates):
    """{debut_bougie: (brut, lisse)} -- la decomposition d Ankit, puis
    l EMA14 qui est ce que l indicateur affiche."""
    out, ema = {}, None
    k = 2.0 / (EMA_N + 1.0)
    for r in rates:
        o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), \
            float(r["close"])
        vol = float(r["real_volume"]) if float(r["real_volume"]) > 0 \
            else float(r["tick_volume"])
        etendue = h - l
        if etendue <= 0 or vol <= 0:
            brut = 0.0                    # l indicateur partage 50/50
        else:
            brut = vol * (abs(c - o) / etendue) * (1.0 if c >= o else -1.0)
        ema = brut if ema is None else brut * k + ema * (1.0 - k)
        out[int(r["time"])] = (brut, ema)
    return out


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


def passe(d1, d2, sens, pas):
    """d1 = la plus recente, d2 = celle d avant."""
    if sens == "SELL":
        return d1 <= d2 - pas
    if sens == "BUY":
        return d1 >= d2 + pas
    return None


def tas():
    return {"n": 0, "pnl": 0.0}


def ajoute(d, pnl):
    d["n"] += 1
    d["pnl"] += pnl


def verdict(titre, pris, ref, note=""):
    tot = pris["n"] + ref["n"]
    print("")
    print("-" * 74)
    print(titre)
    print("-" * 74)
    if note:
        print("  %s" % note)
    if tot == 0:
        print("  aucune entree jugee.")
        return
    def tr(x):
        return x["pnl"] / x["n"] if x["n"] else 0.0
    print("  AUTORISEES  %5d (%2.0f %%)   PnL %+10.2f   %+7.2f / trade"
          % (pris["n"], 100.0 * pris["n"] / tot, pris["pnl"], tr(pris)))
    print("  REFUSEES    %5d (%2.0f %%)   PnL %+10.2f   %+7.2f / trade"
          % (ref["n"], 100.0 * ref["n"] / tot, ref["pnl"], tr(ref)))
    print("  total       %5d            PnL %+10.2f   %+7.2f / trade"
          % (tot, pris["pnl"] + ref["pnl"], (pris["pnl"] + ref["pnl"]) / tot))
    print("  la regle rapporte %+.2f  (le PnL des refusees, a l envers)"
          % (-ref["pnl"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--terminal", default=TERMINAL_DEDIE)
    ap.add_argument("--tickets", default=TICKETS)
    ap.add_argument("--pas", type=float, default=1.0)
    ap.add_argument("--sonde", action="store_true",
                    help="dit ce qui est disponible, ne conclut rien")
    a = ap.parse_args()

    print("=" * 74)
    print("CVD V13 -- le delta d Ankit, reproduit, et la regle mesuree")
    print("=" * 74)
    if mt5 is None:
        print("MetaTrader5 introuvable dans cet interpreteur.")
        return 2

    tickets, diag = lit_tickets(a.tickets)
    if tickets is None:
        print("REFUS : %s" % diag["erreur"])
        return 1
    print("  entrees retenues %d   (hors magics %d, hors %02dh-%02dh %d,"
          " sans pnl %d)"
          % (diag["retenus"], diag["hors_plage"], PM[0], PM[1],
             diag["hors_pm"], diag["sans_pnl"]))
    if not tickets:
        print("Aucune entree exploitable.")
        return 1

    if not mt5.initialize(path=a.terminal):
        print("initialize a echoue : %s" % (mt5.last_error(),))
        return 1
    try:
        ai = mt5.account_info()
        if ai is not None:
            print("  terminal : compte %s%s  %s"
                  % (str(ai.login)[:2], "**" + str(ai.login)[-2:],
                     ai.server))

        # -- les symboles, essayes et non supposes
        sym = {}
        for actif, cands in NOMS.items():
            for c in cands:
                try:
                    if mt5.symbol_info(c) is not None:
                        mt5.symbol_select(c, True)
                        sym[actif] = c
                        break
                except Exception:
                    continue
        print("  symboles : %s"
              % (", ".join("%s->%s" % (k, v) for k, v in sorted(sym.items()))
                 or "AUCUN"))
        manquants = [k for k in NOMS if k not in sym]
        if manquants:
            print("  SANS SYMBOLE : %s -- leurs entrees seront comptees a"
                  " part" % ", ".join(manquants))
        if not sym:
            print("")
            print("REFUS : aucun symbole reconnu. Je ne devine pas leurs noms.")
            return 1

        # -- l heure, mesuree
        dec, ref_sym = decalage_serveur(list(sym.values()))
        if dec is None:
            print("")
            print("REFUS : aucun tick lisible, donc aucun moyen de connaitre")
            print("l heure du serveur. Une heure d ecart alignerait chaque")
            print("entree sur la mauvaise bougie. Je m arrete.")
            return 1
        arrondi = int(round(dec / 60.0)) * 60
        print("  decalage serveur - machine : %+d s (%+.2f h), lu sur %s"
              % (dec, dec / 3600.0, ref_sym))
        print("               retenu : %+d s" % arrondi)

        # -- les barres
        t0 = min(t["t"] for t in tickets) + arrondi - 3 * 86400
        t1 = max(t["t"] for t in tickets) + arrondi + 86400
        series = {}
        for actif, s in sorted(sym.items()):
            r = mt5.copy_rates_range(s, mt5.TIMEFRAME_M1,
                                     datetime.datetime.utcfromtimestamp(t0),
                                     datetime.datetime.utcfromtimestamp(t1))
            if r is None or len(r) == 0:
                print("  %-6s %s : aucune barre M1 sur la periode" % (actif, s))
                continue
            series[actif] = delta_bougies(r)
            prem = datetime.datetime.utcfromtimestamp(int(r[0]["time"]))
            der = datetime.datetime.utcfromtimestamp(int(r[-1]["time"]))
            print("  %-6s %-12s %6d barres M1  %s -> %s"
                  % (actif, s, len(r), prem.strftime("%d/%m %H:%M"),
                     der.strftime("%d/%m %H:%M")))

        if a.sonde:
            print("")
            vus = {}
            for t in tickets:
                vus[t["actif"]] = vus.get(t["actif"], 0) + 1
            print("  entrees par actif :")
            for k, v in sorted(vus.items(), key=lambda x: -x[1]):
                print("     %-8s %4d   %s"
                      % (k or "(vide)", v,
                         "mesurable" if k in series else "PAS DE BARRES"))
            print("")
            print("--sonde : rien n a ete conclu.")
            return 0

        # -- la mesure
        cadres = {"close": (tas(), tas()), "close_lisse": (tas(), tas()),
                  "encours": (tas(), tas()), "encours_lisse": (tas(), tas())}
        par_magic, sans = {}, tas()

        for t in tickets:
            s = series.get(t["actif"])
            if not s:
                ajoute(sans, t["pnl"])
                continue
            b = ((t["t"] + arrondi) // BAR) * BAR
            trio = [s.get(b - 2 * BAR), s.get(b - BAR), s.get(b)]
            if trio[0] is None or trio[1] is None:
                ajoute(sans, t["pnl"])
                continue
            for nom, i1, i2, col in (("close", 1, 0, 0),
                                     ("close_lisse", 1, 0, 1),
                                     ("encours", 2, 1, 0),
                                     ("encours_lisse", 2, 1, 1)):
                if trio[i1] is None:
                    continue
                ok = passe(trio[i1][col], trio[i2][col], t["sens"], a.pas)
                if ok is None:
                    continue
                ajoute(cadres[nom][0 if ok else 1], t["pnl"])
                if nom == "close":
                    e = par_magic.setdefault(t["magic"],
                                             {"p": tas(), "r": tas()})
                    ajoute(e["p" if ok else "r"], t["pnl"])

        verdict("DEUX BOUGIES CLOSES -- delta BRUT   (le cadrage causal)",
                *cadres["close"])
        verdict("DEUX BOUGIES CLOSES -- delta LISSE EMA%d" % EMA_N,
                *cadres["close_lisse"])
        verdict("BOUGIE DE L ENTREE contre la precedente -- BRUT",
                *cadres["encours"],
                note="NON CAUSAL : la bougie qui contient l entree n est pas"
                     " terminee au moment ou l on decide. Reference seule.")
        verdict("BOUGIE DE L ENTREE contre la precedente -- LISSE",
                *cadres["encours_lisse"],
                note="NON CAUSAL, meme reserve.")

        if par_magic:
            print("")
            print("-" * 74)
            print("PAR MAGIC -- cadrage causal, delta brut")
            print("-" * 74)
            print("  %-8s %6s %11s %8s %6s %11s %8s"
                  % ("MAGIC", "pris", "PnL", "/trade", "refus", "PnL",
                     "/trade"))
            for m in sorted(par_magic):
                p, r = par_magic[m]["p"], par_magic[m]["r"]
                print("  %-8d %6d %+11.2f %+8.2f %6d %+11.2f %+8.2f"
                      % (m, p["n"], p["pnl"],
                         p["pnl"] / p["n"] if p["n"] else 0.0,
                         r["n"], r["pnl"],
                         r["pnl"] / r["n"] if r["n"] else 0.0))

        if sans["n"]:
            print("")
            print("  NON MESUREES : %d entree(s), PnL %+.2f -- pas de"
                  " symbole ou pas de barres. Ni prises ni refusees."
                  % (sans["n"], sans["pnl"]))
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())

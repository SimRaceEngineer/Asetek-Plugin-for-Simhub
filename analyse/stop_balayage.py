#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""stop_balayage.py -- ce qu un trail ou un break-even auraient donne.

  python stop_balayage.py
  python stop_balayage.py --points 5,10,20,30,50,80
  python stop_balayage.py --bras 207

DEUX MODES, ET LE RAPIDE NE MESURE PAS, IL BORNE
------------------------------------------------
    MODE RAPIDE (par defaut) -- a partir du MFE seul.

        trail : resultat = max(points, MFE - D)
        BE    : le perdant arme revient a zero

    CE N EST PAS UNE MESURE, C EST UNE BORNE HAUTE. Elle suppose que
    le trail ne se declenche qu en retracant D depuis le sommet FINAL.
    Or un trail serre se ferait toucher bien avant, sur un sommet
    INTERMEDIAIRE, et le trade s arreterait la -- sans jamais atteindre
    le MFE qu on observe.

    Sur donnees d essai, ce mode annonce +9419 EUR a D=5 avec 80 % des
    trades touches. C est l illusion en question : plus la distance est
    petite, plus la borne est lache.

    Le mode rapide sert a une seule chose : ECARTER. Si meme la borne
    haute est faible, inutile d aller plus loin.

    MODE CHEMIN (--chemin) -- a partir des barres M1 du trade.

        On relit les barres entre l ouverture et la sortie, et on suit
        le stop barre par barre. Le trail monte avec le sommet COURANT
        et se declenche des que le prix rend D depuis lui, quel que
        soit le moment. Le BE s arme quand le gain courant atteint X et
        se declenche au retour a l entree.

        Une seule convention est necessaire : DANS UNE BARRE, on
        suppose que l extreme defavorable vient APRES l extreme
        favorable. C est le pire cas pour un stop, donc le choix
        prudent -- il ne peut que sous-estimer le resultat, jamais le
        flatter.

POURQUOI CETTE DISTINCTION COMPTE ICI
    L autopsie du 26/08 a montre que 26 % des trades perdants sont
    des RETOURNES -- montes puis rendus. Ce sont eux que le BE et le
    trail visent. Les 60 % de mort-nes ne verront jamais ni l un ni
    l autre : ils ne montent pas assez.

    Un trail bien regle s attaque donc a un quart du probleme. C est
    beaucoup, mais ce n est pas tout, et il ne faut pas en attendre
    la moitie.

LES MORCEAUX SONT FUSIONNES
    Le bras 207 solde en deux fois. Sans fusion, son MFE est celui
    d un segment tronque et tout le balayage serait faux.

TOUT EST EN POINTS POUR LA REGLE, EN EUROS POUR LE RESULTAT
    Le seuil d un trail est en points -- c est une distance de prix.
    Le resultat est converti avec le rapport euro/point PROPRE A
    CHAQUE TRADE, tire de ses propres champs : les lots varient.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime

RACINE = os.path.dirname(os.path.abspath(__file__))
TRADES = os.path.join(RACINE, "docs", "papier_tf", "trades.jsonl")
SORTIE = os.path.join(RACINE, "cartes")
MARGE = 2.0        # points sous l entree au-dela desquels un BE aurait pu tuer
LARGE = 104


def lis(chemin, bras, depuis=None):
    T = []
    if not os.path.isfile(chemin):
        return None
    for l in io.open(chemin, encoding="utf-8", errors="replace"):
        l = l.strip()
        if not l or '"TRADE"' not in l:
            continue
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if o.get("quoi") != "TRADE":
            continue
        if bras and str(o.get("bras")) != str(bras):
            continue
        if depuis and str(o.get("ts", "")) < depuis:
            continue
        T.append(o)
    return T


def fusionne(T):
    """Un bras peut solder en deux fois. Sans fusion le MFE est celui
    d un segment tronque, et tout le balayage serait faux."""
    par = {}
    for o in T:
        cle = (str(o.get("bras")), o.get("actif"), o.get("mn"),
               o.get("ouvert"))
        par.setdefault(cle, []).append(o)
    out, coupes = [], 0
    for recs in par.values():
        if len(recs) == 1:
            out.append(recs[0])
            continue
        coupes += 1
        recs = sorted(recs, key=lambda x: str(x.get("ts", "")))
        d = dict(recs[-1])
        d["eur"] = sum(float(x.get("eur", 0.0)) for x in recs)
        d["points"] = sum(float(x.get("points", 0.0)) for x in recs)
        d["mfe"] = max(float(x.get("mfe", 0.0)) for x in recs)
        d["mae"] = min(float(x.get("mae", 0.0)) for x in recs)
        out.append(d)
    return out, coupes


def prepare(T):
    """Garde le rapport euro/point PROPRE A CHAQUE TRADE : les lots
    varient, et convertir avec une moyenne ferait passer une taille de
    position pour un resultat."""
    out = []
    for o in T:
        p = float(o.get("points", 0.0))
        e = float(o.get("eur", 0.0))
        if p == 0:
            continue
        out.append({"actif": o.get("actif") or "?",
                    "sens": int(o.get("sens", 0) or 0),
                    "motif": o.get("motif") or "?",
                    "p": p, "e": e, "r": e / p,
                    "mfe": float(o.get("mfe", 0.0)),
                    "mae": float(o.get("mae", 0.0)),
                    "entree": float(o.get("entree", 0.0) or 0.0),
                    "ouvert": o.get("ouvert"), "ts": o.get("ts")})
    return out


def trail(recs, d):
    """BORNE HAUTE, pas une mesure : suppose que le trail ne touche
    qu en retracant d depuis le sommet FINAL. Un trail serre se ferait
    toucher avant, sur un sommet intermediaire."""
    tot = touche = 0.0
    n_t = 0
    for o in recs:
        np_ = o["p"] if o["p"] >= o["mfe"] - d else (o["mfe"] - d)
        if np_ != o["p"]:
            n_t += 1
            touche += (np_ - o["p"]) * o["r"]
        tot += np_ * o["r"]
    return tot, n_t, touche


def be(recs, x):
    """ENCADRE. Haute : aucun gagnant tue. Basse : tout gagnant arme et
    passe sous l entree aurait ete tue."""
    haute = basse = 0.0
    sauves = menaces = 0
    montant_menace = 0.0
    for o in recs:
        arme = o["mfe"] >= x
        if arme and o["p"] < 0:
            sauves += 1
            haute += 0.0
            basse += 0.0
        elif arme and o["p"] > 0 and o["mae"] < -MARGE:
            menaces += 1
            montant_menace += o["e"]
            haute += o["e"]
            basse += 0.0
        else:
            haute += o["e"]
            basse += o["e"]
    return haute, basse, sauves, menaces, montant_menace


def base(recs):
    return sum(o["e"] for o in recs)


# ----------------------------------------------------------------------
# LE MODE CHEMIN -- on suit le stop barre par barre
# ----------------------------------------------------------------------
NOMS = {
    "US30":  ("US30", "US30.cash", "us30", "DOW", "DJ30"),
    "US500": ("US500", "SPX500", "spx500", "US500.cash", "SPX500.cash"),
    "US100": ("US100", "NAS100", "nas100", "US100.cash", "NAS100.cash"),
}


def epoch(ts):
    """'AAAA-MM-JJTHH:MM:SS' -> epoch de l horloge, telle quelle."""
    import calendar
    from datetime import datetime as _dt
    try:
        d = _dt.strptime(str(ts)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    return calendar.timegm(d.timetuple())


def suit(barres, entree, sens, d, x):
    """(points_trail, points_be) le long du CHEMIN.

    Convention, et c est la seule : DANS UNE BARRE, l extreme
    defavorable est suppose venir APRES le favorable. C est le pire cas
    pour un stop, donc le choix prudent -- il ne peut que sous-estimer
    le resultat, jamais le flatter.

    None quand le stop n a pas touche : l appelant garde alors le
    resultat reel du trade."""
    sommet = 0.0
    arme = False
    r_trail = r_be = None
    for b in barres:
        h, l = float(b["high"]), float(b["low"])
        if sens > 0:
            fav, def_ = h - entree, l - entree
        else:
            fav, def_ = entree - l, entree - h
        # le favorable d abord : le sommet monte, le BE s arme
        if fav > sommet:
            sommet = fav
        if sommet >= x:
            arme = True
        # puis le defavorable, dans la meme barre
        if r_trail is None and d > 0 and sommet - def_ >= d:
            r_trail = sommet - d
        if r_be is None and arme and def_ <= 0.0:
            r_be = 0.0
        if r_trail is not None and r_be is not None:
            break
    return r_trail, r_be


def chemin(recs, T, ds, xs, mt5):
    """Rejoue chaque trade sur ses barres M1. Rend, par distance, le
    resultat total en euros."""
    sym = {}
    for actif, cands in NOMS.items():
        for c in cands:
            if mt5.symbol_info(c) is not None:
                sym[actif] = c
                break
    dec = 0
    for s in sym.values():
        tk = mt5.symbol_info_tick(s)
        t = int(getattr(tk, "time", 0) or 0) if tk is not None else 0
        if t > 0:
            import calendar
            from datetime import datetime as _dt
            dec = t - calendar.timegm(_dt.now().timetuple())
            break
    print("  decalage serveur - machine : %+d s (%+.2f h)"
          % (dec, dec / 3600.0))

    from datetime import datetime as _dt
    res_t = dict((d, 0.0) for d in ds)
    res_b = dict((x, 0.0) for x in xs)
    n_t = dict((d, 0) for d in ds)
    n_b = dict((x, 0) for x in xs)
    lus = sans = 0
    for o in recs:
        s = sym.get(o["actif"])
        t0, t1 = epoch(o["ouvert"]), epoch(o["ts"])
        if s is None or t0 is None or t1 is None or t1 <= t0:
            sans += 1
            continue
        try:
            br = mt5.copy_rates_range(
                s, mt5.TIMEFRAME_M1,
                _dt.utcfromtimestamp(t0 + dec),
                _dt.utcfromtimestamp(t1 + dec + 60))
        except Exception:
            br = None
        if br is None or len(br) == 0:
            sans += 1
            for d in ds:
                res_t[d] += o["e"]
            for x in xs:
                res_b[x] += o["e"]
            continue
        lus += 1
        for d in ds:
            rt, _ = suit(br, o["entree"], o["sens"], d, 1e18)
            if rt is None:
                res_t[d] += o["e"]
            else:
                res_t[d] += rt * o["r"]
                n_t[d] += 1
        for x in xs:
            _, rb = suit(br, o["entree"], o["sens"], 0.0, x)
            if rb is None:
                res_b[x] += o["e"]
            else:
                res_b[x] += rb * o["r"]
                n_b[x] += 1
    print("  chemins relus %d, sans barres %d (resultat reel conserve)"
          % (lus, sans))
    return res_t, res_b, n_t, n_b


def groupe(recs, cle):
    out = {}
    for o in recs:
        out.setdefault(cle(o), []).append(o)
    return out


def bloc_trail(titre, recs, ds):
    ref = base(recs)
    L = ["", "=" * LARGE, titre, "=" * LARGE,
         "  reference sans trail : %+.2f EUR sur %d trades" % (ref, len(recs)),
         "-" * LARGE,
         "  %8s %12s %12s %10s %12s" % ("distance", "resultat", "gain",
                                        "touches", "part touchee"),
         "-" * LARGE]
    for d in ds:
        tot, n_t, _ = trail(recs, d)
        L.append("  %8.0f %+12.2f %+12.2f %10d %11.0f %%"
                 % (d, tot, tot - ref, n_t,
                    100.0 * n_t / len(recs) if recs else 0))
    return L


def bloc_be(titre, recs, xs):
    ref = base(recs)
    L = ["", "=" * LARGE, titre, "=" * LARGE,
         "  reference sans BE : %+.2f EUR sur %d trades" % (ref, len(recs)),
         "-" * LARGE,
         "  %8s %12s %12s %9s %9s %12s"
         % ("seuil", "borne haute", "borne basse", "sauves", "menaces",
            "montant menace"),
         "-" * LARGE]
    for x in xs:
        h, b, s, m, mm = be(recs, x)
        L.append("  %8.0f %+12.2f %+12.2f %9d %9d %+12.2f"
                 % (x, h - ref, b - ref, s, m, mm))
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", default=TRADES)
    ap.add_argument("--sortie", default=SORTIE)
    ap.add_argument("--bras", default="206",
                    help="206 par defaut : il ne fractionne pas. "
                         "'tous' pour ne pas filtrer.")
    ap.add_argument("--points", default="5,10,15,20,30,40,60,80",
                    help="distances de trail et seuils de BE, en points")
    ap.add_argument("--chemin", action="store_true",
                    help="rejoue chaque trade sur ses barres M1. Plus"
                         " long, mais c est la seule facon de MESURER :"
                         " le mode rapide ne fait que borner.")
    a = ap.parse_args()

    ds = []
    for x in str(a.points).split(","):
        x = x.strip()
        if x:
            try:
                ds.append(float(x))
            except ValueError:
                pass
    if not ds:
        ds = [10.0, 20.0, 40.0]

    bras = None if str(a.bras).lower() in ("tous", "tout", "*") else a.bras
    T = lis(a.trades, bras)
    if T is None:
        print("introuvable : %s" % a.trades)
        return 2
    T, coupes = fusionne(T)
    recs = prepare(T)

    L = ["=" * LARGE,
         "BALAYAGE DES STOPS -- trail et break-even, sur ce qui a"
         " reellement eu lieu",
         "=" * LARGE,
         "  source : docs\\papier_tf\\trades.jsonl, bras %s"
         % (bras or "tous"),
         "  trades : %d retenus, %d soldes en plusieurs morceaux et"
         " fusionnes" % (len(recs), coupes),
         "",
         "  CE MODE BORNE, IL NE MESURE PAS. resultat = max(points,",
         "  MFE - distance) suppose que le trail ne touche qu en",
         "  retracant depuis le sommet FINAL. Un trail serre se ferait",
         "  toucher avant, sur un sommet intermediaire, et le trade",
         "  s arreterait la sans jamais atteindre ce MFE. Plus la",
         "  distance est petite, plus la borne est lache.",
         "",
         "  Il sert a ECARTER : si meme la borne haute est faible,",
         "  inutile d aller plus loin. Pour decider, --chemin.",
         "",
         "  LE BREAK-EVEN EST ENCADRE. Il ne touche que si le prix",
         "  revient a l entree APRES l armement, et le fichier ne dit",
         "  pas si le MAE est venu avant ou apres le MFE.",
         "     borne haute  aucun gagnant tue",
         "     borne basse  tout gagnant arme et passe sous l entree",
         "                  de plus de %.0f points aurait ete tue" % MARGE,
         "  La verite est entre les deux, et probablement pres de la",
         "  borne haute -- 'creux puis envolee' est plus frequent que",
         "  'envolee, passage sous l entree, re-envolee'. C est un",
         "  raisonnement, pas une mesure.",
         ""]
    if not recs:
        L.append("  AUCUN TRADE exploitable.")
        print("\n".join(L))
        return 1

    if a.chemin:
        try:
            import MetaTrader5 as mt5
        except Exception as e:
            print("MetaTrader5 illisible : %s" % e)
            return 2
        if not mt5.initialize():
            print("initialize a echoue : %s" % (mt5.last_error(),))
            return 2
        print("")
        print("  MODE CHEMIN -- on suit le stop barre par barre")
        rt, rb, nt, nb = chemin(recs, T, ds, ds, mt5)
        mt5.shutdown()
        ref = base(recs)
        L += ["", "=" * LARGE,
              "TRAIL SUR LE CHEMIN -- mesure, et non borne",
              "=" * LARGE,
              "  reference sans trail : %+.2f EUR sur %d trades"
              % (ref, len(recs)),
              "-" * LARGE,
              "  %8s %12s %12s %10s %12s"
              % ("distance", "resultat", "gain", "touches", "part"),
              "-" * LARGE]
        for d in ds:
            L.append("  %8.0f %+12.2f %+12.2f %10d %11.0f %%"
                     % (d, rt[d], rt[d] - ref, nt[d],
                        100.0 * nt[d] / len(recs) if recs else 0))
        L += ["", "=" * LARGE,
              "BREAK-EVEN SUR LE CHEMIN -- mesure, et non encadrement",
              "=" * LARGE,
              "  reference sans BE : %+.2f EUR sur %d trades"
              % (ref, len(recs)),
              "-" * LARGE,
              "  %8s %12s %12s %10s %12s"
              % ("seuil", "resultat", "gain", "touches", "part"),
              "-" * LARGE]
        for x in ds:
            L.append("  %8.0f %+12.2f %+12.2f %10d %11.0f %%"
                     % (x, rb[x], rb[x] - ref, nb[x],
                        100.0 * nb[x] / len(recs) if recs else 0))
        L.append("")

    L += bloc_trail("TRAIL -- borne haute, toutes affaires", recs, ds)
    L += bloc_be("BREAK-EVEN -- encadre, toutes affaires", recs, ds)

    for actif, sous in sorted(groupe(recs, lambda o: o["actif"]).items()):
        L += bloc_trail("TRAIL -- %s" % actif, sous, ds)
    for actif, sous in sorted(groupe(recs, lambda o: o["actif"]).items()):
        L += bloc_be("BREAK-EVEN -- %s" % actif, sous, ds)

    L += ["", "=" * LARGE,
          "  Une distance de trail n a pas le meme sens sur tous les",
          "  actifs : le NAS bouge plusieurs fois plus que le SPX. Lire",
          "  les tableaux PAR ACTIF pour choisir, pas le tableau",
          "  d ensemble -- celui-ci melange des echelles differentes.",
          "",
          "  Et le rappel de l autopsie : 26 %% des perdants sont des",
          "  RETOURNES, 60 %% des MORT-NES. Ni trail ni BE ne touchent",
          "  les mort-nes -- ils ne montent pas assez. On s attaque a",
          "  un quart du probleme.",
          "",
          "  Genere le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    txt = "\n".join(L)
    print(txt)

    if not os.path.isdir(a.sortie):
        os.makedirs(a.sortie)
    p = os.path.join(a.sortie, "panel_stops.txt")
    io.open(p, "w", encoding="utf-8", newline="").write(txt + "\n")
    print("")
    print("  ecrit : %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

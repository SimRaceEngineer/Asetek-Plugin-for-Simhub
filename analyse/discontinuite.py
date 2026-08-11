# -*- coding: utf-8 -*-
"""
discontinuite.py -- l ecart de capture survit-il a pic de MFE egal ?

  python discontinuite.py
  python discontinuite.py --largeur 0.25
  python discontinuite.py --depuis 2026-08-05

LE PROBLEME QU IL RESOUT
    bande_morte.py a sorti ceci, le 11/08 :

        bande morte      146 tickets   capture 19%
        lock50 atteint   123 tickets   capture 56%
        lock70 atteint    55 tickets   capture 71%

    Monotone, large, et invendable en l etat. Les trois zones sont
    definies par le pic de MFE atteint : un trade qui culmine a 20 points
    et un trade qui culmine a 101 points ne sont pas la meme population.
    Le second est dans un mouvement plus ample et aurait peut-etre mieux
    capture SANS aucun trailing. La capture croissante peut donc etre une
    propriete des trades, pas un effet des crans.

    Tant que ce confondant tient, ces chiffres ne valent rien.

CE QU ON PEUT FAIRE, ET C EST PROPRE
    Le seuil lock50 est une DISCONTINUITE. A 0.16% du prix d entree, le
    module passe d un cran refuse (BE, vetoe par C14 dans 99.96% des cas)
    a un cran qui passe. Un ticket dont le pic finit juste SOUS le seuil
    et un ticket dont le pic finit juste AU-DESSUS sont des trades quasi
    identiques -- meme actif, meme amplitude, meme journee -- separes par
    un franchissement de quelques dixiemes de point.

    Si la capture saute a cet endroit precis, ce n est plus une
    correlation avec l amplitude : c est l effet du stop. Si elle monte
    doucement de part et d autre sans marche a la frontiere, alors c est
    l amplitude qui portait tout, et la bande morte n est qu une facon de
    nommer les petits trades.

    C est le seul test de ce dossier qui puisse distinguer les deux, et
    il peut parfaitement conclure contre l hypothese.

CE QU IL FAUT LIRE EN PREMIER
    Les effectifs. Une fenetre etroite autour du seuil, sur 343 tickets
    dont 94% joignables, laisse peu de monde de chaque cote. Sous 20
    tickets par cote la comparaison ne se lit pas, et le script le dit au
    lieu de sortir un pourcentage.

CE QU IL NE FAIT PAS
    Il ne prouve pas la causalite au sens strict. Le franchissement du
    seuil n est pas aleatoire : un trade qui va plus loin est un trade
    different, meme de peu. La discontinuite reduit ce biais, elle ne le
    supprime pas. Elle vaut mieux que la comparaison brute, c est tout ce
    qu on lui demande.

    Il ne regarde que mfe_ticket_trail. Les autres systemes de stop
    n ecrivent pas dans ce journal.
"""
import argparse
import csv
import io
import json
import os
import sys
from collections import defaultdict

CSV_DEFAUT = "mfe_trail_events.csv"
TICKETS = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")

OK = 10009
BE_PCT, L50_PCT, L70_PCT = 0.0008, 0.0016, 0.0032
MINI = 20          # sous ce nombre par cote, on ne conclut pas
LARG = 92


def nombre(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def entier(v):
    try:
        return int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def charger(chemin, depuis):
    """Un dict par ticket : pic max vu, cran le plus haut obtenu."""
    par = {}
    lignes = 0
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            lignes += 1
            ts = str(r.get("timestamp") or "")
            if depuis and ts[:10] < depuis:
                continue
            op = nombre(r.get("open_price"))
            pk = nombre(r.get("peak_mfe_pts"))
            tr = entier(r.get("tier"))
            rc = entier(r.get("retcode"))
            tk = str(r.get("ticket") or "").strip()
            if not tk or op is None or pk is None or tr is None or rc is None:
                continue
            d = par.setdefault(tk, {
                "sym": str(r.get("symbol") or "?").strip(),
                "open": op, "jour": ts[:10], "peak": 0.0, "obtenu": 0,
                "tente": 0})
            d["peak"] = max(d["peak"], pk)
            d["tente"] = max(d["tente"], tr)
            if rc == OK:
                d["obtenu"] = max(d["obtenu"], tr)
    return par, lignes


def joindre(par, chemin):
    """Ajoute pnl et mfe en euros. Rend le nombre de tickets joints."""
    if not os.path.isfile(chemin):
        return 0
    n = 0
    for l in io.open(chemin, encoding="utf-8-sig"):
        l = l.strip()
        if not l or l[0] != "{":
            continue
        try:
            o = json.loads(l)
        except ValueError:
            continue
        tk = str(o.get("ticket") or "").strip()
        d = par.get(tk)
        if d is None:
            continue
        p, m = nombre(o.get("pnl_eur")), nombre(o.get("mfe_eur"))
        if p is None:
            continue
        d["pnl"], d["mfe"] = p, m
        n += 1
    return n


def capture(lot):
    """P&L / MFE sur les tickets montes en profit. None si non definie."""
    g = [d for d in lot if d.get("mfe") and d["mfe"] > 0]
    sm = sum(d["mfe"] for d in g)
    if sm <= 0:
        return None, 0
    return 100.0 * sum(d["pnl"] for d in g) / sm, len(g)


def ligne(lab, lot):
    c, n = capture(lot)
    avec = sum(1 for d in lot if d["obtenu"] > 0)
    pnl = sum(d.get("pnl", 0.0) for d in lot)
    print("%-26s %7d %9d %11.2f %10s%s"
          % (lab, len(lot), avec, pnl,
             ("%.0f%%" % c) if c is not None else "-",
             "  ?" if len(lot) < MINI else ""))


def cadre(t):
    print()
    print("=" * LARG)
    print("  " + t)
    print("=" * LARG)


def main():
    global MINI
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=CSV_DEFAUT)
    p.add_argument("--tickets", default=TICKETS)
    p.add_argument("--depuis", default=None)
    p.add_argument("--largeur", type=float, default=0.30,
                   help="demi-fenetre autour du seuil, en fraction du seuil")
    p.add_argument("--mini", type=int, default=MINI)
    a = p.parse_args()
    MINI = a.mini

    if not os.path.isfile(a.csv):
        print("KO : %s introuvable -- lance depuis le dossier de la stack." % a.csv)
        return 1

    par, lignes = charger(a.csv, a.depuis)
    if not par:
        print("Aucun ticket exploitable sur %d lignes." % lignes)
        return 1
    joints = joindre(par, a.tickets)

    print("=== SCALP-EA / LA DISCONTINUITE DU SEUIL lock50 ===")
    print("%d lignes, %d tickets, %d joints a tickets_rails (%.0f%%)"
          % (lignes, len(par), joints, 100.0 * joints / len(par)))
    if not joints:
        print()
        print("Sans P&L il n y a pas de capture a comparer.")
        print("Lance rails_join.py, puis relance ce script.")
        return 1

    lot = [d for d in par.values() if "pnl" in d]

    # Position de chaque ticket par rapport a SON seuil lock50.
    for d in lot:
        s = d["open"] * L50_PCT
        d["seuil"] = s
        d["ratio"] = d["peak"] / s if s > 0 else 0.0

    # -------------------------------------------------- 1. le voisinage
    cadre("AU VOISINAGE DU SEUIL -- des trades presque identiques")
    print("  Fenetre : pic compris entre %.0f%% et %.0f%% du seuil lock50"
          % (100 * (1 - a.largeur), 100 * (1 + a.largeur)))
    print("  du ticket. A gauche le cran est refuse, a droite il passe.")
    print()
    print("%-26s %7s %9s %11s %10s"
          % ("", "tickets", "avec stop", "P&L EUR", "capture"))
    print("-" * LARG)
    gauche = [d for d in lot if 1 - a.largeur <= d["ratio"] < 1.0]
    droite = [d for d in lot if 1.0 <= d["ratio"] <= 1 + a.largeur]
    ligne("juste SOUS le seuil", gauche)
    ligne("juste AU-DESSUS", droite)
    print("-" * LARG)

    cg, _ = capture(gauche)
    cd, _ = capture(droite)
    if len(gauche) < MINI or len(droite) < MINI:
        print("  EFFECTIFS INSUFFISANTS -- %d a gauche, %d a droite, il en"
              % (len(gauche), len(droite)))
        print("  faut %d de chaque cote. Elargis avec --largeur 0.5, en" % MINI)
        print("  sachant qu une fenetre large ramene le confondant qu on")
        print("  cherche justement a eliminer. Ne conclus pas d ici.")
    elif cg is None or cd is None:
        print("  Capture non definie d un cote -- aucun ticket monte en profit.")
    else:
        print("  marche a la frontiere : %+.0f points de capture" % (cd - cg))
        print()
        if cd - cg >= 15:
            print("  Il y a une marche. Deux trades d amplitude voisine ne")
            print("  capturent pas pareil selon que le stop a pu bouger ou")
            print("  non. Le confondant d amplitude n explique pas tout.")
        elif cd - cg <= 5:
            print("  PAS DE MARCHE. A pic comparable, obtenir son stop ne")
            print("  change pas la capture. Les 19%% / 56%% / 71%% de")
            print("  bande_morte.py etaient alors un effet d amplitude, et")
            print("  la bande morte n est qu un autre nom pour les petits")
            print("  trades. NE PAS construire de correctif la-dessus.")
        else:
            print("  Marche faible et fenetre etroite : indecidable. Refais")
            print("  la mesure quand le journal aura une semaine de plus.")

    # ------------------------------------------- 2. le profil, cran par cran
    cadre("LE PROFIL COMPLET -- la marche est-elle AU seuil, ou partout ?")
    print("  Si la capture monte regulierement avec le pic, c est")
    print("  l amplitude. Si elle saute entre 0.9 et 1.1, c est le stop.")
    print()
    bornes = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.0),
              (1.0, 1.1), (1.1, 1.3), (1.3, 2.0), (2.0, 99.0)]
    print("%-26s %7s %9s %11s %10s"
          % ("pic / seuil lock50", "tickets", "avec stop", "P&L EUR", "capture"))
    print("-" * LARG)
    for b, h in bornes:
        sel = [d for d in lot if b <= d["ratio"] < h]
        if sel:
            ligne("%.1f a %.1f" % (b, h), sel)
    print("-" * LARG)
    print("  'avec stop' = tickets ayant obtenu au moins un deplacement.")
    print("  Il doit passer de ~0 a ~tout entre 0.9-1.0 et 1.0-1.1 : c est")
    print("  ce qui fait de ce seuil une discontinuite exploitable.")

    # --------------------------------------------- 3. le contraste interne
    cadre("A L INTERIEUR DE LA BANDE MORTE -- les rares qui ont eu un stop")
    dm = [d for d in lot if d["open"] * BE_PCT <= d["peak"] < d["seuil"]]
    avec = [d for d in dm if d["obtenu"] > 0]
    sans = [d for d in dm if d["obtenu"] == 0]
    print("%-26s %7s %9s %11s %10s"
          % ("", "tickets", "avec stop", "P&L EUR", "capture"))
    print("-" * LARG)
    ligne("bande morte AVEC stop", avec)
    ligne("bande morte SANS stop", sans)
    print("-" * LARG)
    print("  Meme zone, donc meme amplitude a peu pres : le confondant est")
    print("  tenu. Mais les tickets AVEC stop y sont une poignee, et ce")
    print("  n est pas le hasard qui les a servis -- ce sont ceux ou Buddha")
    print("  s etait retourne, ou etait encore en INIT. Ils different donc")
    print("  des autres par autre chose que le stop. A lire comme un indice,")
    print("  jamais comme une preuve.")

    # ------------------------------------------------------- 4. par actif
    cadre("PAR ACTIF -- le meme resultat des deux cotes ?")
    print("%-26s %7s %9s %11s %10s"
          % ("", "tickets", "avec stop", "P&L EUR", "capture"))
    print("-" * LARG)
    for sym in sorted(set(d["sym"] for d in lot)):
        for lab, sel in (("sous seuil", [d for d in lot if d["sym"] == sym
                                         and d["ratio"] < 1.0]),
                         ("au-dessus", [d for d in lot if d["sym"] == sym
                                        and d["ratio"] >= 1.0])):
            if sel:
                ligne("%-10s %s" % (sym, lab), sel)
    print("-" * LARG)
    print("  Un effet reel se retrouve sur les deux actifs. S il n existe")
    print("  que sur un seul, c est une particularite de cet actif, pas un")
    print("  mecanisme -- et les seuils C14 y sont differents (3 pts contre")
    print("  20), ce qui donne un second point de comparaison gratuit.")

    print()
    print("-" * LARG)
    print("Une ligne suivie de ? compte moins de %d tickets." % MINI)
    print("Ce script ne prouve pas la causalite. Le franchissement du seuil")
    print("n est pas aleatoire : aller plus loin, c est deja etre un autre")
    print("trade. La discontinuite reduit ce biais, elle ne l efface pas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

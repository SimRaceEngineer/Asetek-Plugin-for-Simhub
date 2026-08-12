# -*- coding: utf-8 -*-
"""
rails_ecart.py -- serre ou large : l ecartement des rails RSI par pas de temps

  python rails_ecart.py
  python rails_ecart.py --jour 2026-08-12
  python rails_ecart.py --seuil 15 --tfs M1 M3 M5 M15 H1

LA QUESTION

    Les fenetres qui gagnent et celles qui perdent portent le meme etat
    DOUTEUX. L ecartement des rails est le candidat suivant pour les
    departager, et il a un avantage decisif sur le comptage de
    retournements SAR : il est DEJA ECRIT dans chaque ticket, decline par
    pas de temps. On peut donc le tester sur les 3 108 tickets du corpus
    au lieu d une seule journee.

    Ecartement = |bull - bear| sur le pas de temps considere. Le bareme
    du panel rails est repris tel quel : SERRE au-dessous de --seuil
    (15 par defaut), LARGE au-dessus.

CE QU IL NE FAIT PAS

    Il ne recalcule aucun rail. bull et bear sont lus dans les tickets
    avec les memes clefs candidates que oos_v9 -- CLEFS_BULL, CLEFS_BEAR,
    et la niche rails_snapshot -- importees, pas recopiees. Deux lectures
    differentes du meme champ donneraient deux verites.

    Il n INVENTE pas H1. Si aucun ticket ne porte de rails H1, la
    couverture affichee sera nulle et le tableau le dira au lieu de
    montrer une ligne vide qui aurait l air d un resultat.

CE QU IL MESURE, DANS CET ORDRE

    1. la COUVERTURE par pas de temps -- sans elle, tout le reste ment
    2. serre contre large, par pas de temps : tickets, euros, EUR/ticket
    3. le croisement M5 x M15, la combinaison soupconnee
    4. la part de serre dans les fenetres gagnantes et perdantes du jour

    Le point 2 est un test par TICKET : c est le plus gros echantillon
    disponible et il ne depend d aucun decoupage en fenetres.

UNE MISE EN GARDE QUI A DEJA SERVI QUATRE FOIS LE 12/08

    Une cellule sous MINI tickets est imprimee mais marquee d un ?. Elle
    est la pour que rien ne soit cache, pas pour etre lue.

LECTURE SEULE. Aucun ordre. Ecrit panels/rails_ecart.txt.
"""
import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

try:
    import horloge_regime as H
except ImportError:
    print("KO : horloge_regime.py introuvable a cote de ce script.")
    sys.exit(1)

O = H.O
import io
import json

TFS = ["M1", "M3", "M5", "M15", "H1"]
SEUIL = 15.0          # bareme du panel rails : serre au-dessous
MINI = 30             # sous ce nombre de tickets, une cellule ne se lit pas
COUV_MINI = 50.0      # % de couverture sous lequel on refuse de conclure
DEST = os.path.join(_ICI, "panels")
LARG = 100


def rails_nombres(o, tf):
    """(bull, bear) du pas de temps, ou (None, None).

    Memes clefs candidates que oos_v9._etat_tf : la niche d abord, les
    clefs a plat ensuite. On ne reconstruit rien, on lit."""
    src = O._niche(o, tf) or o
    kl, ku = tf.lower(), tf.upper()

    def cands(mod):
        return [m % kl for m in mod] + [m % ku for m in mod]

    b = u = None
    if src is not o:
        b = O._nombre(src.get("bull"))
        u = O._nombre(src.get("bear"))
    if b is None:
        b = O._nombre(O._prem(o, cands(O.CLEFS_BULL)))
    if u is None:
        u = O._nombre(O._prem(o, cands(O.CLEFS_BEAR)))
    return b, u


def charger(chemins, tfs):
    """Un enregistrement par ticket, avec l ecartement par pas de temps."""
    par, brut = {}, 0
    for ch in chemins:
        try:
            f = io.open(ch, encoding="utf-8-sig")
        except IOError:
            continue
        for l in f:
            l = l.strip()
            if not l or l[0] != "{":
                continue
            brut += 1
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ts = str(O._prem(o, O.CLEFS_TS) or "")
            tk = O._prem(o, O.CLEFS_TICKET)
            if len(ts) < 16 or tk is None or tk in par:
                continue
            s = {"ts": ts, "jour": ts[:10], "hm": ts[11:16],
                 "ticket": str(tk),
                 "pnl": O._nombre(O._prem(o, O.CLEFS_PNL)),
                 "actif": H._actif(o), "churn": O._churn(o)}
            for tf in tfs:
                b, u = rails_nombres(o, tf)
                s["ec_" + tf] = (abs(b - u) if (b is not None and u is not None)
                                 else None)
            par[tk] = s
    return list(par.values()), brut


def agrege(lot):
    n = len(lot)
    eur = sum(s["pnl"] for s in lot if s["pnl"] is not None)
    w = sum(1 for s in lot if (s["pnl"] or 0) > 0)
    return n, eur, (eur / n if n else 0.0), (100.0 * w / n if n else 0.0)


def ligne(nom, lot):
    n, eur, par, wr = agrege(lot)
    return ("%-22s %7d %12.2f %11.2f %6.0f%%%s"
            % (nom, n, eur, par, wr, " ?" if n < MINI else ""))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--jour")
    p.add_argument("--tfs", nargs="*", default=TFS)
    p.add_argument("--seuil", type=float, default=SEUIL)
    p.add_argument("--dest", default=DEST)
    a = p.parse_args()

    chemins = a.fichier or O.sources(None)
    lot, brut = charger(chemins, a.tfs)
    if not lot:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        return 1
    if a.jour:
        lot = [s for s in lot if s["jour"] == a.jour]
        if not lot:
            print("Aucun ticket le %s." % a.jour)
            return 1

    L = []
    L.append("=" * LARG)
    L.append("  ECARTEMENT DES RAILS RSI -- serre contre large,"
             " par pas de temps")
    L.append("=" * LARG)
    L.append("ecartement = |bull - bear|   SERRE au-dessous de %.0f,"
             " LARGE au-dessus" % a.seuil)
    L.append("%d tickets, %s -> %s"
             % (len(lot), min(s["jour"] for s in lot),
                max(s["jour"] for s in lot)))
    L.append("")

    L.append("=" * LARG)
    L.append("  COUVERTURE -- sans elle, tout le reste ment")
    L.append("=" * LARG)
    L.append("%-8s %10s %10s %12s %12s"
             % ("TF", "renseigne", "part", "ecart median", "part serre"))
    L.append("-" * LARG)
    utiles = []
    for tf in a.tfs:
        v = [s["ec_" + tf] for s in lot if s["ec_" + tf] is not None]
        part = 100.0 * len(v) / len(lot)
        if v:
            med = sorted(v)[len(v) // 2]
            ser = 100.0 * sum(1 for x in v if x <= a.seuil) / len(v)
            L.append("%-8s %10d %9.0f%% %12.1f %11.0f%%"
                     % (tf, len(v), part, med, ser))
        else:
            L.append("%-8s %10d %9.0f%% %12s %12s"
                     % (tf, 0, 0.0, "-", "-"))
        if part >= COUV_MINI:
            utiles.append(tf)
    L.append("-" * LARG)
    absents = [tf for tf in a.tfs if tf not in utiles]
    if absents:
        L.append("  Sous %.0f%% de couverture : %s. Ces pas de temps ne"
                 % (COUV_MINI, ", ".join(absents)))
        L.append("  sont PAS analyses plus bas. Une ligne calculee sur un")
        L.append("  ticket sur dix ressemble a un resultat et n en est pas.")
    L.append("")

    if not utiles:
        L.append("Aucun pas de temps exploitable. Lance :")
        L.append("    python oos_v9.py --champs")
        for l in L:
            print(l)
        return 1

    L.append("=" * LARG)
    L.append("  SERRE CONTRE LARGE -- test par TICKET, sans decoupage")
    L.append("=" * LARG)
    L.append("%-22s %7s %12s %11s %7s"
             % ("", "N", "EUR total", "EUR/ticket", "WR"))
    L.append("-" * LARG)
    for tf in utiles:
        v = [s for s in lot if s["ec_" + tf] is not None]
        ser = [s for s in v if s["ec_" + tf] <= a.seuil]
        lar = [s for s in v if s["ec_" + tf] > a.seuil]
        L.append(ligne("%s serre" % tf, ser))
        L.append(ligne("%s large" % tf, lar))
        L.append("")
    L.append("-" * LARG)
    L.append("  Si l ecartement dit quelque chose, les deux lignes d un meme")
    L.append("  pas de temps doivent differer nettement en EUR/ticket. Si")
    L.append("  elles se ressemblent, ce pas de temps ne trie rien -- et le")
    L.append("  savoir vaut mieux que de le supposer.")
    L.append("")

    if "M5" in utiles and "M15" in utiles:
        L.append("=" * LARG)
        L.append("  LE CROISEMENT M5 x M15 -- la combinaison soupconnee")
        L.append("=" * LARG)
        L.append("%-22s %7s %12s %11s %7s"
                 % ("", "N", "EUR total", "EUR/ticket", "WR"))
        L.append("-" * LARG)
        v = [s for s in lot
             if s["ec_M5"] is not None and s["ec_M15"] is not None]
        for n5, f5 in (("M5 serre", True), ("M5 large", False)):
            for n15, f15 in (("M15 serre", True), ("M15 large", False)):
                g = [s for s in v
                     if ((s["ec_M5"] <= a.seuil) == f5
                         and (s["ec_M15"] <= a.seuil) == f15)]
                L.append(ligne("%s + %s" % (n5, n15), g))
        L.append("-" * LARG)
        L.append("  Quatre cellules sur le meme corpus : si l une se detache")
        L.append("  franchement, c est la piste. Si les quatre se tiennent,")
        L.append("  le croisement n ajoute rien au simple.")
        L.append("")

    jour = a.jour or max(s["jour"] for s in lot)
    duj = [s for s in lot if s["jour"] == jour]
    if duj:
        L.append("=" * LARG)
        L.append("  LES FENETRES DU %s -- part de serre, gagnantes"
                 " et perdantes" % jour)
        L.append("=" * LARG)
        ech = H.echantillons(duj, jour, H.FENETRE, 1)
        if not ech:
            L.append("  Pas de decoupage possible ce jour-la.")
        else:
            L.append("%-13s %-8s %5s %10s %s"
                     % ("plage", "etat", "tk", "EUR",
                        "  ".join("%-11s" % ("part serre " + tf)
                                  for tf in utiles)))
            L.append("-" * LARG)
            for m0, m1, e, _pa in H.intervalles(ech):
                d, eur = H.chiffres(duj, jour, m0, m1)
                if len(d) < 3:
                    continue
                parts = []
                for tf in utiles:
                    v = [s for s in d if s["ec_" + tf] is not None]
                    parts.append("%-11s" % (
                        "%.0f%%" % (100.0 * sum(1 for s in v
                                                if s["ec_" + tf] <= a.seuil)
                                    / len(v)) if v else "-"))
                L.append("%-13s %-8s %5d %+10.2f %s"
                         % ("%s-%s" % (H.hm(m0), H.hm(m1)), e, len(d), eur,
                            "  ".join(parts)))
            L.append("-" * LARG)
            L.append("  Les trois fenetres qui ont GAGNE le 12/08 --"
                     " 10h34-11h24,")
            L.append("  13h39-14h09, 14h24-14h54 -- sont a comparer aux trois")
            L.append("  qui ont perdu. Si la part de serre les separe, on")
            L.append("  tient un critere ; sinon, il faut chercher ailleurs.")
    L.append("")
    L.append("  ATTENTION : cet ecartement est celui de l entree du ticket.")
    L.append("  Il est donc disponible AU MOMENT d entrer -- c est un signal")
    L.append("  utilisable -- mais la part de serre d une FENETRE ne se")
    L.append("  connait qu apres coup, comme le comptage SAR. Pour s en")
    L.append("  servir en avance il faudra la mesurer en glissant sur le")
    L.append("  passe, comme dans signal_avance.py.")

    for l in L:
        print(l)
    H.ecrire(["# rails_ecart.txt",
              "# ecrit le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "# via rails_ecart.py", ""] + L,
             os.path.join(a.dest, "rails_ecart.txt"))
    print()
    print("ecrit : %s" % os.path.join(a.dest, "rails_ecart.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

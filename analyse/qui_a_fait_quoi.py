# -*- coding: utf-8 -*-
"""
qui_a_fait_quoi.py -- qui declenche en premier, et qui paie

  python qui_a_fait_quoi.py --jour 2026-08-12
  python qui_a_fait_quoi.py --depuis 2026-07-28
  python qui_a_fait_quoi.py --jour 2026-08-12 --top 8

LES DEUX QUESTIONS

    1. Pendant les mouvements qu on a vus, QUI a fait quoi -- en euros
       et en part du total. « M207202 a perdu 161 EUR » ne dit pas la
       meme chose que « M207202 porte 40 % de la perte de la fenetre ».

    2. QUI A ALLUME. Dans chaque fenetre, quel magic et quel actif sont
       entres les PREMIERS. Les tickets portent l horodatage a la
       seconde : l ordre d entree se lit, il n a pas a etre suppose.

POURQUOI LA SECONDE QUESTION EST LA PLUS INTERESSANTE

    Savoir qui perd le plus est une comptabilite. Savoir qui declenche
    est une causalite possible : si le meme magic ouvre le bal dans les
    fenetres qui coutent, et un autre dans celles qui rapportent, on
    tient un signal disponible DES LA PREMIERE ENTREE -- donc avant le
    reste du mouvement, pas apres.

    Le tableau final compte donc, sur toutes les fenetres du corpus,
    combien de fois chaque magic allume, et ce que la fenetre a rendu
    quand c est lui.

CE QU IL N INVENTE PAS

    Les fenetres, les etats et les euros viennent de horloge_regime,
    importe. Le premier entre est celui dont l horodatage est le plus
    petit -- rien de plus. Aucune notion d ignition n est recalculee
    ici : le module ignition.py de la stack a la sienne, et deux
    definitions concurrentes du meme mot seraient pires que pas de
    tableau du tout.

UNE LIMITE, ET ELLE COMPTE

    Le premier entre d une fenetre depend d ou la fenetre commence. Une
    frontiere qui tombe une minute plus tot peut changer le declencheur.
    Le tableau final n a donc de sens qu en NOMBRE : si un magic allume
    trente fois sur quarante fenetres, la frontiere n y est pour rien.
    S il allume trois fois, c est du hasard de decoupage.

LECTURE SEULE. Aucun ordre. Ecrit panels/qui_a_fait_quoi.txt.
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

MINI_TICKETS = 3      # une fenetre plus petite ne raconte rien
MINI_ALLUMAGES = 5    # sous ce nombre, « il allume souvent » n a pas de sens
TOP = 6
DEST = os.path.join(_ICI, "panels")
LARG = 100


def part(x, total):
    """Part en %, du camp de meme signe. Rend '-' si le camp est vide."""
    if not total:
        return "-"
    return "%.0f%%" % (100.0 * x / total)


def detail(d, eur):
    """[(rang, heure, magic, actif, n, eur, part)] par ordre d ENTREE."""
    g = defaultdict(lambda: {"n": 0, "eur": 0.0, "ts": None, "actif": set()})
    for s in d:
        k = s["magic"]
        g[k]["n"] += 1
        if s["pnl"] is not None:
            g[k]["eur"] += s["pnl"]
        g[k]["actif"].add(s["actif"] or "?")
        if g[k]["ts"] is None or s["ts"] < g[k]["ts"]:
            g[k]["ts"] = s["ts"]
    pos = sum(v["eur"] for v in g.values() if v["eur"] > 0)
    neg = sum(v["eur"] for v in g.values() if v["eur"] < 0)
    out = []
    for i, (k, v) in enumerate(sorted(g.items(), key=lambda kv: kv[1]["ts"])):
        camp = pos if v["eur"] > 0 else neg
        out.append((i + 1, v["ts"][11:19], k,
                    "/".join(sorted(v["actif"]))[:12], v["n"], v["eur"],
                    part(v["eur"], camp)))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--jour")
    p.add_argument("--depuis")
    p.add_argument("--top", type=int, default=TOP)
    p.add_argument("--dest", default=DEST)
    a = p.parse_args()

    chemins = a.fichier or H.O.sources(None)
    lot, brut = H.charger(chemins)
    if not lot:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        return 1

    jours = sorted(set(s["jour"] for s in lot))
    if a.jour:
        cibles = [a.jour]
    elif a.depuis:
        cibles = [j for j in jours if j >= a.depuis]
    else:
        cibles = jours[-1:]

    L = []
    L.append("=" * LARG)
    L.append("  QUI DECLENCHE, ET QUI PAIE")
    L.append("=" * LARG)
    L.append("ordre d entree : horodatage du PREMIER ticket de chaque magic")
    L.append("part : part du camp de meme signe -- les perdants entre eux,")
    L.append("les gagnants entre eux")
    L.append("")

    fenetres = []
    for jour in cibles:
        ech = H.echantillons(lot, jour, H.FENETRE, 1)
        if not ech:
            continue
        for m0, m1, e, _pa in H.intervalles(ech):
            d, eur = H.chiffres(lot, jour, m0, m1)
            if len(d) >= MINI_TICKETS:
                fenetres.append((jour, m0, m1, e, d, eur))

    if not fenetres:
        L.append("Aucune fenetre d au moins %d tickets." % MINI_TICKETS)
        for l in L:
            print(l)
        return 1

    gros = sorted(fenetres, key=lambda x: -abs(x[5]))[:a.top]
    for jour, m0, m1, e, d, eur in gros:
        L.append("=" * LARG)
        L.append("  %s  %s-%s  %s  %d min  %d tickets  %+.2f EUR"
                 % (jour, H.hm(m0), H.hm(m1), e, m1 - m0, len(d), eur))
        L.append("=" * LARG)
        L.append("%-5s %-10s %-12s %-13s %7s %12s %8s"
                 % ("rang", "1re entree", "magic", "actif", "trades", "EUR",
                    "part"))
        L.append("-" * LARG)
        for rang, heure, mg, act, n, ep, pc in detail(d, eur):
            L.append("%-5d %-10s %-12s %-13s %7d %+12.2f %8s"
                     % (rang, heure, mg, act, n, ep, pc))
        L.append("-" * LARG)
        prem = detail(d, eur)[0]
        L.append("  premier declenche : %s sur %s a %s"
                 % (prem[2], prem[3], prem[1]))
        L.append("")

    L.append("=" * LARG)
    L.append("  QUI ALLUME LE PLUS SOUVENT -- sur %d fenetres" % len(fenetres))
    L.append("=" * LARG)
    L.append("%-14s %10s %12s %14s %12s"
             % ("magic", "allumages", "EUR total", "EUR/fenetre",
                "fenetres +"))
    L.append("-" * LARG)
    allume = defaultdict(lambda: [0, 0.0, 0])
    for jour, m0, m1, e, d, eur in fenetres:
        prem = detail(d, eur)[0][2]
        allume[prem][0] += 1
        allume[prem][1] += eur
        if eur > 0:
            allume[prem][2] += 1
    for mg, (n, eur, gag) in sorted(allume.items(), key=lambda kv: -kv[1][0]):
        L.append("%-14s %10d %12.2f %14.2f %11d%s"
                 % (mg, n, eur, eur / n, gag,
                    "" if n >= MINI_ALLUMAGES else "  ?"))
    L.append("-" * LARG)
    L.append("  Un ? signale moins de %d allumages : a ce compte, celui qui"
             % MINI_ALLUMAGES)
    L.append("  ouvre le bal depend surtout de l endroit ou la fenetre")
    L.append("  commence, pas du marche. Ces lignes-la ne se lisent pas.")
    L.append("")
    L.append("  Les lignes qui comptent sont celles a beaucoup d allumages :")
    L.append("  si l une d elles a un EUR/fenetre tres au-dessous des autres,")
    L.append("  alors savoir QUI entre en premier est un signal disponible")
    L.append("  des la premiere seconde du mouvement -- et c est le seul")
    L.append("  tableau de la soiree qui puisse en donner un.")

    L.append("")
    L.append("=" * LARG)
    L.append("  QUI PAIE, TOUTES FENETRES CONFONDUES")
    L.append("=" * LARG)
    L.append("%-14s %8s %12s %13s %10s"
             % ("magic", "trades", "EUR total", "EUR/ticket", "part perte"))
    L.append("-" * LARG)
    tot = defaultdict(lambda: [0, 0.0])
    for jour, m0, m1, e, d, eur in fenetres:
        for s in d:
            tot[s["magic"]][0] += 1
            if s["pnl"] is not None:
                tot[s["magic"]][1] += s["pnl"]
    perte = sum(v[1] for v in tot.values() if v[1] < 0)
    for mg, (n, eur) in sorted(tot.items(), key=lambda kv: kv[1][1]):
        L.append("%-14s %8d %12.2f %13.2f %10s"
                 % (mg, n, eur, eur / n if n else 0.0,
                    part(eur, perte) if eur < 0 else "-"))
    L.append("-" * LARG)

    for l in L:
        print(l)
    H.ecrire(["# qui_a_fait_quoi.txt",
              "# ecrit le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "# via qui_a_fait_quoi.py", ""] + L,
             os.path.join(a.dest, "qui_a_fait_quoi.txt"))
    print()
    print("ecrit : %s" % os.path.join(a.dest, "qui_a_fait_quoi.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

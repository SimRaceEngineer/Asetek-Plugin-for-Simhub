# -*- coding: utf-8 -*-
"""
diag_bougies.py -- combien de bougies recoit-on vraiment, et sur quelle plage

  python diag_bougies.py --depuis 2026-07-28
  python diag_bougies.py --jour 2026-08-12

POURQUOI CE SCRIPT EXISTE

    signal_avance.py n a trouve que 143 instants exploitables sur ONZE
    seances, soit treize par jour. A un pas de cinq minutes, cela ferait
    environ deux heures de grille par seance au lieu de dix.

    Une grille courte ne se voit pas : le tableau sort, les quartiles se
    calculent, les chiffres ont l air normaux. Mais s ils ne portent que
    sur un cinquieme de chaque seance, ils ne veulent rien dire -- et
    rien dans la sortie ne l aurait signale.

    Ce script ne fait qu une chose : DIRE ce que MT5 rend vraiment.

CE QU IL AFFICHE, PAR JOUR ET PAR ACTIF

    le nombre de bougies M1 et M5 recues
    la premiere et la derniere, en heure serveur
    les trous : minutes manquantes a l interieur de la plage
    la grille que signal_avance en deduit, en nombre d instants

CE QU IL FAUT LIRE

    Une seance de bourse ouverte en continu doit rendre pres de 1 400
    bougies M1. Si on en recoit 130, la question n est pas dans nos
    scripts : c est la fenetre demandee, la limite du terminal, ou
    l historique reellement telecharge dans MT5.

    Le cas le plus courant et le plus sournois : MT5 ne garde en memoire
    que ce que le graphique a charge. Un actif dont on n a jamais ouvert
    le M1 loin en arriere ne rendra que quelques centaines de bougies,
    silencieusement.

LECTURE SEULE. Aucun ordre, aucun fichier ecrit.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

try:
    import MetaTrader5 as mt5
except ImportError:
    print("KO : MetaTrader5 introuvable dans cet interpreteur.")
    sys.exit(1)

ACTIFS = ["US30", "US500", "US100"]
PASSE, FUTUR, PAS = 30, 30, 5


def mn(t):
    d = datetime.fromtimestamp(t)
    return d.hour * 60 + d.minute


def hm(m):
    return "%02d:%02d" % (m // 60, m % 60)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--actifs", nargs="*", default=ACTIFS)
    p.add_argument("--jour")
    p.add_argument("--depuis")
    p.add_argument("--jours", type=int, default=12)
    a = p.parse_args()

    if not mt5.initialize():
        print("KO : mt5.initialize() a echoue -- %s" % (mt5.last_error(),))
        return 1

    if a.jour:
        cibles = [a.jour]
    else:
        fin = datetime.now()
        deb = (datetime.strptime(a.depuis, "%Y-%m-%d") if a.depuis
               else fin - timedelta(days=a.jours))
        cibles = []
        d = deb
        while d.date() <= fin.date():
            if d.weekday() < 5:
                cibles.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)

    print("=" * 96)
    print(" CE QUE MT5 REND VRAIMENT -- bougies par jour et par actif")
    print("=" * 96)
    print("Une seance ouverte en continu doit rendre pres de 1 400 bougies"
          " M1.")
    print("Heures en heure SERVEUR MT5.")
    print()
    print("%-12s %-8s %-4s %8s %8s %8s %8s %8s"
          % ("jour", "actif", "TF", "bougies", "de", "a", "trous",
             "instants"))
    print("-" * 96)

    total_pts, maigres = 0, []
    for jour in cibles:
        d0 = datetime.strptime(jour, "%Y-%m-%d")
        vu = False
        for act in a.actifs:
            for nom, tf, pas in (("M1", mt5.TIMEFRAME_M1, 1),
                                 ("M5", mt5.TIMEFRAME_M5, 5)):
                r = mt5.copy_rates_range(act, tf, d0, d0 + timedelta(days=1))
                if r is None or len(r) == 0:
                    print("%-12s %-8s %-4s %8s %8s %8s %8s %8s"
                          % (jour, act, nom, 0, "-", "-", "-", "-"))
                    continue
                vu = True
                m0, m1 = mn(r[0]["time"]), mn(r[-1]["time"])
                attendu = (m1 - m0) // pas + 1
                trous = max(0, attendu - len(r))
                pts = max(0, (m1 - m0 - PASSE - FUTUR) // PAS + 1)
                if nom == "M1":
                    total_pts += pts
                    if len(r) < 600:
                        maigres.append((jour, act, len(r)))
                print("%-12s %-8s %-4s %8d %8s %8s %8d %8d"
                      % (jour, act, nom, len(r), hm(m0), hm(m1), trous, pts))
        if vu:
            print("-" * 96)

    mt5.shutdown()
    print()
    print("=" * 96)
    print(" CE QUE CA IMPLIQUE")
    print("=" * 96)
    print("Instants de grille possibles en M1, tous jours et actifs"
          " confondus : %d" % total_pts)
    print("signal_avance en a trouve 143 avec au moins un ticket dans leur")
    print("futur. Si le nombre ci-dessus est du meme ordre, la grille est")
    print("normale et c est la DENSITE DE TRADES qui limite -- pas les")
    print("bougies. S il est dix fois plus grand, ce sont les bougies qui")
    print("manquaient, et les quartiles de ce soir ne portaient que sur une")
    print("fraction de chaque seance.")
    print()
    if maigres:
        print("SEANCES MAIGRES EN M1 (moins de 600 bougies) : %d"
              % len(maigres))
        for jour, act, n in maigres[:12]:
            print("  %-12s %-8s %6d bougies" % (jour, act, n))
        print()
        print("MT5 ne garde en memoire que ce que le graphique a charge.")
        print("Ouvre le M1 de ces actifs et fais defiler loin en arriere,")
        print("puis relance : le nombre doit changer. Si c est le cas, tout")
        print("ce qui a ete calcule sur ces jours est a refaire.")
    else:
        print("Aucune seance maigre : l historique M1 est complet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

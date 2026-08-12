# -*- coding: utf-8 -*-
"""
bougie_news.py -- la bougie anomalie encadre-t-elle vraiment la seance ?

  python bougie_news.py
  python bougie_news.py --jours 20 --actifs US30 US100 US500

L OBSERVATION

    Le 12/08, une bougie M1 d amplitude exceptionnelle a 14h30 Paris
    (08h30 New York, heure des publications). Le reste de l apres-midi
    s est loge dans son haut et son bas :

        US500   7 739,40 -- 7 764,90
        US30   53 840,0  -- 53 984,9
        US100  29 646,7  -- 29 846,2

    Question : est-ce une regularite ou une impression ?

LE PIEGE, ET COMMENT ON LE DESAMORCE

    Une bougie LARGE contient mecaniquement plus de barres qu une
    bougie etroite. Annoncer « 85 % des barres sont restees dedans » ne
    prouverait donc rien.

    Ce script mesure donc DEUX bougies par seance :

        l ANOMALIE  la plus ample de la fenetre, si son amplitude
                    depasse FACTEUR fois la mediane des 30 precedentes
        le TEMOIN   la plus ample d une fenetre du matin

    et rapporte pour chacune le taux de containment ET son amplitude.
    Si l anomalie contient davantage A LARGEUR COMPARABLE, il y a
    quelque chose. Sinon, c est seulement qu elle est large.

IL NE SUPPOSE PAS L HEURE

    Un vrai detecteur ne peut pas coder 14h30 en dur : l heure des
    publications change, et l heure serveur MT5 n est pas l heure de
    Paris. Le script CHERCHE la bougie anormale et IMPRIME son
    horodatage -- ce qui apprend au passage le decalage du courtier.

CE QU IL MESURE, PAR SEANCE ET PAR ACTIF

    heure de l anomalie, son amplitude, son facteur contre la mediane
    part des barres suivantes dont le CLOSE reste dans [bas, haut]
    nombre de touches de chaque borne (a TOLERANCE points pres)
    si une borne est cassee : de combien, et si le prix revient dedans

LECTURE SEULE. Aucun ordre. Il n ecrit rien -- il affiche.
"""
import argparse
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta

try:
    import MetaTrader5 as mt5
except ImportError:
    print("KO : MetaTrader5 introuvable dans cet interpreteur.")
    sys.exit(1)

ACTIFS = ["US30", "US100", "US500"]
FACTEUR = 4.0          # amplitude / mediane des 30 precedentes
FENETRE = (13, 17)     # ou chercher l anomalie, heure serveur
TEMOIN = (9, 12)       # ou prendre la bougie temoin
FIN = 22               # jusqu ou mesurer le containment
TOL = 0.15             # touche = a 0,15 % de la borne... non : voir plus bas
MINI_SEANCES = 8


def med(v):
    return statistics.median(v) if v else 0.0


def analyse_jour(bars, h0, h1, fin, facteur):
    """Trouve la bougie la plus ample de [h0,h1[ et mesure la suite.

    Rend None si la fenetre est vide ou si l amplitude ne depasse pas
    facteur x la mediane des 30 barres precedentes -- une seance sans
    anomalie n a pas a etre comptee comme une anomalie ratee."""
    idx = [i for i, b in enumerate(bars)
           if h0 <= datetime.fromtimestamp(b["time"]).hour < h1]
    if not idx:
        return None
    i = max(idx, key=lambda k: bars[k]["high"] - bars[k]["low"])
    amp = float(bars[i]["high"] - bars[i]["low"])
    prec = [float(b["high"] - b["low"]) for b in bars[max(0, i - 30):i]]
    m = med(prec)
    if m <= 0 or amp < facteur * m:
        return None

    haut, bas = float(bars[i]["high"]), float(bars[i]["low"])
    suite = [b for b in bars[i + 1:]
             if datetime.fromtimestamp(b["time"]).hour < fin]
    if len(suite) < 30:
        return None

    dedans = sum(1 for b in suite if bas <= float(b["close"]) <= haut)
    # Une touche : la barre effleure la borne sans la traverser en cloture.
    tol = amp * 0.05
    t_haut = sum(1 for b in suite
                 if abs(float(b["high"]) - haut) <= tol
                 and float(b["close"]) <= haut)
    t_bas = sum(1 for b in suite
                if abs(float(b["low"]) - bas) <= tol
                and float(b["close"]) >= bas)
    hors = [b for b in suite if not (bas <= float(b["close"]) <= haut)]
    exces = 0.0
    if hors:
        exces = max(max(float(b["close"]) - haut, bas - float(b["close"]))
                    for b in hors)
    return {
        "heure": datetime.fromtimestamp(bars[i]["time"]).strftime("%H:%M"),
        "amp": amp, "facteur": amp / m, "haut": haut, "bas": bas,
        "n": len(suite), "dedans": 100.0 * dedans / len(suite),
        "touches": t_haut + t_bas, "exces": exces,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--actifs", nargs="*", default=ACTIFS)
    p.add_argument("--jours", type=int, default=20)
    p.add_argument("--facteur", type=float, default=FACTEUR)
    a = p.parse_args()

    if not mt5.initialize():
        print("KO : mt5.initialize() a echoue -- %s" % (mt5.last_error(),))
        return 1

    print("=" * 86)
    print(" SCALP-EA / LA BOUGIE ANOMALIE ENCADRE-T-ELLE LA SEANCE ?")
    print("=" * 86)
    print("%d jours, seuil d anomalie : amplitude >= %.1f x la mediane"
          " des 30 precedentes" % (a.jours, a.facteur))
    print("Les heures sont celles du SERVEUR MT5, pas de Paris.")
    print()

    fin = datetime.now()
    debut = fin - timedelta(days=a.jours + 5)

    for actif in a.actifs:
        r = mt5.copy_rates_range(actif, mt5.TIMEFRAME_M1, debut, fin)
        if r is None or len(r) < 500:
            print("%-8s : pas assez d historique." % actif)
            continue
        jours = defaultdict(list)
        for b in r:
            jours[datetime.fromtimestamp(b["time"]).date()].append(b)

        res_a, res_t = [], []
        print("-" * 86)
        print(" %s" % actif)
        print("-" * 86)
        print("  %-10s %-6s %8s %7s %8s %8s %7s" %
              ("jour", "heure", "ampl", "facteur", "dedans", "touches",
               "exces"))
        for j in sorted(jours):
            bars = jours[j]
            an = analyse_jour(bars, FENETRE[0], FENETRE[1], FIN, a.facteur)
            tm = analyse_jour(bars, TEMOIN[0], TEMOIN[1], FIN, a.facteur)
            if an:
                res_a.append(an)
                print("  %-10s %-6s %8.1f %7.1f %7.0f%% %8d %7.1f"
                      % (j, an["heure"], an["amp"], an["facteur"],
                         an["dedans"], an["touches"], an["exces"]))
            if tm:
                res_t.append(tm)

        print("-" * 86)
        if len(res_a) < MINI_SEANCES:
            print("  %d seance(s) avec anomalie -- moins de %d, on ne"
                  " conclut pas." % (len(res_a), MINI_SEANCES))
        else:
            da = med([x["dedans"] for x in res_a])
            aa = med([x["amp"] for x in res_a])
            print("  ANOMALIE : %d seances, mediane dedans %.0f%%,"
                  " amplitude mediane %.1f" % (len(res_a), da, aa))
            if len(res_t) >= MINI_SEANCES:
                dt = med([x["dedans"] for x in res_t])
                at = med([x["amp"] for x in res_t])
                print("  TEMOIN   : %d seances, mediane dedans %.0f%%,"
                      " amplitude mediane %.1f" % (len(res_t), dt, at))
                print()
                if at > 0 and aa / at > 1.3:
                    print("  L anomalie est %.1f fois plus large que le"
                          " temoin." % (aa / at))
                    print("  Elle DEVRAIT donc contenir davantage, meme si")
                    print("  elle n avait aucune vertu. L ecart de"
                          " containment")
                    print("  (%.0f%% contre %.0f%%) n est donc PAS"
                          " interpretable tel quel." % (da, dt))
                    print("  Il faudrait comparer a largeur egale -- ce que")
                    print("  ce script ne fait pas encore.")
                else:
                    print("  Largeurs comparables (%.1f contre %.1f) : la"
                          % (aa, at))
                    print("  difference de containment, si elle existe, est")
                    print("  lisible.")
            else:
                print("  Pas assez de seances temoin pour comparer.")
        print()

    print("=" * 86)
    print(" CE QUE CE COMPTAGE NE DIT PAS")
    print("=" * 86)
    print("  1. Rien sur la RENTABILITE. Savoir que le prix respecte une")
    print("     borne ne dit pas qu on gagne a y trader : il faut croiser")
    print("     avec tickets_rails.jsonl, et ce n est pas fait ici.")
    print("  2. Une bougie large contient plus de barres. Tant que les")
    print("     deux amplitudes different, l ecart de containment melange")
    print("     l effet cherche et cet effet mecanique.")
    print("  3. L heure affichee est celle du serveur MT5. Si l anomalie")
    print("     sort systematiquement a 15h30 serveur, c est 14h30 Paris")
    print("     -- et on aura appris le decalage du courtier au passage.")
    mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())

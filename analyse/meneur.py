# -*- coding: utf-8 -*-
"""
meneur.py -- qui allume en premier SUR LES BOUGIES, et de combien

  python meneur.py --depuis 2026-07-28
  python meneur.py --jour 2026-08-12 --souffle 5 --seuil 3.0
  python meneur.py --depuis 2026-07-28 --souffle 3

L OBSERVATION A VERIFIER

    Sur les trois M1 du 12/08 au soir, la pente propre -- pas le bruit,
    pas les bougies rouges des dernieres minutes -- part visiblement des
    techs ou du S&P. US30 montre encore deux bougies quand l ignition a
    deja eu lieu ailleurs.

    Si ce decalage est REGULIER, alors l ignition d US100 ou d US500 est
    un signal disponible AVANT le mouvement d US30. C est le premier
    signal de la journee qui pourrait l etre vraiment.

POURQUOI SUR LES BOUGIES ET NON SUR LES TRADES

    qui_a_fait_quoi.py lit l ordre d entree des magics : il ne voit donc
    que la ou la stack a decide de trader. Le marche, lui, bouge partout.
    Pour savoir qui MENE, il faut regarder le prix, pas nos entrees.

CE QU EST UNE IGNITION ICI, ET RIEN D AUTRE

    Le mouvement de cloture sur --souffle minutes depasse --seuil fois
    le mouvement TYPIQUE de l actif SUR LA MEME DUREE -- la mediane des
    |variations sur souffle minutes| de la journee.

    La duree compte : normaliser par la variation d UNE bougie serait
    trop laxiste, car une somme sur cinq bougies atteint deja environ la
    racine de cinq fois cette variation par pur hasard. Avec ce mauvais
    seuil le script sortait cinquante ignitions par jour et un test de
    controle a decalage connu (3 et 6 minutes injectees) ne retrouvait
    plus le decalage. Corrige, il rend 3,0 et 6,0.

    La normalisation par actif est indispensable : sans elle, 53 000
    points d US30 et 7 700 d US500 ne se comparent pas, et le tableau
    dirait surtout lequel est le plus cher.

    Deux ignitions de meme sens sur le meme actif sont separees d au
    moins --repos minutes : sinon un seul mouvement en produirait dix.

LE CHIFFRE QUI DECIDE, ET IL EST DUR

    Une ignition sur un souffle de cinq minutes n est CONNUE qu au bout
    de ces cinq minutes. Si US100 precede US30 de deux minutes mais qu il
    en faut cinq pour le savoir, l avance est deja mangee.

        delai net = delai median - souffle

    S il est negatif, le lien existe peut-etre mais il n est PAS
    exploitable a cette definition. Le tableau l affiche en clair et ne
    se cache pas derriere le delai brut. C est la meme lecon que ce
    soir : mesurer avant, pas apres.

CE QU IL AJOUTE

    Pour chaque ignition, les euros des tickets entres dans les
    --apres minutes qui suivent, par actif. Savoir qui mene ne sert que
    si suivre le meneur rapporte.

LECTURE SEULE. Aucun ordre. Ecrit panels/meneur.txt.
"""
import argparse
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

try:
    import horloge_regime as H
except ImportError:
    print("KO : horloge_regime.py introuvable a cote de ce script.")
    sys.exit(1)

try:
    import MetaTrader5 as mt5
except ImportError:
    print("KO : MetaTrader5 introuvable dans cet interpreteur.")
    sys.exit(1)

ACTIFS = ["US100", "US500", "US30"]
SOUFFLE = 5           # minutes de la somme glissante
SEUIL = 3.0           # en unites de bruit de l actif
REPOS = 15            # minutes minimum entre deux ignitions de meme sens
FENETRE = 10          # minutes pour apparier deux ignitions
APRES = 30            # minutes de P&L apres l ignition
MINI_PAIRES = 8       # sous ce nombre, un delai median ne se lit pas
DEST = os.path.join(_ICI, "panels")
LARG = 100


def bougies(actif, jour):
    """[(minute, close)] du jour, en heure serveur."""
    d0 = datetime.strptime(jour, "%Y-%m-%d")
    r = mt5.copy_rates_range(actif, mt5.TIMEFRAME_M1, d0,
                             d0 + timedelta(days=1))
    if r is None or len(r) < 60:
        return []
    out = []
    for b in r:
        d = datetime.fromtimestamp(b["time"])
        out.append((d.hour * 60 + d.minute, float(b["close"])))
    return out


def bruit(serie, souffle):
    """Mediane des |mouvements sur souffle minutes|. L unite de l actif.

    On normalise par le mouvement typique SUR LA MEME DUREE, et non par
    celui d une bougie : une somme sur cinq bougies atteint environ la
    racine de cinq fois la variation unitaire par pur hasard. Un seuil
    exprime en variations unitaires serait donc a peine au-dessus du
    bruit -- il produisait cinquante ignitions par jour, et un test de
    controle a decalage connu ne retrouvait plus le decalage."""
    v = [abs(serie[i][1] - serie[i - souffle][1])
         for i in range(souffle, len(serie))]
    v = [x for x in v if x > 0]
    return statistics.median(v) if v else None


def ignitions(serie, souffle, seuil, repos):
    """[(minute, sens, ampleur en unites de bruit)].

    L instant retenu est le DEBUT du souffle -- c est la que le mouvement
    commence. Mais il n est connu qu a la fin : voir le delai net."""
    u = bruit(serie, souffle)
    if not u:
        return []
    out, derniere = [], {}
    for i in range(souffle, len(serie)):
        d = serie[i][1] - serie[i - souffle][1]
        amp = abs(d) / u
        if amp < seuil:
            continue
        sens = "H" if d > 0 else "B"
        m = serie[i - souffle][0]
        if m - derniere.get(sens, -10000) < repos:
            continue
        derniere[sens] = m
        out.append((m, sens, amp))
    return out


def apparier(a, b, fenetre):
    """[(minute_a, delai)] -- delai > 0 quand b SUIT a.

    Chaque ignition de b ne sert qu une fois : sans cela, une salve sur b
    ferait paraitre a meneur autant de fois qu elle compte de bougies."""
    pris, out = set(), []
    for ma, sa, _ in a:
        cand = [(abs(mb - ma), mb) for mb, sb, _ in b
                if sb == sa and abs(mb - ma) <= fenetre
                and mb not in pris]
        if not cand:
            continue
        cand.sort()
        mb = cand[0][1]
        pris.add(mb)
        out.append((ma, mb - ma))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--jour")
    p.add_argument("--depuis")
    p.add_argument("--actifs", nargs="*", default=ACTIFS)
    p.add_argument("--souffle", type=int, default=SOUFFLE)
    p.add_argument("--seuil", type=float, default=SEUIL)
    p.add_argument("--repos", type=int, default=REPOS)
    p.add_argument("--fenetre", type=int, default=FENETRE)
    p.add_argument("--apres", type=int, default=APRES)
    p.add_argument("--dest", default=DEST)
    a = p.parse_args()

    if not mt5.initialize():
        print("KO : mt5.initialize() a echoue -- %s" % (mt5.last_error(),))
        return 1

    chemins = a.fichier or H.O.sources(None)
    lot, _brut = H.charger(chemins)
    jours = sorted(set(s["jour"] for s in lot)) if lot else []
    if a.jour:
        cibles = [a.jour]
    elif a.depuis:
        cibles = [j for j in jours if j >= a.depuis] or [a.depuis]
    else:
        cibles = jours[-1:]

    L = []
    L.append("=" * LARG)
    L.append("  QUI MENE -- ignitions mesurees sur les bougies M1")
    L.append("=" * LARG)
    L.append("ignition : mouvement sur %d min >= %.1f fois le mouvement TYPIQUE"
             % (a.souffle, a.seuil))
    L.append("           de l actif sur la MEME duree (mediane des |%d min|)"
             % a.souffle)
    L.append("repos    : %d min entre deux ignitions de meme sens"
             % a.repos)
    L.append("appariement : meme sens, a %d minutes pres" % a.fenetre)
    L.append("")

    par_jour, compte = {}, defaultdict(int)
    pnl_apres = defaultdict(lambda: [0, 0.0])
    for jour in cibles:
        ig = {}
        for act in a.actifs:
            s = bougies(act, jour)
            if not s:
                continue
            ig[act] = ignitions(s, a.souffle, a.seuil, a.repos)
            compte[act] += len(ig[act])
            for m, sens, amp in ig[act]:
                d, eur = H.chiffres(lot, jour, m, m + a.apres)
                d = [x for x in d if x["actif"] == act]
                pnl_apres[act][0] += len(d)
                pnl_apres[act][1] += sum(x["pnl"] for x in d
                                         if x["pnl"] is not None)
        if ig:
            par_jour[jour] = ig
    mt5.shutdown()

    if not par_jour:
        L.append("Aucune bougie recuperee. MT5 est-il connecte ?")
        for l in L:
            print(l)
        return 1

    L.append("%-10s %12s %14s %14s"
             % ("actif", "ignitions", "tickets apres", "EUR apres"))
    L.append("-" * LARG)
    for act in a.actifs:
        n, eur = pnl_apres[act]
        L.append("%-10s %12d %14d %+14.2f" % (act, compte[act], n, eur))
    L.append("-" * LARG)
    L.append("  « apres » = les %d minutes suivant chaque ignition, tickets"
             % a.apres)
    L.append("  de CET actif seulement.")
    L.append("")

    L.append("=" * LARG)
    L.append("  QUI PRECEDE QUI, ET DE COMBIEN")
    L.append("=" * LARG)
    L.append("%-18s %8s %12s %12s %14s"
             % ("paire", "paires", "delai median", "part A avant",
                "delai NET"))
    L.append("-" * LARG)
    lignes = []
    for i, x in enumerate(a.actifs):
        for y in a.actifs[i + 1:]:
            tous = []
            for jour, ig in par_jour.items():
                if x in ig and y in ig:
                    tous.extend(d for _m, d in
                                apparier(ig[x], ig[y], a.fenetre))
            if not tous:
                lignes.append("%-18s %8d %12s %12s %14s"
                              % ("%s -> %s" % (x, y), 0, "-", "-", "-"))
                continue
            med = statistics.median(tous)
            avant = 100.0 * sum(1 for d in tous if d > 0) / len(tous)
            net = med - a.souffle
            lignes.append("%-18s %8d %11.1fm %11.0f%% %13.1fm%s"
                          % ("%s -> %s" % (x, y), len(tous), med, avant, net,
                             "" if len(tous) >= MINI_PAIRES else " ?"))
    for l in lignes:
        L.append(l)
    L.append("-" * LARG)
    L.append("  delai median > 0 : le second SUIT le premier.")
    L.append("  part A avant : proportion des appariements ou A precede.")
    L.append("")
    L.append("  LE DELAI NET EST LE SEUL CHIFFRE UTILISABLE. Une ignition")
    L.append("  sur %d minutes n est connue qu au bout de %d minutes ; si"
             % (a.souffle, a.souffle))
    L.append("  l avance mediane est plus courte que ca, elle est deja")
    L.append("  mangee quand on la mesure. Un delai net negatif veut dire")
    L.append("  que le lien existe peut-etre mais qu il ne se trade pas a")
    L.append("  cette definition -- essaie --souffle 3, ou 2.")
    L.append("")
    L.append("  Un ? signale moins de %d appariements : a ce compte le"
             % MINI_PAIRES)
    L.append("  delai median est celui de deux ou trois mouvements, pas")
    L.append("  celui du marche.")

    L.append("")
    L.append("=" * LARG)
    L.append("  LE DETAIL, JOUR PAR JOUR")
    L.append("=" * LARG)
    for jour in sorted(par_jour):
        ig = par_jour[jour]
        L.append("")
        L.append("  %s" % jour)
        tout = []
        for act, v in ig.items():
            tout.extend((m, act, sens, amp) for m, sens, amp in v)
        tout.sort()
        for m, act, sens, amp in tout[:40]:
            L.append("    %s  %-8s %s  %.1f x bruit"
                     % (H.hm(m), act, "hausse" if sens == "H" else "baisse",
                        amp))
        if len(tout) > 40:
            L.append("    ... %d ignitions de plus ce jour-la"
                     % (len(tout) - 40))

    for l in L:
        print(l)
    H.ecrire(["# meneur.txt",
              "# ecrit le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "# via meneur.py", ""] + L,
             os.path.join(a.dest, "meneur.txt"))
    print()
    print("ecrit : %s" % os.path.join(a.dest, "meneur.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

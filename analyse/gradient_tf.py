# -*- coding: utf-8 -*-
"""
gradient_tf.py -- la performance monte-t-elle avec l unite de temps ?

  python gradient_tf.py
  python gradient_tf.py --depuis 2026-07-21 --detail
  python gradient_tf.py --bras 206

CE QUE LE CODE DU MOTEUR A REVELE, LE 12/08

    leader_hold_trader.py ligne 20 :

        Magic = 208 + asset(1/2/3) + 03(M3) : 208103 US30, ...

    ignition_trader.py ligne 54 :

        les vieux 206201/206301 = M1

    Les deux derniers chiffres ne codent pas une strategie. Ils codent
    L UNITE DE TEMPS, EN MINUTES :

        01 = M1    02 = M2    03 = M3    05 = M5    60 = H1

    Le « setup 60 » n existe pas. Les x60 sont les cellules H1 de la
    meme logique d ignition -- memes bras (206 ignition, 207 ignition
    + trail), memes actifs. La seule chose qui change est l echelle.

POURQUOI CE TEST VAUT PLUS QUE LE HORS-ECHANTILLON

    Un magic qui gagne parmi trente est suspect : sur trente candidats
    il y en a forcement un devant. Mais un CLASSEMENT ORDONNE sur cinq
    echelles de temps ne se produit pas par tirage : il y a 120 facons
    de ranger cinq valeurs, et une seule est parfaitement croissante.

    C est une relation dose-effet. Si elle existe, elle dit que ce
    n est pas la cellule H1 qui a de la chance, c est le bruit qui
    diminue quand l echelle augmente -- et ca, ca se transpose.

    Le module la teste par PERMUTATION EXACTE : il enumere les k!
    ordres possibles et compte ceux au moins aussi monotones que
    l observe. Pas d approximation, pas de loi supposee.

TROIS REPLICATIONS INDEPENDANTES

    Le gradient est refait separement sur le bras 206 et sur le bras
    207, puis sur chacun des trois actifs. Cinq courbes qui montent
    dans le meme sens valent infiniment plus qu une seule : elles ne
    partagent ni la logique de sortie, ni l instrument.

CE QUE CA NE DIT PAS

    Rien sur la CAUSE. Que H1 fasse mieux que M1 n explique pas
    pourquoi ; ce module mesure la pente, il ne la justifie pas. Et
    une pente mesuree sur seize seances reste une pente mesuree sur
    seize seances.

    Il refuse de conclure sous MINI tickets par cellule, et sous
    MINI_TF unites de temps -- une « pente » sur deux points est une
    droite, pas une tendance.

LECTURE SEULE. Ecrit panels/gradient_tf.txt.
"""
import argparse
import itertools
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

try:
    import horloge_regime as H
except ImportError:
    print("KO : horloge_regime.py introuvable a cote de ce script.")
    print("Il porte le chargement des tickets. Le recopier ici produirait")
    print("une deuxieme lecture du meme fichier, donc des chiffres")
    print("incomparables avec familles.py et x60_oos.py.")
    sys.exit(1)

ACTIF_CODE = {"1": "US30", "2": "US500", "3": "US100"}
MINI = 20             # tickets sous lesquels une cellule ne se lit pas
MINI_TF = 3           # unites de temps sous lesquelles il n y a pas de pente
DEST = os.path.join(_ICI, "panels")
LARG = 100

RE_MAGIC = re.compile(r"^M(\d+)$")


def decomposer(magic):
    """(bras, actif_attendu, minutes). minutes = les deux derniers
    chiffres lus COMME UNE DUREE -- c est la lecture que le code du
    moteur a confirmee le 12/08, pas une inference de plus."""
    m = RE_MAGIC.match(str(magic))
    if not m or len(m.group(1)) != 6:
        return None, None, None
    d = m.group(1)
    try:
        mn = int(d[4:])
    except ValueError:
        return None, None, None
    return d[:3], ACTIF_CODE.get(d[3]), mn


def libelle(mn):
    if mn is None:
        return "?"
    if mn < 60:
        return "M%d" % mn
    if mn % 60 == 0:
        return "H%d" % (mn // 60)
    return "%dmn" % mn


def agrege(lot):
    n = len(lot)
    eur = sum(s["pnl"] for s in lot if s["pnl"] is not None)
    w = sum(1 for s in lot if (s["pnl"] or 0) > 0)
    return n, eur, (eur / n if n else 0.0), (100.0 * w / n if n else 0.0)


def f(x, n=2):
    return "-" if x is None else ("%.*f" % (n, x))


def rho(xs, ys):
    """Spearman, sur des listes sans ex aequo (les minutes sont
    distinctes par construction)."""
    n = len(xs)
    if n < 2:
        return None
    rx = {v: i for i, v in enumerate(sorted(xs))}
    ry = {v: i for i, v in enumerate(sorted(ys))}
    d2 = sum((rx[a] - ry[b]) ** 2 for a, b in zip(xs, ys))
    return 1.0 - 6.0 * d2 / (n * (n * n - 1))


def permutation(minutes, valeurs):
    """(rho observe, p exact). p = part des k! ordres dont le rho est
    au moins egal a l observe. Exact, enumere -- pas de loi supposee,
    pas de tirage aleatoire dont le resultat changerait d une execution
    a l autre."""
    n = len(minutes)
    if n < MINI_TF:
        return None, None
    obs = rho(minutes, valeurs)
    if obs is None:
        return None, None
    total = mieux = 0
    for perm in itertools.permutations(valeurs):
        total += 1
        r = rho(minutes, list(perm))
        if r is not None and r >= obs - 1e-12:
            mieux += 1
    return obs, float(mieux) / total


def bloc(L, nom, lot, mini=MINI):
    """Une courbe : une ligne par unite de temps, puis le verdict."""
    par = defaultdict(list)
    for s in lot:
        if s["mn"] is not None:
            par[s["mn"]].append(s)
    gardes = sorted(k for k, v in par.items() if len(v) >= mini)
    if len(gardes) < MINI_TF:
        L.append("%-16s  %d unite(s) de temps a %d+ tickets, minimum %d --"
                 % (nom, len(gardes), mini, MINI_TF))
        L.append("%-16s  pas de pente calculable." % "")
        return None
    vals = [agrege(par[k])[2] for k in gardes]
    r, p = permutation(gardes, vals)
    detail = "  ".join("%s %+.1f" % (libelle(k), v)
                       for k, v in zip(gardes, vals))
    L.append("%-16s %s" % (nom, detail))
    L.append("%-16s rho %s   p %s   (%d unites, %d tickets)"
             % ("", f(r), f(p, 3), len(gardes), sum(len(par[k])
                                                    for k in gardes)))
    return r, p, gardes, vals


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--depuis")
    p.add_argument("--bras")
    p.add_argument("--mini", type=int, default=MINI)
    p.add_argument("--detail", action="store_true")
    p.add_argument("--dest", default=DEST)
    a = p.parse_args()

    chemins = a.fichier or H.O.sources(None)
    lot, brut = H.charger(chemins)
    if not lot:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        return 1
    if a.depuis:
        lot = [s for s in lot if s["jour"] >= a.depuis]
    for s in lot:
        s["bras"], _att, s["mn"] = decomposer(s["magic"])
    if a.bras:
        lot = [s for s in lot if s["bras"] == a.bras]
    lot = [s for s in lot if s["mn"] is not None]
    if not lot:
        print("Aucun ticket a magic decomposable sur la periode.")
        return 1

    jours = sorted(set(s["jour"] for s in lot))
    L = []
    L.append("=" * LARG)
    L.append("  LE GRADIENT D UNITE DE TEMPS -- les x60 sont les cellules H1")
    L.append("=" * LARG)
    L.append("%d tickets, %s -> %s" % (len(lot), jours[0], jours[-1]))
    L.append("")
    L.append("  Les deux derniers chiffres du magic sont des MINUTES. Le")
    L.append("  code du moteur le dit deux fois : leader_hold_trader.py")
    L.append("  ligne 20 (« 03(M3) »), ignition_trader.py ligne 54 (« les")
    L.append("  vieux 206201/206301 = M1 »). 60 = H1.")
    L.append("")

    # ------------------------------------------------- le tableau brut
    L.append("=" * LARG)
    L.append("  CHAQUE UNITE DE TEMPS, TOUS BRAS ET ACTIFS CONFONDUS")
    L.append("=" * LARG)
    L.append("%-10s %8s %7s %12s %11s %7s"
             % ("unite", "minutes", "N", "EUR total", "EUR/ticket", "WR"))
    L.append("-" * LARG)
    par = defaultdict(list)
    for s in lot:
        par[s["mn"]].append(s)
    for k in sorted(par):
        n, eur, moy, wr = agrege(par[k])
        L.append("%-10s %8d %7d %12.2f %11.2f %6.0f%%%s"
                 % (libelle(k), k, n, eur, moy, wr,
                    "" if n >= a.mini else "  ?"))
    L.append("-" * LARG)
    L.append("  Trie par duree croissante, pas par performance : c est")
    L.append("  l ordre qu on teste. Un ? signale moins de %d tickets."
             % a.mini)
    L.append("")

    # ------------------------------------------------------ la pente
    L.append("=" * LARG)
    L.append("  LA PENTE, ET SES REPLICATIONS")
    L.append("=" * LARG)
    L.append("  rho = Spearman entre duree et EUR/ticket. p = part des k!")
    L.append("  ordres au moins aussi monotones, enumeres exactement.")
    L.append("")
    gl = bloc(L, "TOUT", lot, a.mini)
    L.append("")
    reps = []
    for br in sorted(set(s["bras"] for s in lot if s["bras"])):
        r = bloc(L, "bras %s" % br, [s for s in lot if s["bras"] == br],
                 a.mini)
        if r:
            reps.append(("bras %s" % br, r))
    L.append("")
    for act in ("US30", "US500", "US100"):
        r = bloc(L, act, [s for s in lot if s["actif"] == act], a.mini)
        if r:
            reps.append((act, r))
    L.append("-" * LARG)

    # ------------------------------------------------------ le verdict
    if not gl:
        L.append("  PAS DE VERDICT D ENSEMBLE : trop peu d unites de temps")
        L.append("  atteignent %d tickets. Baisse --mini pour voir, en" % a.mini)
        L.append("  sachant que ce que tu verras sera plus fragile.")
    else:
        r, pv, gardes, vals = gl
        L.append("  ENSEMBLE : rho = %s sur %d unites, p = %s."
                 % (f(r), len(gardes), f(pv, 3)))
        montants = sum(1 for nom, (rr, _p, _g, _v) in reps if rr and rr > 0)
        if reps:
            L.append("  REPLICATIONS : %d sur %d montent dans le meme sens."
                     % (montants, len(reps)))
        if pv is not None and pv <= 0.05 and montants >= max(1, len(reps) - 1):
            L.append("")
            L.append("  La pente tient, et elle tient sur des populations qui")
            L.append("  ne partagent ni la logique de sortie ni l instrument.")
            L.append("  Ce n est alors pas la cellule H1 qui a de la chance :")
            L.append("  c est le bruit qui diminue quand l echelle augmente.")
            L.append("  C est le seul resultat de cette etude qui justifierait")
            L.append("  de coder les cellules manquantes -- M15 et M30 -- non")
            L.append("  pour essayer, mais pour verifier une prediction.")
        elif pv is not None and pv > 0.20:
            L.append("")
            L.append("  PAS DE PENTE. Les unites de temps ne se rangent pas")
            L.append("  par performance. Le H1 fait peut-etre mieux que les")
            L.append("  autres, mais pas parce qu il est plus long -- et")
            L.append("  alors il redevient un magic qui gagne parmi trente,")
            L.append("  ce qui ne prouve rien. Coder M15 et M30 sur cette")
            L.append("  base serait construire sur du vide.")
        else:
            L.append("")
            L.append("  PENTE INDECISE. p entre 0.05 et 0.20 sur %d points :"
                     % len(gardes))
            L.append("  c est trop peu pour trancher dans un sens ou dans")
            L.append("  l autre. Avec cinq unites de temps, le p le plus")
            L.append("  petit atteignable est 1/120 = 0.008 ; il faut donc")
            L.append("  un ordre presque parfait pour conclure, et on ne")
            L.append("  l a pas.")
    L.append("")
    L.append("  Ce module mesure une pente. Il n explique pas pourquoi elle")
    L.append("  existe, et seize seances restent seize seances.")

    if a.detail:
        L.append("")
        L.append("=" * LARG)
        L.append("  LE DETAIL : chaque cellule bras x actif x unite")
        L.append("=" * LARG)
        L.append("%-10s %-8s %-8s %7s %12s %11s %7s"
                 % ("unite", "bras", "actif", "N", "EUR", "EUR/tk", "WR"))
        L.append("-" * LARG)
        for k in sorted(par):
            for br in sorted(set(s["bras"] for s in par[k] if s["bras"])):
                for act in ("US30", "US500", "US100"):
                    v = [s for s in par[k]
                         if s["bras"] == br and s["actif"] == act]
                    if not v:
                        continue
                    n, eur, moy, wr = agrege(v)
                    L.append("%-10s %-8s %-8s %7d %12.2f %11.2f %6.0f%%%s"
                             % (libelle(k), br, act, n, eur, moy, wr,
                                "" if n >= a.mini else "  ?"))

    for l in L:
        print(l)
    H.ecrire(["# gradient_tf.txt",
              "# ecrit le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "# via gradient_tf.py", ""] + L,
             os.path.join(a.dest, "gradient_tf.txt"))
    print()
    print("ecrit : %s" % os.path.join(a.dest, "gradient_tf.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

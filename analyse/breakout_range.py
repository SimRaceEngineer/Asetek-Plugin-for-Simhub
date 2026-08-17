# -*- coding: utf-8 -*-
r"""
breakout_range.py -- les sorties de RANGE, a l echelle ou l oeil les voit

  python breakout_range.py --schema
  python breakout_range.py
  python breakout_range.py --fenetres 60,240 --tirages 1000

POURQUOI UN SECOND OUTIL

    breakout_qualifie.py mesure le franchissement de `nearest_top`, le
    niveau le plus proche publie par la stack. Sur les donnees reelles
    il s en produit un toutes les trois minutes et demie : c est du
    bruit de niveau, pas une sortie de range.

    Ce que l oeil appelle une cassure, sur un M15 ou un H1, c est le
    prix qui sort du plus haut (ou du plus bas) des N dernieres
    minutes et n y revient pas. C est cet objet-la qu on mesure ici.

    Les CSV portent le prix toutes les dix secondes : on peut donc
    fabriquer la fenetre qu on veut, sans dependre d aucun graphique.

L EVENEMENT, DEFINI AVANT D AVOIR REGARDE

    Fenetre W minutes. A chaque cycle i :

        haut(i) = max des prix sur les W minutes precedant i
        bas(i)  = min des prix sur les W minutes precedant i

    CASSURE HAUSSIERE en i : bid[i] > haut(i) et bid[i-1] <= haut(i).
    Le prix sort par le haut d un range qu il n avait pas franchi.

    PERIODE REFRACTAIRE. Sans elle, une tendance produirait une
    "cassure" a chaque nouveau plus haut -- des centaines pour un seul
    mouvement. On n en compte donc qu UNE par fenetre glissante : apres
    une cassure, aucune autre dans le meme sens pendant W minutes.
    C est ce qui fait la difference entre compter des evenements et
    compter des cycles.

LA CONTINUATION

    A l horizon H minutes, le prix est-il encore au-dela du niveau
    franchi ? Le niveau, c est `haut(i)` -- celui d AVANT la sortie,
    jamais un plus haut recalcule apres coup.

LE TEMOIN APPARIE

    Les cycles ou le prix est a moins de --proche pour cent de la
    LARGEUR du range sous son plus haut, sans le franchir. Meme actif,
    meme journee, meme fenetre, meme voisinage du bord. Sans lui, on
    mesurerait la persistance du prix et on l appellerait continuation.

    La largeur du range sert d unite : "a 10 points du bord" ne veut
    pas dire la meme chose dans un range de 30 points et dans un range
    de 300.

L ENUMERATION EST CALIBREE

    4 fenetres x 3 horizons x 2 sens x 3 actifs = 72 cellules. Le
    maximum de 72 ecarts est grand meme sans aucun effet. On rebat les
    JOURNEES en bloc, on refait toute la recherche, --tirages fois, et
    la p-valeur porte sur le MAXIMUM. Methode validee le 15/08 par
    cassure_par_actif.py.

CE QU IL NE DIT PAS

    Rien sur la direction a prendre : ce sont des taux de continuation,
    pas des signaux. Rien sur le PnL : le lien avec les trades de la
    stack est une autre mesure, a faire separement.

Lecteur SEUL : lit les CSV de cartes\cycles\, ecrit un .txt.
"""
import argparse
import csv
import io
import os
import random
import sys
import datetime as dt

ENTREE = os.path.join("cartes", "cycles")
SORTIE = os.path.join("cartes", "panel_range.txt")
ACTIFS = ("US30", "US500", "US100")
FENETRES = (15, 30, 60, 240)      # minutes
HORIZONS = (15, 60, 240)          # minutes
TIRAGES = 200
GRAINE = 12345
LARG = 104

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def charge(dossier):
    jours = {}
    if not os.path.isdir(dossier):
        return jours
    for nom in sorted(os.listdir(dossier)):
        if not nom.startswith("cycles_") or not nom.endswith(".csv"):
            continue
        with io.open(os.path.join(dossier, nom), encoding="utf-8",
                     errors="replace") as f:
            L = [r for r in csv.DictReader(f, delimiter=";")]
        if L:
            jours[nom[7:-4]] = L
    return jours


def prix(L, actif):
    return [flt(r.get("%s_bid" % actif)) for r in L]


def pas_median(jours):
    p = []
    for L in jours.values():
        for k in range(1, min(len(L), 300)):
            try:
                t0 = dt.datetime.strptime(L[k - 1]["ts"][:19],
                                          "%Y-%m-%d %H:%M:%S")
                t1 = dt.datetime.strptime(L[k]["ts"][:19],
                                          "%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError, TypeError):
                continue
            d = (t1 - t0).total_seconds()
            if 0 < d < 600:
                p.append(d)
    p.sort()
    return p[len(p) // 2] if p else 10.0


def extremes(px, w):
    """Le plus haut et le plus bas des w cycles PRECEDENTS -- soit les
    indices i-w a i-1 inclus, jamais i lui-meme.

    Deux files monotones, O(n) au lieu de O(n*w) : une version naive
    mettrait des minutes sur 42 000 cycles par fenetre et par actif.

    L ORDRE DES TROIS ETAPES EST LE FOND DU SUJET. Purger, puis lire,
    puis empiler. Une premiere version lisait avant de purger et
    purgeait avec `<= i - w` au lieu de `< i - w` : 67 desaccords sur
    200 series aleatoires face a une version naive, et des ranges
    decales d un cycle dans tout le tableau. Le test contre la version
    naive est dans le depot ; il doit etre rejoue a toute modification
    de cette fonction."""
    from collections import deque
    n = len(px)
    hi, lo = [None] * n, [None] * n
    fh, fb = deque(), deque()
    for i in range(n):
        while fh and fh[0] < i - w:
            fh.popleft()
        while fb and fb[0] < i - w:
            fb.popleft()
        hi[i] = px[fh[0]] if fh else None
        lo[i] = px[fb[0]] if fb else None
        v = px[i]
        if v is None:
            continue
        while fh and px[fh[-1]] <= v:
            fh.pop()
        fh.append(i)
        while fb and px[fb[-1]] >= v:
            fb.pop()
        fb.append(i)
    return hi, lo


def evenements(jours, actif, w, proche):
    """Cassures et temoins pour une fenetre de w cycles.

    La periode refractaire est w : apres une sortie, on n en compte
    plus dans le meme sens tant que la fenetre ne s est pas
    renouvelee."""
    cass, temo = [], []
    for j, L in jours.items():
        px = prix(L, actif)
        n = len(px)
        if n < 3 * w:
            continue
        hi, lo = extremes(px, w)
        dernier = {"HAUT": -10 ** 9, "BAS": -10 ** 9}
        for i in range(w + 1, n):
            b0, b1 = px[i - 1], px[i]
            h, l = hi[i], lo[i]
            if b0 is None or b1 is None or h is None or l is None:
                continue
            larg = h - l
            if larg <= 0:
                continue
            for sens, niv, sorti, dedans in (
                    ("HAUT", h, b1 > h, b0 <= h),
                    ("BAS", l, b1 < l, b0 >= l)):
                if sorti and dedans and i - dernier[sens] >= w:
                    dernier[sens] = i
                    cass.append({"jour": j, "i": i, "sens": sens,
                                 "niveau": niv, "larg": larg})
                elif dedans and abs(b0 - niv) <= proche / 100.0 * larg:
                    temo.append({"jour": j, "i": i, "sens": sens,
                                 "niveau": niv, "larg": larg})
    return cass, temo


def suite(jours, actif, ev, h):
    L = jours[ev["jour"]]
    k = ev["i"] + h
    if k >= len(L):
        return None
    b = flt(L[k].get("%s_bid" % actif))
    if b is None:
        return None
    return (b > ev["niveau"]) if ev["sens"] == "HAUT" else (b < ev["niveau"])


def taux(jours, actif, lot, h):
    ok = tot = 0
    for ev in lot:
        r = suite(jours, actif, ev, h)
        if r is None:
            continue
        tot += 1
        ok += 1 if r else 0
    return tot, (100.0 * ok / tot) if tot else None


def grille(jours, ev, a, cyc):
    out = []
    for actif in ACTIFS:
        for w in a.fenetres:
            for sens in ("HAUT", "BAS"):
                c = [e for e in ev[(actif, w)][0] if e["sens"] == sens]
                t = [e for e in ev[(actif, w)][1] if e["sens"] == sens]
                for hm in a.horizons:
                    h = max(1, int(round(hm * 60.0 / cyc)))
                    nc, tc = taux(jours, actif, c, h)
                    nt, tt = taux(jours, actif, t, h)
                    if tc is None or tt is None:
                        continue
                    if nc < a.min_n or nt < a.min_n:
                        continue
                    out.append({"actif": actif, "w": w, "sens": sens,
                                "h": hm, "n": nc, "taux": tc, "n_t": nt,
                                "temoin": tt, "ecart": tc - tt})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entree", default=ENTREE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--fenetres", default=",".join(str(x) for x in FENETRES))
    p.add_argument("--horizons", default=",".join(str(x) for x in HORIZONS))
    p.add_argument("--proche", type=float, default=10.0,
                   help="temoin : distance au bord, en %% de la largeur")
    p.add_argument("--min-n", type=int, default=25, dest="min_n")
    p.add_argument("--max-temoins", type=int, default=3000,
                   dest="max_temoins")
    p.add_argument("--tirages", type=int, default=TIRAGES)
    p.add_argument("--graine", type=int, default=GRAINE)
    p.add_argument("--schema", action="store_true")
    a = p.parse_args()
    a.fenetres = [int(x) for x in a.fenetres.split(",") if x.strip()]
    a.horizons = [int(x) for x in a.horizons.split(",") if x.strip()]

    jours = charge(a.entree)
    if not jours:
        print("KO : aucun CSV dans %s." % a.entree)
        print("     Lance d abord : python extraire_cycles.py")
        return 1
    cyc = pas_median(jours)
    ncyc = sum(len(v) for v in jours.values())
    alea = random.Random(a.graine)

    ev = {}
    reduits = False
    for actif in ACTIFS:
        for wm in a.fenetres:
            w = max(2, int(round(wm * 60.0 / cyc)))
            c, t = evenements(jours, actif, w, a.proche)
            if a.max_temoins and len(t) > a.max_temoins:
                t = alea.sample(t, a.max_temoins)
                reduits = True
            ev[(actif, wm)] = (c, t)

    if a.schema:
        print("%d journees, %d cycles, pas median %.0f s."
              % (len(jours), ncyc, cyc))
        print("%-6s %6s %8s %8s %8s"
              % ("actif", "fen", "cassures", "haut", "temoins"))
        for actif in ACTIFS:
            for wm in a.fenetres:
                c, t = ev[(actif, wm)]
                h = sum(1 for e in c if e["sens"] == "HAUT")
                print("%-6s %5dm %8d %8d %8d"
                      % (actif, wm, len(c), h, len(t)))
        return 0

    dis("=" * LARG)
    dis("LES SORTIES DE RANGE, A L ECHELLE OU L OEIL LES VOIT")
    dis("=" * LARG)
    dis("  %d journees, %d cycles, pas median %.0f s."
        % (len(jours), ncyc, cyc))
    dis("  genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dis()
    dis("  RANGE : le plus haut et le plus bas des W minutes PRECEDENT")
    dis("  le cycle. CASSURE : le prix en sort, alors qu il etait")
    dis("  dedans au cycle d avant.")
    dis()
    dis("  PERIODE REFRACTAIRE de W minutes. Sans elle, une tendance")
    dis("  produirait une cassure a chaque nouveau plus haut -- des")
    dis("  centaines pour un seul mouvement. On compte des evenements,")
    dis("  pas des cycles.")
    dis()
    dis("  TEMOIN : le prix a moins de %.0f %% de la largeur du range"
        % a.proche)
    dis("  sous le bord, sans le franchir. La largeur sert d unite : a")
    dis("  10 points du bord ne veut pas dire la meme chose dans un")
    dis("  range de 30 points et dans un range de 300.")
    if reduits:
        dis()
        dis("  Temoins ECHANTILLONNES a %d par actif et par fenetre."
            % a.max_temoins)
    dis("=" * LARG)
    dis()
    dis("  %-6s %6s %9s %7s %9s" % ("actif", "fen", "cassures", "haut",
                                    "temoins"))
    for actif in ACTIFS:
        for wm in a.fenetres:
            c, t = ev[(actif, wm)]
            h = sum(1 for e in c if e["sens"] == "HAUT")
            dis("  %-6s %5dm %9d %7d %9d" % (actif, wm, len(c), h, len(t)))

    g = grille(jours, ev, a, cyc)
    if not g:
        dis()
        dis("  Aucune cellule n atteint %d evenements." % a.min_n)
        io.open(a.sortie, "w", encoding="utf-8").write("\n".join(_ECHO))
        return 0

    dis()
    dis("-" * LARG)
    dis("  %-6s %6s %-5s %6s  %5s %8s  %6s %8s  %9s"
        % ("actif", "fen", "sens", "horiz", "n", "continue", "n tem",
           "temoin", "ecart"))
    dis("-" * LARG)
    for x in sorted(g, key=lambda y: -y["ecart"]):
        dis("  %-6s %5dm %-5s %5dm  %5d %7.1f%%  %6d %7.1f%%  %+8.1f pts"
            % (x["actif"], x["w"], x["sens"], x["h"], x["n"], x["taux"],
               x["n_t"], x["temoin"], x["ecart"]))

    obs = max(abs(x["ecart"]) for x in g)
    noms = list(jours.keys())
    maxs = []
    for _ in range(a.tirages):
        mel = list(noms)
        alea.shuffle(mel)
        corr = dict((noms[k], jours[mel[k]]) for k in range(len(noms)))
        gg = grille(corr, ev, a, cyc)
        maxs.append(max((abs(x["ecart"]) for x in gg), default=0.0))
    maxs.sort()
    pv = (sum(1 for x in maxs if x >= obs - 1e-12) + 1.0) / (a.tirages + 1.0)

    dis()
    dis("  Permutation : %d tirages, journees rebattues en bloc."
        % a.tirages)
    dis("    ecart maximum observe  : %.1f points" % obs)
    dis("    maximum median sous H0 : %.1f points" % maxs[len(maxs) // 2])
    dis("    seuil 95%% sous H0      : %.1f points"
        % maxs[int(0.95 * len(maxs))])
    dis("    p-valeur               : %.3f" % pv)
    dis()
    if pv <= 0.05:
        dis("  => Le meilleur ecart depasse ce qu on obtient en cherchant")
        dis("     dans du bruit de meme structure (p = %.3f)." % pv)
        dis("     C est un CANDIDAT a pre-enregistrer dans HYPOTHESES.md.")
        dis("     Il a ete choisi parmi %d cellules : le seuil corrige"
            % len(g))
        dis("     le nombre de cases, pas le fait d avoir choisi apres.")
    else:
        dis("  => RIEN NE SE DETACHE (p = %.3f)." % pv)
        dis("     Sortir d un range de W minutes ne dit pas, sur ces")
        dis("     journees, plus que de s en approcher sans en sortir.")
        dis("     C est une reponse, pas un echec de la mesure.")

    dis()
    dis("=" * LARG)
    dis("  Aucune direction dans ce tableau : ce sont des taux de")
    dis("  continuation, pas des signaux. Et aucun lien avec le PnL de")
    dis("  la stack -- c est une autre mesure, a faire separement.")

    d = os.path.dirname(a.sortie)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.sortie, "w", encoding="utf-8").write("\n".join(_ECHO) + "\n")
    print()
    print("ecrit : %s (%d octets)" % (a.sortie, os.path.getsize(a.sortie)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

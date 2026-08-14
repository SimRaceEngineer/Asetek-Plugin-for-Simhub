# -*- coding: utf-8 -*-
"""
richesse_episode.py -- le rang, ou la richesse de l episode ?

  python richesse_episode.py
  python richesse_episode.py --fusion 15 --portee 60
  python richesse_episode.py --depuis 2026-08-05

CE QU ON CONTROLE, ET POURQUOI C EST LE BON CONTROLE

    rang_ignition a montre qu a delai egal le rang 4 bat le rang 1,
    aux deux reglages. J en ai tire H13 : "le nombre d entrees deja
    declenchees confirme que le depart est reel".

    Mais un episode ne compte quatre entrees que s il en a produit
    quatre. Si les episodes riches sont simplement ceux ou le marche
    bougeait fort, alors on mesure l amplitude du mouvement et on
    l appelle une confirmation. Le rang 4 serait bon non pas parce
    qu il est quatrieme, mais parce qu il n existe que dans les bons
    episodes.

    C est exactement la forme d un chiffre garanti par sa methode de
    calcul -- et cette fois le piege est dans MA conclusion.

LA DIFFERENCE QUI DECIDE, ET ELLE EST PRATIQUE

    Le RANG est connu EN DIRECT : au moment ou le quatrieme ticket
    s ouvre, on sait que trois ont deja ete prises. C est un
    compteur.

    La TAILLE FINALE de l episode n est PAS connue : savoir qu il en
    comptera dix suppose de connaitre l avenir. C est une
    retrospection.

    Donc :
      - si l effet survit A TAILLE FIXEE, il est exploitable ;
      - s il disparait a taille fixee, il n est qu une propriete des
        bons episodes, et il n y a rien a en faire en direct.

    Les deux lectures produisent le MEME tableau dans rang_ignition.
    Seul ce decoupage-ci les separe.

CE QU IL FAUT REGARDER, DANS L ORDRE

    Section C : le rang 1 et le rang 4 A TAILLE EGALE. Si le rang 4
    d un episode a 4 entrees ressemble au rang 1 d un episode a 4
    entrees, le rang ne dit rien. S il le bat, le rang dit quelque
    chose.

    Section D : la pente du rang A L INTERIEUR de chaque taille. Une
    pente positive dans plusieurs tailles est la seule preuve
    recevable.

    Section B est descriptive et sert a voir les effectifs. Elle est
    triangulaire par construction : le rang 4 n existe pas dans un
    episode a 2 entrees. Ce n est pas un trou, c est la definition.

LECTEUR SEUL. Aucun ordre, aucune ecriture, aucun effet de bord.
"""
import argparse
import bisect
import collections
import datetime as dt
import io
import json
import os
import sys

CIBLE = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
GROS = ("10", "20", "30", "60")
PETIT = ("01", "02", "03", "05")
SEUIL = 54

TAILLES = ((1, 1), (2, 2), (3, 4), (5, 9), (10, 19), (20, 9999))
TAILLES_NOM = ("1", "2", "3-4", "5-9", "10-19", "20+")
RANGS = ("rang 1", "rang 2", "rang 3", "rang 4", "rang 5-9", "rang 10+")


def taille_nom(n):
    for (lo, hi), nom in zip(TAILLES, TAILLES_NOM):
        if lo <= n <= hi:
            return nom
    return TAILLES_NOM[-1]


def rang_nom(r):
    if r <= 4:
        return "rang %d" % r
    if r <= 9:
        return "rang 5-9"
    return "rang 10+"


def setup_de(magic):
    try:
        d = str(int(magic))
    except (TypeError, ValueError):
        return None
    return d[4:] if len(d) == 6 else None


def horo(s):
    try:
        return dt.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def stat(v):
    n = len(v)
    if not n:
        return None
    return (n, sum(v) / n, sum(v))


def ligne(nom, v, large=28):
    s = stat(v)
    if s is None:
        print("  %-*s        -" % (large, nom))
        return
    n, m, t = s
    print("  %-*s n=%-5d moy %+8.2f  total %+10.2f%s"
          % (large, nom, n, m, t, "" if n >= SEUIL else "  ?"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--fusion", type=int, default=30)
    p.add_argument("--portee", type=int, default=120)
    p.add_argument("--depuis", default=None)
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1

    tickets = []
    for l in io.open(a.fichier, encoding="utf-8", errors="replace"):
        if not l.strip():
            continue
        try:
            d = json.loads(l)
        except ValueError:
            continue
        t = horo(d.get("entry_ts"))
        if t is None:
            continue
        tickets.append({"t": t, "jour": d.get("entry_ts", "")[:10],
                        "actif": d.get("asset"), "sens": d.get("dir"),
                        "setup": setup_de(d.get("magic")),
                        "pnl": d.get("pnl_eur")})
    tickets.sort(key=lambda k: k["t"])
    print("%s : %d tickets dates" % (a.fichier, len(tickets)))
    print("episode : fusion %d min, portee %d min%s"
          % (a.fusion, a.portee,
             ("   depuis %s" % a.depuis) if a.depuis else ""))

    # --- episodes ----------------------------------------------------
    allum = collections.defaultdict(list)
    for k in tickets:
        if k["setup"] in GROS:
            allum[k["actif"]].append((k["t"], k["setup"], k["sens"]))
    for act in allum:
        allum[act].sort(key=lambda x: x[0])

    episodes = collections.defaultdict(list)
    for act, ar in allum.items():
        cur = None
        for t, st, sn in ar:
            if cur is not None and (t - cur["dernier"]).total_seconds() \
                    <= a.fusion * 60:
                cur["dernier"] = t
                cur["n_allum"] += 1
                continue
            cur = {"debut": t, "dernier": t, "n_allum": 1,
                   "sens": sn, "petits": []}
            episodes[act].append(cur)
    if not episodes:
        print("Aucun allumage -- rien a mesurer.")
        return 0

    debuts = dict((act, [e["debut"] for e in eps])
                  for act, eps in episodes.items())
    for k in tickets:
        if k["setup"] not in PETIT or k["pnl"] is None:
            continue
        eps = episodes.get(k["actif"])
        if not eps:
            continue
        i = bisect.bisect_right(debuts[k["actif"]], k["t"]) - 1
        if i < 0:
            continue
        e = eps[i]
        if (k["t"] - e["dernier"]).total_seconds() > a.portee * 60:
            continue
        k["rang"] = len(e["petits"]) + 1
        k["ep"] = e
        e["petits"].append(k)

    def dans(k):
        return (not a.depuis) or k["jour"] >= a.depuis

    # La taille finale est posee APRES coup -- c est justement ce qui
    # la rend inutilisable en direct, et c est tout le sujet.
    rat = []
    for act in episodes:
        for e in episodes[act]:
            e["taille"] = len(e["petits"])
            for k in e["petits"]:
                if dans(k):
                    k["taille"] = e["taille"]
                    rat.append(k)
    if not rat:
        print("Aucun ticket rattache sur la periode demandee.")
        return 0

    # -----------------------------------------------------------------
    print()
    print("A. DISTRIBUTION DES EPISODES PAR TAILLE")
    print("   " + "-" * 58)
    par_t = collections.Counter()
    for act in episodes:
        for e in episodes[act]:
            if e["taille"]:
                par_t[taille_nom(e["taille"])] += 1
    tot_ep = sum(par_t.values())
    for nom in TAILLES_NOM:
        n = par_t.get(nom, 0)
        if n:
            print("   taille %-6s %4d episodes   (%4.1f %%)"
                  % (nom, n, 100.0 * n / tot_ep))
    print("   %d episodes non vides, %d tickets rattaches"
          % (tot_ep, len(rat)))

    # -----------------------------------------------------------------
    print()
    print("B. RANG x TAILLE FINALE DE L EPISODE  (descriptif)")
    print("   Triangulaire par construction : le rang 4 n existe pas")
    print("   dans un episode a 2 entrees. Ce n est pas un trou.")
    print("   " + "-" * 58)
    g = collections.defaultdict(list)
    for k in rat:
        g[(taille_nom(k["taille"]), rang_nom(k["rang"]))].append(k["pnl"])
    for nom in TAILLES_NOM:
        vu = False
        for r in RANGS:
            v = g.get((nom, r), [])
            if v:
                vu = True
                ligne("taille %-6s %s" % (nom, r), v)
        if vu:
            print()

    # -----------------------------------------------------------------
    print("C. LA COMPARAISON QUI DECIDE")
    print("   Le meme rang, dans des episodes de richesse differente.")
    print("   Si le rang 4 d un episode pauvre ressemble au rang 4")
    print("   d un episode riche, alors c est le RANG qui parle et il")
    print("   est exploitable en direct. Si seul le riche est bon,")
    print("   c est la RICHESSE qui parle -- et elle n est pas connue")
    print("   au moment d entrer.")
    print("   " + "-" * 58)
    for r in ("rang 1", "rang 2", "rang 3", "rang 4"):
        vu = False
        for nom in TAILLES_NOM:
            v = g.get((nom, r), [])
            if v:
                vu = True
                ligne("%-8s dans taille %-6s" % (r, nom), v)
        if vu:
            print()

    # -----------------------------------------------------------------
    print("D. LA PENTE DU RANG, A TAILLE FIXEE")
    print("   La seule preuve recevable de H13 : une pente positive")
    print("   du rang A L INTERIEUR d une meme taille, et dans")
    print("   plusieurs tailles. Une seule ne suffit pas.")
    print("   " + "-" * 58)
    for nom in TAILLES_NOM:
        pts = [(r, stat(g.get((nom, r), []))) for r in RANGS]
        pts = [(r, s) for r, s in pts if s]
        if len(pts) < 2:
            continue
        print("   taille %s :" % nom)
        for r, s in pts:
            print("     %-10s n=%-5d moy %+8.2f%s"
                  % (r, s[0], s[1], "" if s[0] >= SEUIL else "  ?"))
        prem = pts[0][1][1]
        dern = pts[-1][1][1]
        print("     pente %s -> %s : %+.2f"
              % (pts[0][0], pts[-1][0], dern - prem))
        print()

    # -----------------------------------------------------------------
    print("E. CE QUI EST CONNU EN DIRECT, ET CE QUI NE L EST PAS")
    print("   " + "-" * 58)
    print("   rang            connu au moment d entrer  -> exploitable")
    print("   taille finale   connue apres l episode    -> retrospectif")
    print()
    riches = [k["pnl"] for k in rat if k["taille"] >= 10]
    pauvres = [k["pnl"] for k in rat if k["taille"] <= 4]
    moyens = [k["pnl"] for k in rat if 5 <= k["taille"] <= 9]
    ligne("episodes a 1-4 entrees", pauvres)
    ligne("episodes a 5-9 entrees", moyens)
    ligne("episodes a 10+ entrees", riches)
    print()
    print("   Si l ecart entre ces trois lignes est plus grand que la")
    print("   pente du rang de la section D, alors l essentiel de ce")
    print("   que j ai appele H13 est de la richesse d episode -- une")
    print("   propriete du marche ce jour-la, pas une regle d entree.")
    print()
    print("-" * 62)
    print("  `?` = moins de %d tickets. ~172 pour une cellule regardee"
          % SEUIL)
    print("  parmi cent. Les cellules de la section C sont petites par")
    print("  construction : croiser deux decoupages divise l effectif.")
    print("  Un resultat qui n apparait que la est a re-tester, pas a")
    print("  appliquer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

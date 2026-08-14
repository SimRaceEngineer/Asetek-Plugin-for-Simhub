# -*- coding: utf-8 -*-
"""
latence_premier.py -- un depart qui tarde a produire sa premiere
                      entree est-il un faux depart ?

  python latence_premier.py
  python latence_premier.py --depuis 2026-08-05
  python latence_premier.py --fusion 15 --portee 60

TEST ANNONCE AVANT D ETRE LANCE (H16 de HYPOTHESES.md)

    Declare d avance, il ne s ajoute pas au compteur des decoupes du
    paragraphe 0 -- le seuil reste z ~ 2.9 et H14, deja a t = 2.5,
    n est pas penalisee par cette recherche.

D OU IL VIENT

    H15 predisait qu un fort debit precoce signalait un mauvais
    episode. Refutee : le debit ne porte rien. Mais la section B
    laissait voir autre chose --

        0 entree pendant le guet   n=304   -8.71
        2-3 entrees                n=278   -4.63

    le PIRE camp est celui qui n a rien produit dans les dix premieres
    minutes. Ce n est pas une histoire de debit, c est peut-etre une
    histoire de LATENCE : un allumage qui met longtemps a entrainer
    une entree n a entraine personne, et ce qui vient ensuite arrive
    sur un depart deja mort.

    Ca recoupe la bande 30-60 min de x05 a -26.58 -- pire que pas de
    couverture du tout.

CE QUI EST MESURE, ET POURQUOI C EST CAUSAL

    La latence du PREMIER ticket est connue a la seconde ou ce
    premier ticket s ouvre. On peut donc decider du sort de tous les
    SUIVANTS.

    Section B evalue donc les tickets de rang >= 2, classes par la
    latence du rang 1. Aucune information posterieure a la decision
    n entre dans le camp juge.

    Le rang 1 lui-meme est inevitable : c est lui qui revele la
    latence. Il est mesure a part, en section C, comme temoin.

LES PIEGES, ECRITS AVANT LE RESULTAT

    1. Latence et duree sont lieees mecaniquement : un episode dont
       le premier ticket arrive a la minute 40 a, par construction,
       moins de temps restant dans la portee. La section E affiche
       duree et nombre de tickets restants par tranche de latence.
       Si le camp "latence longue" a simplement moins de tickets
       apres, on ne mesure pas un effet mais une troncature.
    2. Un episode a UN SEUL ticket n a pas de rang >= 2 : il ne
       contribue pas a la section B. Les episodes courts sont donc
       sous-representes dans le camp juge, alors qu ils sont les
       meilleurs selon H14. A garder en tete avant d attribuer un
       ecart a la latence.
    3. L unite reste l EPISODE. Un n de 300 tickets reparti sur 25
       episodes vaut 25 observations.

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

LAT = ((0, 2, "0-2 min"), (2, 5, "2-5 min"), (5, 10, "5-10 min"),
       (10, 20, "10-20 min"), (20, 40, "20-40 min"),
       (40, 99999, "40 min et +"))
TAILLES = ((1, 4, "1-4"), (5, 9, "5-9"), (10, 19, "10-19"),
           (20, 9999, "20+"))


def cat(x, table):
    for lo, hi, nom in table:
        if lo <= x < hi:
            return nom
    return table[-1][2]


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


def ligne(nom, v, large=24):
    n = len(v)
    if not n:
        print("  %-*s        -" % (large, nom))
        return
    print("  %-*s n=%-5d moy %+8.2f  total %+10.2f%s"
          % (large, nom, n, sum(v) / n, sum(v),
             "" if n >= SEUIL else "  ?"))


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
                        "actif": d.get("asset"),
                        "setup": setup_de(d.get("magic")),
                        "pnl": d.get("pnl_eur")})
    tickets.sort(key=lambda k: k["t"])
    print("%s : %d tickets dates" % (a.fichier, len(tickets)))
    print("episode fusion %d / portee %d%s"
          % (a.fusion, a.portee,
             ("   depuis %s" % a.depuis) if a.depuis else ""))
    print("La latence du 1er ticket est connue quand il s ouvre.")
    print("On juge donc les tickets de rang >= 2. Le rang 1 est temoin.")

    allum = collections.defaultdict(list)
    for k in tickets:
        if k["setup"] in GROS:
            allum[k["actif"]].append(k["t"])
    for act in allum:
        allum[act].sort()

    episodes = collections.defaultdict(list)
    for act, ar in allum.items():
        cur = None
        for t in ar:
            if cur is not None and (t - cur["dernier"]).total_seconds() \
                    <= a.fusion * 60:
                cur["dernier"] = t
                cur["n_allum"] += 1
                continue
            cur = {"debut": t, "dernier": t, "n_allum": 1, "petits": []}
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
        e["petits"].append(k)

    def dans(k):
        return (not a.depuis) or k["jour"] >= a.depuis

    eps_ok = []
    for act in episodes:
        for e in episodes[act]:
            if not e["petits"]:
                continue
            if not dans(e["petits"][0]):
                continue
            e["taille"] = len(e["petits"])
            e["lat"] = (e["petits"][0]["t"]
                        - e["debut"]).total_seconds() / 60.0
            e["duree"] = (e["petits"][-1]["t"]
                          - e["debut"]).total_seconds() / 60.0
            e["suite"] = e["petits"][1:]
            eps_ok.append(e)
    if not eps_ok:
        print("Aucun episode sur la periode demandee.")
        return 0

    print()
    print("A. LA LATENCE PREDIT-ELLE LA TAILLE FINALE ?")
    print("   " + "-" * 58)
    croise = collections.Counter()
    nb = collections.Counter()
    for e in eps_ok:
        c = cat(e["lat"], LAT)
        croise[(c, cat(e["taille"], TAILLES))] += 1
        nb[c] += 1
    for _, _, ln in LAT:
        if not nb.get(ln):
            continue
        det = "   ".join("%s:%-3d" % (tn, croise.get((ln, tn), 0))
                         for _, _, tn in TAILLES)
        print("   %-14s %3d ep.   %s" % (ln, nb[ln], det))

    print()
    print("B. LES TICKETS DE RANG >= 2, PAR LATENCE DU RANG 1")
    print("   Causal : la latence est connue quand le rang 1 s ouvre.")
    print("   " + "-" * 58)
    g = collections.defaultdict(list)
    for e in eps_ok:
        c = cat(e["lat"], LAT)
        for k in e["suite"]:
            g[c].append(k["pnl"])
    for _, _, ln in LAT:
        ligne(ln, g.get(ln, []))

    print()
    print("C. TEMOIN -- le rang 1 lui-meme, par sa propre latence")
    print("   Inevitable : c est lui qui revele la latence. S il")
    print("   porte deja tout l ecart, la regle constate un etat")
    print("   sans rien eviter.")
    print("   " + "-" * 58)
    g1 = collections.defaultdict(list)
    for e in eps_ok:
        g1[cat(e["lat"], LAT)].append(e["petits"][0]["pnl"])
    for _, _, ln in LAT:
        ligne(ln, g1.get(ln, []))

    print()
    print("D. CE QUE REFUSER LA SUITE AURAIT DONNE")
    print("   " + "-" * 58)
    for s in (5, 10, 20):
        garde, refuse = [], []
        for e in eps_ok:
            (refuse if e["lat"] >= s else garde).extend(
                k["pnl"] for k in e["suite"])
        print("   refuser la suite si latence >= %d min :" % s)
        ligne("     garde", garde, 20)
        ligne("     refuse", refuse, 20)

    print()
    print("E. CONTROLE -- la troncature mecanique")
    print("   Un episode dont le 1er ticket arrive tard a moins de")
    print("   temps restant dans la portee. S il a simplement moins")
    print("   de tickets apres, on mesure une troncature et pas un")
    print("   effet.")
    print("   " + "-" * 58)
    for _, _, ln in LAT:
        lot = [e for e in eps_ok if cat(e["lat"], LAT) == ln]
        if not lot:
            continue
        suites = [len(e["suite"]) for e in lot]
        print("   %-14s %3d ep.  suite med %4.1f tk  duree med %6.1f min"
              "  allum %4.2f  taille med %4.1f"
              % (ln, len(lot), sorted(suites)[len(lot) // 2],
                 sorted(e["duree"] for e in lot)[len(lot) // 2],
                 sum(e["n_allum"] for e in lot) / float(len(lot)),
                 sorted(e["taille"] for e in lot)[len(lot) // 2]))

    print()
    print("-" * 62)
    print("  Test ANNONCE avant d etre lance : il ne s ajoute pas au")
    print("  compteur du paragraphe 0. Seuil inchange, z ~ 2.9.")
    print("  `?` = moins de %d tickets. L unite reste l EPISODE :" % SEUIL)
    print("  un n de 300 tickets sur 25 episodes vaut 25 observations.")
    print("  Les episodes a UN SEUL ticket ne contribuent pas a la")
    print("  section B -- or ce sont les meilleurs selon H14. Le camp")
    print("  juge est donc biaise vers les episodes longs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

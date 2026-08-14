# -*- coding: utf-8 -*-
"""
rang_ignition.py -- un seul depart propre, et tout le reste est du FOMO ?

  python rang_ignition.py
  python rang_ignition.py --depuis 2026-08-05
  python rang_ignition.py --fusion 15 --portee 60

LA THESE, TELLE QU ELLE A ETE POSEE

    "Il n y a qu un seul depart propre, une seule entree ignition qui
    lance le marche, et tout le reste est du FOMO ou de l ajout de
    positions opportunistes."

    Si c est vrai : le PREMIER petit ticket qui suit un allumage de
    grand timeframe gagne, et les suivants perdent. On pourrait alors
    horodater l allumage, prendre le rang 1, et poser un marqueur
    "plus rien jusqu au prochain X".

CE QUI CHANGE PAR RAPPORT A martingale_inv.py

    Celui-la mesurait un DELAI (0-15 min, 15-30, 30-60). Celui-ci
    mesure un RANG. Ce n est pas la meme chose : dans une bande de
    quinze minutes il peut y avoir cinq entrees, dont une seule
    propre. Le delai les moyenne ensemble ; le rang les separe.

LE PIEGE, ET SON CONTROLE -- A LIRE AVANT LES CHIFFRES

    Le rang 3 arrive forcement plus tard que le rang 1. Un "effet de
    rang" pourrait donc n etre que l effet de delai deja mesure,
    redecore. C est exactement la forme d un chiffre garanti par sa
    methode de calcul.

    Le seul controle valable est la section D : comparer les rangs A
    L INTERIEUR d une meme bande de delai. Si le rang 1 bat le rang 3
    alors que les deux sont a moins de 15 minutes de l allumage,
    l effet est bien un effet de rang. Sinon c est l horloge, et la
    these n est pas prouvee PAR CE TEST -- ce qui ne la rend pas
    fausse, seulement non demontree ici.

    Aucune conclusion ne doit etre tiree de la section B sans avoir
    lu la section D.

CE QUE CA VERIFIE AUSSI, ET QUI VISE MA PROPRE CONCLUSION

    J ai ecrit que l effet de couverture disparait depuis le 05/08.
    Si, en range, il y a PLUS de petits par allumage qu en trend, la
    moyenne du camp AVEC s effondre mecaniquement meme si le rang 1
    reste bon -- et j aurais mesure la densite du FOMO en croyant
    mesurer la disparition du signal. La section A compte les petits
    par episode avant et apres le 5 aout. Elle tranche.

DEFINITION D UN EPISODE

    Un allumage de grand timeframe ouvre un episode. Un allumage qui
    survient moins de FUSION minutes apres le precedent sur le meme
    actif ne rouvre pas d episode : il prolonge celui en cours -- deux
    grands qui s allument a dix minutes d ecart, c est un depart, pas
    deux. L episode se ferme PORTEE minutes apres son dernier
    allumage.

    Ces deux durees sont des CHOIX, pas des mesures. Elles sont en
    ligne de commande pour qu on puisse voir si le resultat y survit.
    Un effet qui n existe qu a un seul reglage n est pas un effet.

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
COUPURE = "2026-08-05"
BANDES = ((0, 15), (15, 30), (30, 60), (60, 120))


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


def rang_nom(r):
    if r <= 4:
        return "rang %d" % r
    if r <= 9:
        return "rang 5-9"
    return "rang 10+"


RANGS = ("rang 1", "rang 2", "rang 3", "rang 4", "rang 5-9", "rang 10+")


def bande_nom(sec):
    m = sec / 60.0
    for lo, hi in BANDES:
        if lo <= m < hi:
            return "%d-%d min" % (lo, hi)
    return "120+ min"


BANDES_NOM = tuple("%d-%d min" % b for b in BANDES) + ("120+ min",)


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
    p.add_argument("--fusion", type=int, default=30,
                   help="minutes : deux allumages plus proches que ca "
                        "sont UN seul depart")
    p.add_argument("--portee", type=int, default=120,
                   help="minutes : duree d un episode apres son dernier "
                        "allumage")
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
    print("episode : fusion %d min, portee %d min  (des CHOIX -- les"
          % (a.fusion, a.portee))
    print("          faire varier fait partie du test)")

    # --- construction des episodes -----------------------------------
    allum = collections.defaultdict(list)
    for k in tickets:
        if k["setup"] in GROS:
            allum[k["actif"]].append((k["t"], k["setup"], k["sens"]))
    for act in allum:
        allum[act].sort(key=lambda x: x[0])

    episodes = collections.defaultdict(list)   # actif -> [ep, ...]
    for act, ar in allum.items():
        cur = None
        for t, st, sn in ar:
            if cur is not None and (t - cur["dernier"]).total_seconds() \
                    <= a.fusion * 60:
                cur["dernier"] = t
                cur["n_allum"] += 1
                cur["setups"].add(st)
                continue
            cur = {"debut": t, "dernier": t, "n_allum": 1,
                   "setups": set([st]), "sens": sn, "petits": []}
            episodes[act].append(cur)
    if not episodes:
        print("Aucun allumage de grand timeframe -- rien a mesurer.")
        return 0

    # --- rattachement des petits, dans l ordre du temps --------------
    debuts = dict((act, [e["debut"] for e in eps])
                  for act, eps in episodes.items())
    orphelins = []
    for k in tickets:
        if k["setup"] not in PETIT or k["pnl"] is None:
            continue
        eps = episodes.get(k["actif"])
        if not eps:
            orphelins.append(k)
            continue
        i = bisect.bisect_right(debuts[k["actif"]], k["t"]) - 1
        if i < 0:
            orphelins.append(k)
            continue
        e = eps[i]
        if (k["t"] - e["dernier"]).total_seconds() > a.portee * 60:
            orphelins.append(k)
            continue
        k["rang"] = len(e["petits"]) + 1
        k["delai"] = (k["t"] - e["debut"]).total_seconds()
        k["ep_sens"] = e["sens"]
        e["petits"].append(k)

    def dans(k):
        return (not a.depuis) or k["jour"] >= a.depuis

    rattaches = [k for act in episodes for e in episodes[act]
                 for k in e["petits"] if dans(k)]
    orph = [k for k in orphelins if dans(k)]

    # -----------------------------------------------------------------
    # A. Densite des episodes -- avant et depuis le 5 aout
    # -----------------------------------------------------------------
    print()
    print("A. COMBIEN DE PETITS PAR EPISODE")
    print("   Si le range produit plus d entrees par allumage que le")
    print("   trend, alors la moyenne du camp AVEC s effondre toute")
    print("   seule -- et l effet que j ai cru voir disparaitre le")
    print("   05/08 ne serait qu une densite de FOMO. Cette section")
    print("   vise ma propre conclusion.")
    print("   " + "-" * 56)
    for lib, filtre in (("avant le 05/08", lambda j: j < COUPURE),
                        ("depuis le 05/08", lambda j: j >= COUPURE)):
        eps = [e for act in episodes for e in episodes[act]
               if filtre(e["debut"].strftime("%Y-%m-%d"))]
        if not eps:
            print("   %-16s aucun episode" % lib)
            continue
        np_ = [len(e["petits"]) for e in eps]
        na = [e["n_allum"] for e in eps]
        print("   %-16s %3d episodes   %5.2f petits/episode   "
              "%4.2f allumages/episode"
              % (lib, len(eps), sum(np_) / float(len(eps)),
                 sum(na) / float(len(na))))
    print("   %d petits rattaches a un episode, %d hors episode"
          % (len(rattaches), len(orph)))

    # -----------------------------------------------------------------
    # B. Le rang
    # -----------------------------------------------------------------
    print()
    print("B. RESULTAT PAR RANG DANS L EPISODE")
    print("   La these predit : rang 1 positif, decroissance ensuite.")
    print("   NE RIEN CONCLURE ICI SANS LA SECTION D.")
    print("   " + "-" * 56)
    g = collections.defaultdict(list)
    for k in rattaches:
        g[rang_nom(k["rang"])].append(k["pnl"])
    for r in RANGS:
        ligne(r, g.get(r, []))
    ligne("hors episode", [k["pnl"] for k in orph])

    # -----------------------------------------------------------------
    # C. Le rang par setup
    # -----------------------------------------------------------------
    print()
    print("C. RANG x SETUP")
    print("   " + "-" * 56)
    g = collections.defaultdict(list)
    for k in rattaches:
        g[(k["setup"], rang_nom(k["rang"]))].append(k["pnl"])
    for s in PETIT:
        vu = False
        for r in RANGS:
            v = g.get((s, r), [])
            if v:
                vu = True
                ligne("x%s  %s" % (s, r), v)
        if not vu:
            print("  x%s  aucun ticket rattache" % s)

    # -----------------------------------------------------------------
    # D. LE CONTROLE : rang a delai comparable
    # -----------------------------------------------------------------
    print()
    print("D. CONTROLE -- LE RANG, A DELAI COMPARABLE")
    print("   C est la section qui decide. Le rang 3 arrive plus tard")
    print("   que le rang 1 : sans ce controle, un effet de rang peut")
    print("   n etre que l effet de delai deja mesure. Si le rang 1")
    print("   bat les suivants A L INTERIEUR d une meme bande, c est")
    print("   bien le rang. Sinon c est l horloge.")
    print("   " + "-" * 56)
    g = collections.defaultdict(list)
    for k in rattaches:
        g[(bande_nom(k["delai"]), rang_nom(k["rang"]))].append(k["pnl"])
    for b in BANDES_NOM:
        vu = False
        for r in RANGS:
            v = g.get((b, r), [])
            if v:
                vu = True
                ligne("%-11s %s" % (b, r), v)
        if not vu:
            print("  %-11s aucun ticket" % b)

    # -----------------------------------------------------------------
    # E. Le rang et le sens de l episode
    # -----------------------------------------------------------------
    print()
    print("E. RANG x SENS  (par rapport au premier allumage)")
    print("   " + "-" * 56)
    g = collections.defaultdict(list)
    for k in rattaches:
        if k["ep_sens"] and k["sens"]:
            c = "MEME" if k["ep_sens"] == k["sens"] else "CONTRE"
        else:
            c = "INCONNU"
        g[(rang_nom(k["rang"]), c)].append(k["pnl"])
    for r in RANGS:
        for c in ("MEME", "CONTRE"):
            ligne("%s  %s" % (r, c), g.get((r, c), []))

    # -----------------------------------------------------------------
    # F. Ce que la regle aurait donne
    # -----------------------------------------------------------------
    print()
    print("F. CE QUE LA REGLE AURAIT DONNE")
    print("   Somme reelle contre somme si on n avait garde que le")
    print("   rang 1 de chaque episode. La difference n est PAS un")
    print("   gain disponible : elle suppose qu on sache reconnaitre")
    print("   l episode en direct, ce que l horodatage de l allumage")
    print("   permet -- mais elle suppose aussi que le passe se")
    print("   repete, ce que rien ne garantit.")
    print("   " + "-" * 56)
    tout = [k["pnl"] for k in rattaches] + [k["pnl"] for k in orph]
    r1 = [k["pnl"] for k in rattaches if k["rang"] == 1]
    print("   tout ce qui a ete pris      n=%-5d  %+10.2f"
          % (len(tout), sum(tout)))
    print("   rang 1 seulement            n=%-5d  %+10.2f"
          % (len(r1), sum(r1)))
    print("   ecart                                 %+10.2f"
          % (sum(r1) - sum(tout)))

    print()
    print("-" * 60)
    print("RAPPELS")
    print("  fusion et portee sont des choix. Relancer avec")
    print("  --fusion 15 --portee 60 : un effet qui ne survit pas au")
    print("  changement de reglage n est pas un effet.")
    print("  `?` = moins de %d tickets. ~172 pour une cellule" % SEUIL)
    print("  regardee parmi cent.")
    print("  Le rattachement se fait sur l heure d ENTREE : on ne sait")
    print("  pas si le grand etait encore ouvert. Meme limite que")
    print("  martingale_inv -- elle dilue, elle n invente pas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

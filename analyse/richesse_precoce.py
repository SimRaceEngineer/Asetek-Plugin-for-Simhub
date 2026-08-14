# -*- coding: utf-8 -*-
"""
richesse_precoce.py -- la richesse d un episode se voit-elle assez tot
                       pour qu on puisse le refuser ?

  python richesse_precoce.py
  python richesse_precoce.py --guet 15 --fusion 15 --portee 60
  python richesse_precoce.py --depuis 2026-08-05

TEST ANNONCE AVANT D ETRE LANCE (H15 de HYPOTHESES.md)

    C est le point : declare d avance, il ne s ajoute pas au compteur
    des decoupes de fouille. La prediction, le critere de mort et le
    piege sont ecrits dans le fichier AVANT que ce script tourne.

D OU IL VIENT

    H14, mesuree le 14/08 : plus un episode produit d entrees, plus il
    est mauvais.

        tailles 1-9    n=261   +16.54/tk   (52 episodes)
        tailles 10+    n=808    -4.18/tk   (54 episodes)

    Mais la taille FINALE n est pas connue au moment d entrer. H14 ne
    permet donc que de s ARRETER (compter jusqu a quatre), pas de
    REFUSER. Pour refuser, il faudrait voir la richesse arriver.

LA REGLE EST STRICTEMENT CAUSALE, ET C EST TOUT L INTERET

    On regarde les GUET premieres minutes de l episode, on compte les
    entrees, on decide -- et on n evalue QUE les tickets ouverts APRES
    la minute GUET. Aucune information posterieure a la decision
    n entre dans le camp qu on juge.

    C est la difference avec richesse_episode.py, qui classait par la
    taille finale : utile pour comprendre, inutilisable en direct.
    Ici, si l ecart apparait, il est exploitable tel quel.

LE PIEGE PRINCIPAL, ECRIT AVANT LE RESULTAT

    Un fort debit precoce et un mauvais resultat peuvent avoir la meme
    cause sans que l un predise l autre : la volatilite. Si les
    episodes a fort debit sont simplement les seances agitees, on
    mesure la volatilite et on l appelle une regle.

    La section E controle ce qu elle peut : nombre d allumages et
    duree. Ce qu elle ne peut pas controler, faute de prix dans
    tickets_rails, c est l amplitude. A garder en tete -- ce test peut
    donc CONFIRMER une regle utilisable sans pour autant en donner la
    cause.

SECOND PIEGE

    Un episode qui n a produit AUCUNE entree pendant le guet n a pas
    "un faible debit" : il n a peut-etre simplement pas encore
    commence. Il est compte a part (`0 pendant le guet`) et non
    fusionne avec les faibles debits.

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

DEBITS = ((0, 0, "0 pendant le guet"), (1, 1, "1 entree"),
          (2, 3, "2-3 entrees"), (4, 6, "4-6 entrees"),
          (7, 9999, "7 entrees et +"))
TAILLES = ((1, 4, "1-4"), (5, 9, "5-9"), (10, 19, "10-19"),
           (20, 9999, "20+"))


def cat(n, table):
    for lo, hi, nom in table:
        if lo <= n <= hi:
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


def ligne(nom, v, large=26):
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
    p.add_argument("--guet", type=int, default=10,
                   help="minutes d observation avant de decider")
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
                        "actif": d.get("asset"), "setup": setup_de(d.get("magic")),
                        "pnl": d.get("pnl_eur")})
    tickets.sort(key=lambda k: k["t"])
    print("%s : %d tickets dates" % (a.fichier, len(tickets)))
    print("episode fusion %d / portee %d   GUET = %d min%s"
          % (a.fusion, a.portee, a.guet,
             ("   depuis %s" % a.depuis) if a.depuis else ""))
    print("La decision n utilise que les %d premieres minutes." % a.guet)
    print("Le resultat n est mesure que sur les tickets ouverts APRES.")

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

    eps_tous = []
    for act in episodes:
        for e in episodes[act]:
            if not e["petits"]:
                continue
            lim = e["debut"] + dt.timedelta(minutes=a.guet)
            e["avant"] = [k for k in e["petits"] if k["t"] <= lim]
            e["apres"] = [k for k in e["petits"] if k["t"] > lim
                          and dans(k)]
            e["debit"] = len(e["avant"])
            e["taille"] = len(e["petits"])
            e["duree"] = (e["petits"][-1]["t"]
                          - e["debut"]).total_seconds() / 60.0
            if dans(e["petits"][0]):
                eps_tous.append(e)
    if not eps_tous:
        print("Aucun episode sur la periode demandee.")
        return 0

    print()
    print("A. LE DEBIT PRECOCE PREDIT-IL LA TAILLE FINALE ?")
    print("   Sans ca, rien de ce qui suit ne peut marcher.")
    print("   " + "-" * 58)
    croise = collections.Counter()
    for e in eps_tous:
        croise[(cat(e["debit"], DEBITS), cat(e["taille"], TAILLES))] += 1
    for _, _, dn in DEBITS:
        row = [(tn, croise.get((dn, tn), 0)) for _, _, tn in TAILLES]
        tot = sum(n for _, n in row)
        if not tot:
            continue
        det = "   ".join("%s:%-3d" % (tn, n) for tn, n in row)
        print("   %-18s %3d ep.   %s" % (dn, tot, det))

    print()
    print("B. LA REGLE, EVALUEE SUR LES SEULS TICKETS POSTERIEURS")
    print("   Ce que le camp aurait rapporte APRES la minute %d," % a.guet)
    print("   classe par ce qu on savait A la minute %d." % a.guet)
    print("   " + "-" * 58)
    g = collections.defaultdict(list)
    for e in eps_tous:
        for k in e["apres"]:
            g[cat(e["debit"], DEBITS)].append(k["pnl"])
    for _, _, dn in DEBITS:
        ligne(dn, g.get(dn, []))

    print()
    print("C. CE QUE REFUSER AURAIT DONNE")
    print("   " + "-" * 58)
    for seuil_d in (2, 3, 4, 5):
        garde, refuse = [], []
        for e in eps_tous:
            cible = garde if e["debit"] < seuil_d else refuse
            cible.extend(k["pnl"] for k in e["apres"])
        if not garde and not refuse:
            continue
        print("   refuser la suite si debit >= %d :" % seuil_d)
        ligne("     garde", garde, 22)
        ligne("     refuse", refuse, 22)

    print()
    print("D. LE MEME DECOUPAGE SUR LES TICKETS DU GUET")
    print("   Temoin : ces tickets-la ne sont PAS evitables, ils sont")
    print("   pris avant la decision. Si l ecart y est deja present,")
    print("   la regle ne fait que constater un etat, elle ne")
    print("   l anticipe pas.")
    print("   " + "-" * 58)
    g = collections.defaultdict(list)
    for e in eps_tous:
        for k in e["avant"]:
            if dans(k):
                g[cat(e["debit"], DEBITS)].append(k["pnl"])
    for _, _, dn in DEBITS:
        ligne(dn, g.get(dn, []))

    print()
    print("E. CONTROLE -- debit, duree, allumages")
    print("   Un fort debit est-il autre chose qu un episode long ou")
    print("   riche en allumages ? Si duree et allumages montent")
    print("   ensemble avec le debit, on ne sait pas lequel parle.")
    print("   " + "-" * 58)
    for _, _, dn in DEBITS:
        lot = [e for e in eps_tous if cat(e["debit"], DEBITS) == dn]
        if not lot:
            continue
        print("   %-18s %3d ep.  duree med %6.1f min  allumages %4.2f"
              % (dn, len(lot),
                 sorted(e["duree"] for e in lot)[len(lot) // 2],
                 sum(e["n_allum"] for e in lot) / float(len(lot))))

    print()
    print("-" * 62)
    print("  Test ANNONCE avant d etre lance : il ne s ajoute pas au")
    print("  compteur de decoupes du paragraphe 0. Le seuil reste")
    print("  z ~ 2.9, soit ~118 tickets par cellule.")
    print("  `?` = moins de %d tickets." % SEUIL)
    print("  L unite qui compte reste l EPISODE, pas le ticket : les")
    print("  tickets d un meme episode sont correles. Regarder le")
    print("  nombre d episodes de la section A avant de croire un n.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

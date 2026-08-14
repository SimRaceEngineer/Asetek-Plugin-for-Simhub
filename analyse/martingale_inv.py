# -*- coding: utf-8 -*-
"""
martingale_inv.py -- est-ce qu un petit timeframe devient rentable
                     quand un grand vient de s allumer ?

  python martingale_inv.py
  python martingale_inv.py --depuis 2026-08-05

LA QUESTION, TELLE QU ELLE A ETE POSEE

    "Comparer les entrees et les ignitions des x10/20/30 pour savoir
    si, lorsqu un timeframe plus large se declenche, les x01/x02/x05
    deviennent rentables."

    C est une martingale inversee : on ne double pas apres une perte,
    on n autorise le petit que sous couverture d un grand. Si l effet
    existe, "couper x02" devient "ne garder x02 que sous couverture",
    et ce n est pas du tout la meme decision.

CE QUE CE LECTEUR MESURE VRAIMENT -- A LIRE AVANT LES CHIFFRES

    Il mesure une PROXIMITE D ALLUMAGE, pas une presence en position.

    tickets_rails.jsonl porte `entry_ts` mais aucune heure de sortie.
    Impossible, donc, de reconstruire qui etait OUVERT a l instant ou
    un petit entre. Ce que je peux dire, c est : un grand est-il entre
    sur le MEME actif dans les N minutes precedentes.

    C est plus grossier que le plateau releve par X_ENTREE depuis le
    14/08 10:35, qui photographie les positions vivantes. Mais le
    plateau a quelques heures d historique, et ceci en a dix-sept
    jours. Les deux se repondront quand le plateau aura du volume ;
    en attendant, celui-ci repond tout de suite, avec sa limite
    ecrite.

    Consequence a ne pas oublier : un grand entre il y a 55 minutes a
    pu etre ferme depuis 50. Le camp AVEC contient donc des cas ou le
    grand n etait deja plus la. Ce bruit va dans le sens de DILUER
    l effet, pas de l inventer -- si un ecart apparait malgre ca, il
    est plutot sous-estime.

LE SENS COMPTE

    Un x30 SELL qui s allume pendant qu un x02 entre en BUY, ce n est
    pas une couverture, c est une contradiction. La section C separe
    les deux. Si l effet est reel, il doit etre porte par le meme
    sens ; s il est identique dans les deux, ce n est pas une
    couverture qu on mesure mais un simple effet d heure.

SEUILS

    54 tickets pour une comparaison annoncee d avance (sigma = 60,
    edge = 16), ~172 pour une cellule regardee parmi cent. Les
    cellules sous 54 sont marquees `?`. Une moyenne sans son n est un
    chiffre sans unite.

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
FENETRES = (30, 60, 120)

# Bandes DISJOINTES. Le cumule a 60 min contient les 30 premieres
# minutes : il melange une couverture fraiche et une qui vieillit, et
# cache donc l horizon propre a chaque unite. Les bandes le montrent.
BANDES = ((0, 15), (15, 30), (30, 60), (60, 120), (120, 240))
HORS = "au-dela / jamais"
BANDES_NOM = tuple("%d-%d min" % b for b in BANDES) + (HORS,)


def bande(secondes):
    """Range un delai en minutes dans sa bande. None (aucun grand
    avant) et les delais tres longs tombent dans le meme sac : dans
    les deux cas il n y a pas de couverture utile."""
    if secondes is None:
        return HORS
    m = secondes / 60.0
    for lo, hi in BANDES:
        if lo <= m < hi:
            return "%d-%d min" % (lo, hi)
    return HORS


def setup_de(magic):
    """Meme decodeur que x60_onset et matrice_tf : 6 chiffres = arme,
    actif, unite. Les magics a 4 chiffres n ont pas de setup -- ils
    sont comptes a part, affiches et jamais filtres en silence."""
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
    m = sum(v) / n
    print("  %-*s n=%-5d moy %+8.2f  total %+10.2f%s"
          % (large, nom, n, m, sum(v), "" if n >= SEUIL else "  ?"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--depuis", default=None,
                   help="AAAA-MM-JJ : ne garder que les entrees a partir de")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1

    lignes = 0
    tickets = []
    for l in io.open(a.fichier, encoding="utf-8", errors="replace"):
        if not l.strip():
            continue
        lignes += 1
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
    print("%s : %d lignes, %d datees" % (a.fichier, lignes, len(tickets)))

    # ---------------------------------------------------------------
    # A. Inventaire des allumages de grand timeframe
    # ---------------------------------------------------------------
    # Index par actif, trie -- c est lui qu on interroge par bissection
    # pour chaque petit ticket.
    idx = collections.defaultdict(list)
    inv = collections.Counter()
    for k in tickets:
        if k["setup"] in GROS:
            idx[k["actif"]].append((k["t"], k["setup"], k["sens"]))
            inv[(k["actif"], k["setup"])] += 1
    for act in idx:
        idx[act].sort(key=lambda x: x[0])

    print()
    print("A. ALLUMAGES DE GRAND TIMEFRAME DISPONIBLES")
    print("   C est le plafond de ce qu on peut mesurer : le camp AVEC")
    print("   ne peut pas etre plus riche que ca.")
    print("   " + "-" * 56)
    for act in sorted(idx):
        det = "  ".join("x%s:%d" % (s, inv[(act, s)])
                        for s in GROS if inv[(act, s)])
        print("   %-8s %4d allumages   %s" % (act, len(idx[act]), det))
    if not idx:
        print("   AUCUN -- rien a mesurer, le reste du rapport est vide.")
        return 0

    def porteur(k, fenetre):
        """Le grand le plus recent sur le meme actif, s il est dans la
        fenetre. Retourne (setup, sens) ou None."""
        ar = idx.get(k["actif"])
        if not ar:
            return None
        i = bisect.bisect_right(ar, (k["t"], "\xff", "\xff"))
        if i <= 0:
            return None
        tt, st, sn = ar[i - 1]
        if (k["t"] - tt).total_seconds() > fenetre * 60:
            return None
        return (st, sn)

    def delai(k):
        """Secondes ecoulees depuis le dernier grand sur le meme actif,
        sans plafond. None s il n y en a aucun avant."""
        ar = idx.get(k["actif"])
        if not ar:
            return None
        i = bisect.bisect_right(ar, (k["t"], "\xff", "\xff"))
        if i <= 0:
            return None
        return (k["t"] - ar[i - 1][0]).total_seconds()

    def petits(depuis=None):
        for k in tickets:
            if k["setup"] not in PETIT or k["pnl"] is None:
                continue
            if depuis and k["jour"] < depuis:
                continue
            yield k

    # ---------------------------------------------------------------
    # B. Le chiffre principal, sur trois fenetres
    # ---------------------------------------------------------------
    print()
    print("B. AVEC ou SANS couverture, selon la largeur de la fenetre")
    print("   La bonne duree fait partie de la question : si l effet")
    print("   n existe qu a une seule fenetre, c est un artefact.")
    for fen in FENETRES:
        g = collections.defaultdict(list)
        for k in petits(a.depuis):
            camp = "AVEC" if porteur(k, fen) else "SANS"
            g[(k["setup"], camp)].append(k["pnl"])
        print("   " + "-" * 56)
        print("   un grand allume dans les %d minutes precedentes" % fen)
        for s in PETIT:
            for camp in ("SANS", "AVEC"):
                ligne("x%s  %s" % (s, camp), g.get((s, camp), []))

    # ---------------------------------------------------------------
    # B bis. Les BANDES, pas les fenetres cumulees
    # ---------------------------------------------------------------
    # Une fenetre de 60 min contient les 30 premieres : elle MELANGE
    # une couverture fraiche et une couverture qui vieillit. La bande
    # les separe, et c est la seule facon de voir que chaque unite a
    # son horizon propre -- ce que le cumule cache par construction.
    print()
    print("B bis. PAR BANDE  (et non par fenetre cumulee)")
    print("   Le cumule a 60 min contient les 30 premieres minutes :")
    print("   il melange une couverture fraiche et une qui vieillit.")
    print("   La bande les separe. C est ici qu on lit l horizon")
    print("   propre a chaque unite -- et qu une couverture PERIMEE")
    print("   peut se reveler pire que pas de couverture du tout.")
    print("   " + "-" * 56)
    g = collections.defaultdict(list)
    for k in petits(a.depuis):
        d = delai(k)
        g[(k["setup"], bande(d))].append(k["pnl"])
    for s in PETIT:
        for b in BANDES_NOM:
            ligne("x%s  %s" % (s, b), g.get((s, b), []))

    # ---------------------------------------------------------------
    # C. Le sens : couverture ou contradiction
    # ---------------------------------------------------------------
    print()
    print("C. LE SENS COMPTE  (fenetre 60 min)")
    print("   Un grand SELL pendant qu un petit entre en BUY n est pas")
    print("   une couverture. Si AVEC-MEME et AVEC-CONTRE donnent la")
    print("   meme chose, ce n est pas une couverture qu on mesure --")
    print("   c est un effet d heure.")
    print("   " + "-" * 56)
    g = collections.defaultdict(list)
    for k in petits(a.depuis):
        po = porteur(k, 60)
        if not po:
            camp = "SANS"
        elif po[1] and k["sens"] and po[1] == k["sens"]:
            camp = "AVEC-MEME"
        else:
            camp = "AVEC-CONTRE"
        g[(k["setup"], camp)].append(k["pnl"])
    for s in PETIT:
        for camp in ("SANS", "AVEC-MEME", "AVEC-CONTRE"):
            ligne("x%s  %s" % (s, camp), g.get((s, camp), []))

    # ---------------------------------------------------------------
    # D. Quel porteur couvre le mieux
    # ---------------------------------------------------------------
    print()
    print("D. QUEL GRAND COUVRE LE MIEUX  (fenetre 60 min)")
    print("   Repartition du camp AVEC selon le setup du porteur le")
    print("   plus recent. Repond a : faut-il un x60, ou un x30")
    print("   suffit-il ?")
    print("   " + "-" * 56)
    g = collections.defaultdict(list)
    for k in petits(a.depuis):
        po = porteur(k, 60)
        if po:
            g[(k["setup"], po[0])].append(k["pnl"])
    for s in PETIT:
        vu = False
        for gr in GROS:
            v = g.get((s, gr), [])
            if v:
                vu = True
                ligne("x%s  porte par x%s" % (s, gr), v)
        if not vu:
            print("  x%s  aucun porteur dans la fenetre" % s)

    # ---------------------------------------------------------------
    # E. Le meme decoupage sur la periode en cours
    # ---------------------------------------------------------------
    if not a.depuis:
        print()
        print("E. DEPUIS LE 05/08 seulement  (fenetre 60 min)")
        print("   La coupure du 5 aout est celle que la stack retient")
        print("   elle-meme en nommant panel_rails_post0508. Un effet")
        print("   qui n existe qu avant cette date ne sert a rien")
        print("   aujourd hui.")
        print("   " + "-" * 56)
        g = collections.defaultdict(list)
        for k in petits("2026-08-05"):
            camp = "AVEC" if porteur(k, 60) else "SANS"
            g[(k["setup"], camp)].append(k["pnl"])
        for s in PETIT:
            for camp in ("SANS", "AVEC"):
                ligne("x%s  %s" % (s, camp), g.get((s, camp), []))

    print()
    print("-" * 60)
    print("CE QUE CE RAPPORT NE PROUVE PAS")
    print("  Proximite d allumage n est pas presence en position : un")
    print("  grand entre il y a 55 min a pu etre ferme depuis 50. Le")
    print("  camp AVEC contient donc des faux positifs, qui DILUENT")
    print("  l effet. Un ecart qui apparait malgre ca est plutot")
    print("  sous-estime -- mais un ecart absent ne prouve rien.")
    print("  Le plateau de X_ENTREE, lui, photographie les positions")
    print("  vivantes ; il repondra proprement quand il aura du")
    print("  volume. Ceci repond aujourd hui, avec sa limite.")
    print("  `?` = moins de %d tickets. Pour une cellule regardee" % SEUIL)
    print("  parmi cent, il en faut ~172.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

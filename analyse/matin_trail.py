# -*- coding: utf-8 -*-
"""
matin_trail.py -- le matin saigne-t-il, ou est-ce le stop qui manquait ?

  python matin_trail.py
  python matin_trail.py --fichier docs\\rails_trades\\tickets_rails.jsonl

LA QUESTION

    Le creneau 09h-11h perd 10 180 EUR sur onze seances, 10 seances
    rouges sur 11, p = 0.0117. La tentation est de le couper.

    Mais les onze seances sont TOUTES anterieures au patch trail/BE du
    11/08 20h14. Sur cette periode, C14 refusait le cran BE : 149
    tickets sur 343 n ont jamais obtenu le moindre deplacement de stop.

    Or le matin est le moment le plus volatil de la journee. Un stop qui
    ne monte jamais coute mecaniquement plus cher la ou l amplitude est
    la plus grande. Le creneau du matin est donc peut-etre le SYMPTOME
    du trailing casse, pas une pathologie horaire.

    Si c est le cas, couper le matin amputerait 888 tickets pour un
    defaut qu on vient de reparer.

CE QUE CE SCRIPT CROISE

    mfe_trail_events.csv sait, ticket par ticket, si un stop a ete pose
    (retcode 10009). Trois etats, pas deux -- la distinction compte :

        AVEC STOP    le trail a obtenu au moins un deplacement
        SANS STOP    le trail a essaye et n a jamais reussi  <- C14
        HORS TRAIL   le trail ne l a jamais vu (magic exclu) <- US30 207

    Croise avec matin (09h-11h) / reste de la journee.

COMMENT LIRE LE RESULTAT

    Regarde d abord UNE cellule : matin, AVEC STOP.

    * proche de zero  -> la cause est le trailing. Le patch d hier
      corrige deja le probleme et couper le matin serait une erreur.
      On attend des seances post-patch avant de decider quoi que ce
      soit.

    * toujours franchement negative -> la cause est l heure. Le stop
      n y change rien, et la regle d abstention se defend.

    Puis compare l ECART avec/sans stop le matin a ce meme ecart
    l apres-midi. Si le stop vaut beaucoup plus cher le matin, c est
    l interaction qu on cherchait. Si l ecart est le meme partout, le
    matin n a rien de special de ce point de vue.

CE QU IL NE PEUT PAS FAIRE

    Les tickets AVEC et SANS stop ne sont pas comparables toutes choses
    egales : obtenir un stop suppose d avoir d abord bouge dans le bon
    sens. Un ticket AVEC stop a donc, par construction, mieux commence
    qu un ticket SANS. La cellule AVEC STOP est un plafond optimiste,
    pas un contrefactuel. C est ecrit dans la sortie, pour qu on ne
    l oublie pas en lisant le tableau.

    Ce biais joue de la meme facon matin et apres-midi -- c est pour ca
    que la COMPARAISON des deux ecarts vaut mieux que chaque cellule
    prise seule.

LECTURE SEULE. Aucun appel MT5. Aucune ecriture.
"""
import argparse
import csv
import io
import os
import sys

try:
    import matin_seances as M
except ImportError:
    print("KO : matin_seances.py introuvable a cote de ce script.")
    print("Il porte le chargement des tickets et le test du signe.")
    sys.exit(1)

CSV_TRAIL = "mfe_trail_events.csv"
OK = 10009          # TRADE_RETCODE_DONE
MINI = 30
LARG = 78
ETATS = ("AVEC STOP", "SANS STOP", "HORS TRAIL")


def trail(chemin):
    """(vus, avec). Meme lecture que rails_trois.trail."""
    vus, avec = set(), set()
    if not os.path.isfile(chemin):
        return vus, avec
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            tk = str(r.get("ticket") or "").strip()
            if not tk:
                continue
            vus.add(tk)
            try:
                if int(float(r.get("retcode"))) == OK:
                    avec.add(tk)
            except (TypeError, ValueError):
                continue
    return vus, avec


def etat(tk, vus, avec):
    if tk in avec:
        return "AVEC STOP"
    if tk in vus:
        return "SANS STOP"
    return "HORS TRAIL"


def cellule(lot):
    if not lot:
        return None
    p = sum(t["pnl"] for t in lot)
    n = len(lot)
    w = sum(1 for t in lot if t["pnl"] > 0)
    return p / n, n, 100.0 * w / n, p


def ligne(lab, lots):
    out = "  %-12s" % lab
    for lot in lots:
        c = cellule(lot)
        if c is None:
            out += "%22s" % "-"
            continue
        out += "%9.2f %5d %5s%s" % (c[0], c[1], "%.0f%%" % c[2],
                                    " ?" if c[1] < MINI else "  ")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*", default=[M.DEFAUT])
    p.add_argument("--trail", default=CSV_TRAIL)
    p.add_argument("--heures", nargs=2, type=int, default=[9, 11])
    p.add_argument("--depuis", default=None)
    a = p.parse_args()

    h0, h1 = a.heures
    tk = M.charger(a.fichier)
    if a.depuis:
        tk = [t for t in tk if t["jour"] >= a.depuis]

    vus, avec = trail(a.trail)
    if not vus:
        print("KO : %s introuvable ou vide." % a.trail)
        print("Sans lui, impossible de savoir quel ticket a obtenu un stop.")
        return 1

    for t in tk:
        t["etat"] = etat(t["ticket"], vus, avec)
        t["matin"] = h0 <= t["heure"] <= h1

    jours = sorted({t["jour"] for t in tk})
    print("=" * LARG)
    print(" SCALP-EA / LE MATIN CROISE AVEC LE TRAILING")
    print("=" * LARG)
    print("%d tickets, %d seances, du %s au %s"
          % (len(tk), len(jours), jours[0], jours[-1]))
    print("Creneau matin : %02dh-%02dh incluses." % (h0, h1))
    print("Journal trail : %d tickets vus, %d avec au moins un stop pose."
          % (len(vus), len(avec)))
    couv = 100.0 * sum(1 for t in tk if t["ticket"] in vus) / max(1, len(tk))
    print("Couverture du journal sur ce corpus : %.0f%% des tickets." % couv)

    print()
    print("EUR par ticket, nombre de tickets, taux de gain")
    print("  %-12s%22s%22s%22s" % ("", ETATS[0], ETATS[1], ETATS[2]))
    print("-" * LARG)
    lots = {}
    for m in (True, False):
        for e in ETATS:
            lots[(m, e)] = [t for t in tk if t["matin"] is m and t["etat"] == e]
    print(ligne("MATIN", [lots[(True, e)] for e in ETATS]))
    print(ligne("RESTE", [lots[(False, e)] for e in ETATS]))
    print("-" * LARG)
    print("  ? = moins de %d tickets, la cellule ne se lit pas." % MINI)

    # L ecart avec / sans stop, matin contre reste.
    print()
    print("CE QUE LE STOP RAPPORTE, PAR MOMENT DE LA JOURNEE")
    print("-" * LARG)
    ec = {}
    for m, nom in ((True, "matin"), (False, "reste")):
        ca = cellule(lots[(m, "AVEC STOP")])
        cs = cellule(lots[(m, "SANS STOP")])
        if ca and cs and ca[1] >= MINI and cs[1] >= MINI:
            ec[nom] = ca[0] - cs[0]
            print("  %-6s : avec %8.2f   sans %8.2f   ecart %+8.2f EUR/tk"
                  % (nom, ca[0], cs[0], ec[nom]))
        else:
            print("  %-6s : echantillon insuffisant pour comparer." % nom)

    print()
    print("VERDICT")
    print("-" * LARG)
    cm = cellule(lots[(True, "AVEC STOP")])
    if cm is None or cm[1] < MINI:
        print("  Indecidable : %d ticket(s) le matin avec un stop pose."
              % (0 if cm is None else cm[1]))
        print("  Il en faut au moins %d. Rien ne peut etre conclu ici," % MINI)
        print("  et c est en soi un resultat : le matin, le trailing")
        print("  n aboutissait presque jamais.")
    else:
        print("  Matin, tickets AYANT obtenu un stop : %.2f EUR/tk sur %d."
              % (cm[0], cm[1]))
        if cm[0] > -2.0:
            print("  -> proche de l equilibre. La perte du matin est portee")
            print("     par les tickets SANS stop, donc par le defaut que le")
            print("     patch du 11/08 corrige. NE PAS couper le creneau :")
            print("     attendre des seances post-patch.")
        elif cm[0] < -8.0:
            print("  -> franchement negative malgre le stop. L heure est en")
            print("     cause, pas le trailing. La regle d abstention sur")
            print("     %02dh-%02dh se defend." % (h0, h1))
        else:
            print("  -> entre les deux. Le trailing explique une partie de la")
            print("     perte, pas toute. Aucune decision ne se prend sur ce")
            print("     seul chiffre ; il faut les seances post-patch.")

    if "matin" in ec and "reste" in ec:
        print()
        print("  Ecart du stop : %+.2f le matin contre %+.2f le reste."
              % (ec["matin"], ec["reste"]))
        if ec["matin"] > ec["reste"] + 3.0:
            print("  Le stop vaut nettement plus cher le matin -- c est")
            print("  l interaction attendue si la volatilite matinale")
            print("  amplifie le defaut du trailing.")
        elif abs(ec["matin"] - ec["reste"]) <= 3.0:
            print("  Ecarts comparables : le matin n a rien de particulier")
            print("  de ce point de vue. Le trailing coute pareil partout,")
            print("  donc il n explique pas pourquoi CE creneau perd.")
        else:
            print("  Le stop vaut MOINS cher le matin. Contraire a")
            print("  l hypothese : le trailing n est pas le coupable.")

    print()
    print("  Rappel : un ticket AVEC stop a d abord bouge dans le bon sens.")
    print("  Cette cellule est un plafond optimiste, pas un contrefactuel.")
    print("  C est pourquoi la comparaison des deux ecarts vaut mieux que")
    print("  chaque cellule prise seule.")

    # Le signe, seance par seance, restreint aux tickets AVEC stop.
    d = {}
    for t in tk:
        if t["matin"] and t["etat"] == "AVEC STOP":
            e = d.setdefault(t["jour"], [0.0, 0])
            e[0] += t["pnl"]
            e[1] += 1
    seances = [(j, v[0], v[1]) for j, v in d.items()]
    M.bloc("MATIN, TICKETS AVEC STOP -- SEANCE PAR SEANCE", seances)

    print()
    print("=" * LARG)
    return 0


if __name__ == "__main__":
    sys.exit(main())

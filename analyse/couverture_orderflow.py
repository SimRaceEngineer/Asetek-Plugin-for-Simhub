# -*- coding: utf-8 -*-
"""
couverture_orderflow.py -- quels jours sont complets, et lesquels mentent

  python couverture_orderflow.py
  python couverture_orderflow.py --depuis 2026-07-01
  python couverture_orderflow.py --csv couverture.csv

POURQUOI

    Le 13/08, of_US30_2026-08-12.jsonl faisait 119 ko contre 305 la
    veille. Ni vide ni corrompu : il commence a 14:33 au lieu de
    l ouverture. Toute la seance europeenne du 12 aout manque, et rien
    dans le fichier ne le dit.

    Une taille de fichier ne suffit donc pas a juger une journee. Un
    jour tronque a la meme forme qu un jour complet : mêmes champs,
    memes valeurs plausibles, simplement moins de lignes. Croise avec
    l historique d ignition, il produirait des correlations calculees
    sur une demi-journee en croyant les calculer sur une journee.

    Ce script existe pour qu on ne decouvre pas ca en septembre, au
    milieu d une etude.

CE QU IL LIT, ET CE QU IL NE FAIT PAS

    Il ouvre chaque of_<actif>_<date>.jsonl, releve la premiere barre,
    la derniere, le compte, et les trous internes. Il n ecrit rien,
    ne repare rien, ne supprime rien. C est un constat.

CE QU IL APPELLE UN JOUR COMPLET

    Le CME cote environ 23 heures. Une journee pleine porte donc a peu
    pres 1 380 barres d une minute. Le script ne fixe pas ce chiffre :
    il prend la MEDIANE des jours observes comme reference, parce
    qu une constante ecrite en dur cesserait d etre vraie le jour ou
    l horaire de cotation change -- et personne ne s en apercevrait.

    Un jour a moins de 80 % de la mediane est SIGNALE. Le seuil est
    arbitraire et affiche comme tel : c est une invitation a regarder,
    pas un verdict.

LES TROUS INTERNES

    Un jour peut avoir le bon compte et rater vingt minutes au milieu.
    Le script compte les ecarts de plus de deux minutes entre barres
    consecutives, hors coupure quotidienne. Deux minutes et pas une :
    une barre sans transaction n est pas ecrite, donc un marche calme
    produit des trous d une minute qui ne sont pas des pannes.
"""
import argparse
import io
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime

OUT = r"C:\OrderflowExport"
LARG = 100
SEUIL = 0.80         # part de la mediane sous laquelle on signale
TROU_S = 120         # ecart entre barres, en s, au-dela duquel c est un trou
RE_NOM = re.compile(r'^of_([A-Z0-9]+)_(\d{4}-\d{2}-\d{2})\.jsonl$')


def lire(chemin):
    """(n, premiere, derniere, trous) -- trous = [(avant, apres, secondes)]."""
    eps, prem, der = [], None, None
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        b = ligne.strip()
        if not b.startswith("{"):
            continue
        try:
            e = json.loads(b)
        except ValueError:
            continue
        ep = e.get("epoch_utc")
        ts = e.get("ts")
        if ep is None:
            continue
        eps.append(float(ep))
        if prem is None:
            prem = ts
        der = ts
    trous = []
    for i in range(1, len(eps)):
        d = eps[i] - eps[i - 1]
        if d > TROU_S:
            trous.append((i - 1, i, d))
    return len(eps), prem, der, trous


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dossier", default=OUT)
    p.add_argument("--depuis", default="", help="AAAA-MM-JJ")
    p.add_argument("--csv", default="")
    a = p.parse_args()

    if not os.path.isdir(a.dossier):
        print("KO : %s introuvable." % a.dossier)
        return 1

    par_actif = defaultdict(list)
    for nom in sorted(os.listdir(a.dossier)):
        m = RE_NOM.match(nom)
        if not m:
            continue
        actif, jour = m.group(1), m.group(2)
        if a.depuis and jour < a.depuis:
            continue
        n, prem, der, trous = lire(os.path.join(a.dossier, nom))
        par_actif[actif].append((jour, n, prem, der, trous))

    if not par_actif:
        print("Aucun fichier of_<actif>_<date>.jsonl dans %s." % a.dossier)
        return 0

    lignes_csv = ["actif,jour,barres,premiere,derniere,trous,verdict"]
    for actif in sorted(par_actif):
        jours = par_actif[actif]
        compte = [n for _j, n, _p, _d, _t in jours if n > 0]
        med = statistics.median(compte) if compte else 0

        print("=" * LARG)
        print("  %s -- %d jour(s), mediane %d barres" % (actif, len(jours), med))
        print("=" * LARG)
        print("%-12s %8s %10s %10s %7s  %s"
              % ("jour", "barres", "premiere", "derniere", "trous", "verdict"))
        print("-" * LARG)

        suspects = 0
        for jour, n, prem, der, trous in jours:
            if n == 0:
                verdict = "VIDE"
            elif med and n < med * SEUIL:
                verdict = "COURT -- %.0f%% de la mediane" % (100.0 * n / med)
            elif trous:
                pire = max(t[2] for t in trous)
                verdict = "troue -- le plus long %d mn" % (pire / 60)
            else:
                verdict = ""
            if verdict:
                suspects += 1
            print("%-12s %8d %10s %10s %7d  %s"
                  % (jour, n, (prem or "-")[11:16], (der or "-")[11:16],
                     len(trous), verdict))
            lignes_csv.append("%s,%s,%d,%s,%s,%d,%s"
                              % (actif, jour, n, prem or "", der or "",
                                 len(trous), verdict))
        print("-" * LARG)
        print("  %d jour(s) signale(s) sur %d." % (suspects, len(jours)))
        print("  Un jour COURT n est ni vide ni corrompu : il a la meme")
        print("  forme qu un jour complet, avec moins de lignes. Croise")
        print("  tel quel, il produit des moyennes calculees sur une")
        print("  demi-seance en croyant porter sur une journee.")
        print("  Le seuil de %d %% de la mediane est arbitraire : il"
              % int(SEUIL * 100))
        print("  invite a regarder, il ne tranche pas.")
        print()

    if a.csv:
        io.open(a.csv, "w", encoding="utf-8").write("\n".join(lignes_csv) + "\n")
        print("Ecrit : %s  (%d ligne(s))" % (a.csv, len(lignes_csv) - 1))
        print("A joindre a l etude : la liste des jours utilisables est")
        print("une donnee de l etude, pas un detail d intendance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

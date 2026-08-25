#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""sonde_cvd.py -- que valent vraiment les colonnes cvd des snapshots ?

  python sonde_cvd.py
  python sonde_cvd.py --jour 2026-08-24 --motif cvd

LECTEUR SEUL. N ECRIT RIEN, N IMPORTE AUCUN MODULE DE LA STACK.

LES TROIS QUESTIONS, ET POURQUOI ON NE LES DEVINE PAS
-----------------------------------------------------
1. LA CADENCE. Le protocole donne ~190 s a cette source. Si c est
   exact, deux bougies M1 sur trois n ont aucune mesure, et une regle
   qui compare deux bougies consecutives ne peut pas etre evaluee
   dessus. On mesure l ecart REEL entre lignes, on ne le suppose pas.

2. LE SIGNE. `cvd_strength` porte un nom de force, `M1_dom_pct` un nom
   de pourcentage. La regle demandee a besoin d une valeur SIGNEE : un
   delta de -34 doit pouvoir descendre a -35. Une magnitude ne le peut
   pas. On regarde donc combien de valeurs sont negatives dans chaque
   colonne -- une colonne qui n en a aucune n est pas un delta.

3. L ECHELLE. -32, -34, +24 : les ordres de grandeur de la regle. Une
   colonne bornee a 0-100 ne s y prete pas de la meme facon qu une
   colonne en contrats.

Le nom d un champ se lit dans les DONNEES, jamais dans le code qui les
ecrit -- c est la regle nee de l ecart de 494 du 18/08.

LE MODULE csv EST OBLIGATOIRE
    Les lignes font plusieurs centaines de milliers de caracteres et
    certains champs contiennent du texte avec des virgules. Un split
    sur la virgule decalerait les colonnes en silence.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import io
import os
import sys

RACINE = os.path.join("docs", "buddha")
CANDIDATS_TS = ("timestamp", "ts", "time", "datetime", "heure", "date")


def jour_du_jour():
    return datetime.date.today().isoformat()


def trouve_ts(cols):
    """La colonne d horodatage, cherchee et non supposee."""
    bas = [c.strip().lower() for c in cols]
    for exact in CANDIDATS_TS:
        if exact in bas:
            return bas.index(exact)
    for i, c in enumerate(bas):
        if "timestamp" in c or c.endswith(".ts"):
            return i
    return None


def secondes(v):
    v = (v or "").strip()
    if not v:
        return None
    try:                                  # epoch
        f = float(v)
        return f / 1000.0 if f > 1e11 else f
    except ValueError:
        pass
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
              "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            d = datetime.datetime.strptime(v[:26], f)
            return (d - datetime.datetime(1970, 1, 1)).total_seconds()
        except ValueError:
            continue
    return None


def mediane(x):
    if not x:
        return 0.0
    y = sorted(x)
    n = len(y)
    return y[n // 2] if n % 2 else 0.5 * (y[n // 2 - 1] + y[n // 2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=RACINE)
    ap.add_argument("--jour", default=None)
    ap.add_argument("--motif", default="cvd")
    ap.add_argument("--lignes", type=int, default=10,
                    help="lignes montrees en tete et en queue")
    a = ap.parse_args()

    csv.field_size_limit(10000000)
    jour = a.jour or jour_du_jour()
    chemin = os.path.join(a.racine, jour, "snapshots.csv")
    print("=" * 74)
    print("SONDE CVD -- %s" % chemin)
    print("=" * 74)
    if not os.path.isfile(chemin):
        print("introuvable. Journees presentes :")
        try:
            for d in sorted(os.listdir(a.racine))[-8:]:
                print("   %s" % d)
        except OSError:
            print("   (racine illisible)")
        return 1

    with io.open(chemin, encoding="utf-8", errors="replace", newline="") as f:
        lec = csv.reader(f)
        try:
            cols = next(lec)
        except StopIteration:
            print("fichier vide.")
            return 1
        i_ts = trouve_ts(cols)
        vises = [i for i, c in enumerate(cols)
                 if a.motif.lower() in c.strip().lower()]
        print("  %d colonnes, %d portent '%s'" % (len(cols), len(vises),
                                                  a.motif))
        if i_ts is None:
            print("")
            print("REFUS : aucune colonne d horodatage reconnue.")
            print("Les huit premieres colonnes sont :")
            for c in cols[:8]:
                print("   %s" % c)
            print("Dites-moi laquelle porte le temps, je ne devine pas.")
            return 1
        print("  horodatage : colonne %d, '%s'" % (i_ts, cols[i_ts]))
        if not vises:
            print("Aucune colonne ne porte ce motif.")
            return 1

        # Une seule passe. On ne garde que l horodatage et les visees.
        ts, vals, tete, n = [], dict((i, []) for i in vises), [], 0
        for ligne in lec:
            if len(ligne) <= i_ts:
                continue
            n += 1
            s = secondes(ligne[i_ts])
            if s is not None:
                ts.append(s)
            for i in vises:
                if i < len(ligne):
                    v = (ligne[i] or "").strip()
                    if v:
                        try:
                            vals[i].append(float(v))
                        except ValueError:
                            pass
            if len(tete) < a.lignes:
                tete.append((ligne[i_ts],
                             [(cols[i], ligne[i] if i < len(ligne) else "")
                              for i in vises[:6]]))

    print("  %d ligne(s) de donnees" % n)

    print("")
    print("-" * 74)
    print("LA CADENCE -- mesuree, pas supposee")
    print("-" * 74)
    ecarts = [b - a2 for a2, b in zip(ts, ts[1:]) if 0 < b - a2 < 86400]
    if not ecarts:
        print("  impossible : moins de deux horodatages lisibles.")
    else:
        med = mediane(ecarts)
        sous60 = sum(1 for e in ecarts if e <= 60)
        print("  mediane %.0f s   min %.0f   max %.0f   sur %d intervalles"
              % (med, min(ecarts), max(ecarts), len(ecarts)))
        print("  %d (%.0f %%) sont a 60 s ou moins"
              % (sous60, 100.0 * sous60 / len(ecarts)))
        print("")
        if med > 90:
            print("  A cette cadence, une regle qui compare DEUX bougies M1")
            print("  consecutives n est pas evaluable sur cette source :")
            print("  il manque en moyenne %.0f minute(s) entre deux mesures."
                  % (med / 60.0))
        else:
            print("  Cadence compatible avec une lecture par minute.")

    print("")
    print("-" * 74)
    print("SIGNE ET ECHELLE -- une magnitude n est pas un delta")
    print("-" * 74)
    print("  %-58s %6s %6s %8s %8s" % ("COLONNE", "n", "<0", "min", "max"))
    for i in vises:
        v = vals[i]
        if not v:
            print("  %-58s %6d %6s %8s %8s" % (cols[i][:58], 0, "-", "-", "-"))
            continue
        neg = sum(1 for x in v if x < 0)
        print("  %-58s %6d %5.0f%% %8.2f %8.2f"
              % (cols[i][:58], len(v), 100.0 * neg / len(v),
                 min(v), max(v)))
    print("")
    print("  Une colonne dont la part de negatifs vaut 0 % est une")
    print("  magnitude : la regle du delta croissant ne peut pas s y")
    print("  appliquer telle quelle.")

    print("")
    print("-" * 74)
    print("LES PREMIERES LIGNES")
    print("-" * 74)
    for t, paires in tete:
        print("  %s" % t)
        for nom, v in paires:
            print("      %-56s %s" % (nom[:56], v))
    return 0


if __name__ == "__main__":
    sys.exit(main())

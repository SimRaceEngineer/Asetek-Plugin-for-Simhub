#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""corrige_etat_papier.py -- que papier_tf ecrive son etat a chaque tour.

LE POINT
--------
Dans la boucle de papier_tf.py :

    if time.time() >= prochaine_veille:
        prochaine_veille = time.time() + VEILLE_MIN * 60
        ecrire_trade({"quoi": "VEILLE", ...})
        ecrire_etat(ouvertes)         <-- 12 espaces
    time.sleep(pas)                   <-- 8 espaces

`ecrire_etat` est enferme dans le bloc de veille. La boucle tourne
toutes les 20 secondes (PAS = 20) et ouvre ou ferme des cellules a ce
rythme, mais l etat n est sauvegarde que toutes les dix minutes
(VEILLE_MIN = 10).

Ce n etait pas un defaut : le commentaire ligne 106 dit a quoi sert ce
fichier -- "les positions ouvertes, pour survivre". Dix minutes
suffisent pour se remettre d un redemarrage.

Elles ne suffisent pas pour qu un executeur copie les decisions du
papier au moment ou il les prend.

LE CORRECTIF
------------
Desindenter cette seule ligne de quatre espaces. Elle sort du bloc de
veille et rejoint le corps de la boucle : l etat est alors ecrit a
chaque tour, donc aussi frais que la connaissance qu en a le papier.

Rien d autre ne change. Aucune ligne ajoutee ni supprimee, aucune
regle, aucun seuil, aucun calcul. Une ligne deplacee de quatre
colonnes.

Cout : 27 Ko reecrits toutes les 20 s, par fichier temporaire puis
renommage -- `ecrire_etat` etait deja atomique.

Effet secondaire souhaitable : le fichier remplit enfin correctement le
role pour lequel il a ete ecrit. Aujourd hui, un plantage fait perdre
jusqu a dix minutes de positions.

Le module tourne dans le processus de papier_tf : la correction ne
prend effet qu au prochain demarrage de la boucle papers.

USAGE
-----
    python corrige_etat_papier.py                 <- simulation
    python corrige_etat_papier.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\papier_tf.py"
SUFFIXE_BAK = ".bak_etat"

# On ne code aucune indentation en dur : on cherche la ligne
# `ecrire_etat(ouvertes)` immediatement suivie de `time.sleep(pas)`, et
# on aligne la premiere sur la seconde. C est l operation voulue, dite
# sans supposer un decompte d espaces qu on ne peut pas verifier.
APPEL = "ecrire_etat(ouvertes)"
SUIVANTE = "time.sleep(pas)"


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def indent(ligne):
    return len(ligne) - len(ligne.lstrip(" "))


def reperer(lignes):
    """Indices (0-based) des lignes `ecrire_etat(ouvertes)` suivies de
    `time.sleep(pas)`. Renvoie aussi si elles sont deja alignees."""
    trouves = []
    for i in range(len(lignes) - 1):
        if lignes[i].strip() != APPEL:
            continue
        j = i + 1
        while j < len(lignes) and not lignes[j].strip():
            j += 1
        if j >= len(lignes) or lignes[j].strip() != SUIVANTE:
            continue
        trouves.append((i, j, indent(lignes[i]), indent(lignes[j])))
    return trouves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    args = ap.parse_args()

    print("=" * 66)
    print("corrige_etat_papier -- %s" % ("APPLIQUER" if args.appliquer
                                         else "SIMULATION"))
    print("=" * 66)

    if not os.path.isfile(args.cible):
        print("introuvable : %s" % args.cible)
        return 2

    source = lire(args.cible)
    lignes = source.split("\n")
    print("cible : %s" % args.cible)
    print("        %d lignes" % len(lignes))

    trouves = reperer(lignes)
    if not trouves:
        print("")
        print("REFUS : aucune ligne `%s` suivie de `%s`." % (APPEL, SUIVANTE))
        print("Le fichier a change depuis la lecture du 25/08. Je ne")
        print("touche pas a l aveugle a une boucle de trading.")
        return 1
    if len(trouves) > 1:
        print("")
        print("REFUS : %d occurrences, ambigu :" % len(trouves))
        for i, j, ia, ib in trouves:
            print("   lignes %d et %d" % (i + 1, j + 1))
        return 1

    i, j, ind_appel, ind_suiv = trouves[0]
    print("        ligne %d, indentee de %d ; ligne %d, indentee de %d"
          % (i + 1, ind_appel, j + 1, ind_suiv))

    if ind_appel == ind_suiv:
        print("")
        print("Deja corrige : ecrire_etat est au niveau de la boucle.")
        return 0
    if ind_appel < ind_suiv:
        print("")
        print("REFUS : ecrire_etat est MOINS indente que time.sleep.")
        print("Ce n est pas la situation decrite. Je m arrete.")
        return 1

    print("")
    print("avant :")
    print("   |%s|" % lignes[i])
    print("   |%s|" % lignes[j])
    print("apres :")
    print("   |%s%s|" % (" " * ind_suiv, APPEL))
    print("   |%s|" % lignes[j])
    print("")
    print("        soit %d espaces de moins, et rien d autre."
          % (ind_appel - ind_suiv))

    if not args.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer.")
        return 0

    bak = args.cible + SUFFIXE_BAK
    if not os.path.exists(bak):
        shutil.copy2(args.cible, bak)
        print("")
        print("sauvegarde : %s" % bak)
    else:
        print("")
        print("sauvegarde deja presente : %s (conservee)" % bak)

    lignes[i] = " " * ind_suiv + APPEL
    with io.open(args.cible, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lignes))
    print("ecrit : %s" % args.cible)

    relu = lire(args.cible)
    verif = reperer(relu.split("\n"))
    if len(verif) != 1 or verif[0][2] != verif[0][3]:
        print("relu   : CORRECTIF ABSENT -- restaurer %s" % bak)
        return 1
    print("relu   : correctif present.")
    try:
        compile(relu, args.cible, "exec")
        print("syntaxe: le fichier compile.")
    except SyntaxError as e:
        print("syntaxe: ERREUR ligne %s -- restaurer %s" % (e.lineno, bak))
        return 1

    print("")
    print("-" * 66)
    print("La boucle papers doit etre relancee pour que ce soit effectif.")
    print("Tant qu elle tourne, elle execute l ancienne version chargee en")
    print("memoire, et etat.json restera vieux de dix minutes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

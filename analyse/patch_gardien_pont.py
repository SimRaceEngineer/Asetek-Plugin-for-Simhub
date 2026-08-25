#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_gardien_pont.py -- confier le pont des miroirs au gardien.

POURQUOI LE GARDIEN ET PAS LE .BAT
----------------------------------
START_TRADING_STACK_V3.bat lance une fois et n y revient pas. Si le pont
meurt a 15h, personne ne s en apercoit avant le lendemain.

Le gardien, lui, verifie ses observateurs a 7h50 et 14h20, relance ce
qui est tombe, redirige les sorties vers logs\\, et respecte la fenetre
lundi 07:50 -> vendredi 20:00. Le pont y sera surveille, pas seulement
lance.

LA DIFFICULTE, ET COMMENT ELLE SE REGLE
---------------------------------------
Le pont est fait de DEUX processus qui partagent le meme fichier :

    pont_miroirs.py --lecteur     lit le compte du moteur
    pont_miroirs.py --envoyeur    ecrit sur le compte dedie

Un gardien qui identifierait ses observateurs par le nom du script
croirait qu un seul suffit, et laisserait la copie a moitie ouverte --
exactement l oubli qu on cherche a rendre impossible.

Celui-ci cherche ses motifs dans la LIGNE DE COMMANDE complete
(ForEach-Object sur $_.CommandLine, ligne ~104). Les deux motifs
`pont_miroirs.py --lecteur` et `pont_miroirs.py --envoyeur` sont donc
distincts, et le gardien saura qu il lui en faut deux.

CE QUE FAIT CE SCRIPT
---------------------
Il insere deux entrees dans OBSERVATEURS, avant la parenthese fermante.
Rien d autre n est touche : ni les observateurs existants, ni le miroir,
ni la fenetre, ni le lanceur.

Il ne code aucune indentation en dur : il repere `OBSERVATEURS = (` puis
la premiere ligne reduite a `)` en colonne zero, et s aligne sur ce
qu il trouve.

Le gardien tourne peut-etre deja : la modification ne prendra effet qu a
son prochain demarrage.

USAGE
-----
    python patch_gardien_pont.py                 <- simulation
    python patch_gardien_pont.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\gardien_stack.py"
SUFFIXE_BAK = ".bak_pont"
DEBUT = "OBSERVATEURS = ("
MARQUEUR = "pont_miroirs.py"
COMPTE = "182109"

AJOUT = '''    # 2026-08-25 : le pont des miroirs paper. Deux processus, parce
    # qu un processus Python ne parle qu a UN terminal MT5 -- le lecteur
    # lit le compte du moteur, l envoyeur ecrit sur le compte dedie.
    # Les deux motifs se distinguent par la LIGNE DE COMMANDE et non par
    # le nom du fichier : sans cela le gardien croirait qu un seul
    # processus suffit, et la copie resterait a moitie ouverte.
    ("pont lecteur", "pont_miroirs.py --lecteur",
     ("-u", "pont_miroirs.py", "--lecteur")),
    ("pont envoyeur", "pont_miroirs.py --envoyeur",
     ("-u", "pont_miroirs.py", "--envoyeur", "--compte", "%s", "--reel")),
''' % COMPTE


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def reperer(lignes):
    """Renvoie (i_debut, i_fin) : la ligne `OBSERVATEURS = (` et la
    parenthese fermante qui lui correspond, en colonne zero."""
    debuts = [i for i, l in enumerate(lignes) if l.strip() == DEBUT]
    if len(debuts) != 1:
        return None, len(debuts)
    i = debuts[0]
    for j in range(i + 1, len(lignes)):
        if lignes[j].rstrip() == ")":
            return (i, j), 1
    return None, 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    args = ap.parse_args()

    print("=" * 68)
    print("patch_gardien_pont -- %s" % ("APPLIQUER" if args.appliquer
                                        else "SIMULATION"))
    print("=" * 68)

    if not os.path.isfile(args.cible):
        print("introuvable : %s" % args.cible)
        return 2

    source = lire(args.cible)
    lignes = source.split("\n")
    print("cible : %s" % args.cible)
    print("        %d lignes" % len(lignes))

    if MARQUEUR in source:
        print("")
        print("Deja fait : %s figure deja dans le gardien." % MARQUEUR)
        return 0

    bornes, combien = reperer(lignes)
    if bornes is None:
        print("")
        if combien != 1:
            print("REFUS : `%s` trouve %d fois." % (DEBUT, combien))
        else:
            print("REFUS : parenthese fermante de OBSERVATEURS introuvable.")
        print("Le fichier a change. Je ne modifie pas a l aveugle le")
        print("gardien d une stack qui trade.")
        return 1

    i, j = bornes
    print("        OBSERVATEURS : lignes %d a %d" % (i + 1, j + 1))
    print("")
    print("observateurs actuels :")
    for k in range(i + 1, j):
        t = lignes[k].strip()
        if t.startswith('("'):
            print("   %s" % t[:66])
    print("")
    print("a ajouter :")
    print("   (\"pont lecteur\",  \"pont_miroirs.py --lecteur\")")
    print("   (\"pont envoyeur\", \"pont_miroirs.py --envoyeur\", compte %s, --reel)"
          % COMPTE)

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

    nouvelles = lignes[:j] + AJOUT.rstrip("\n").split("\n") + lignes[j:]
    with io.open(args.cible, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(nouvelles))
    print("ecrit : %s" % args.cible)

    relu = lire(args.cible)
    if relu.count("pont_miroirs.py --lecteur") != 1 \
            or relu.count("pont_miroirs.py --envoyeur") != 1:
        print("relu   : AJOUT ABSENT OU EN DOUBLE -- restaurer %s" % bak)
        return 1
    print("relu   : les deux entrees sont presentes.")
    try:
        compile(relu, args.cible, "exec")
        print("syntaxe: le fichier compile.")
    except SyntaxError as e:
        print("syntaxe: ERREUR ligne %s -- restaurer %s" % (e.lineno, bak))
        return 1

    print("")
    print("-" * 68)
    print("Le gardien doit etre relance pour en tenir compte. Tant qu il")
    print("tourne, il execute la liste chargee en memoire.")
    print("Le pont lance a la main aujourd hui n est pas concerne : il")
    print("continue. Ne pas le relancer maintenant.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

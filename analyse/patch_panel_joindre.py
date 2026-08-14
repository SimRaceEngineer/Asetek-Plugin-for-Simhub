# -*- coding: utf-8 -*-
"""
patch_panel_joindre.py -- le panneau quadruple inclut le panneau x60

  python patch_panel_joindre.py --essai
  python patch_panel_joindre.py

POURQUOI

    Un tableau que l utilisateur ne voit pas ne sert a rien. Le
    panneau quadruple ecrit dans panels/panel_quadruple.txt ; celui
    qu on ouvre par habitude est panels/panel_x60_onset.txt. Resultat
    : dix sections nouvelles, invisibles.

    Deux facons de corriger. Patcher x60_onset pour y ajouter les
    tableaux -- mais c est le COLLECTEUR du gel, et un patch rate sur
    lui coute les donnees qu on paie quinze jours pour obtenir.
    Ou recopier sa sortie en tete du panneau quadruple : lui garde
    son fichier intact, et le quadruple devient le sur-ensemble.

    C est la seconde. Un seul fichier a ouvrir, contenu identique
    plus le reste, zero risque pour le collecteur.

LE PIEGE, ET SA GARDE

    Les deux panneaux sont produits par des processus DIFFERENTS, a
    des rythmes differents. Si x60_onset decroche, sa partie se fige
    pendant que la suite continue de vivre -- et les deux moities du
    meme fichier ne parleraient plus du meme instant.

    Le patch affiche donc l age du panneau inclus, et AVERTIT au-dela
    d une heure. Un fichier introuvable est signale, jamais tu.

  --joindre ""   pour revenir a l ancien comportement.

TROIS ANCRES, chacune verifiee unique. IDEMPOTENT. Sauvegarde
horodatee. ast.parse, puis controle sur l arbre.

GENERE PAR DIFFERENCE : le script producteur a verifie que les trois
substitutions reproduisent EXACTEMENT le fichier teste.

Ce patch ne modifie qu un LECTEUR. Aucun ordre, aucun collecteur.
"""
import argparse
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "panel_quadruple.py"
MARQUEUR = "--joindre"

A1 = 'SORTIE = os.path.join("panels", "panel_quadruple.txt")\n'
N1 = 'SORTIE = os.path.join("panels", "panel_quadruple.txt")\nJOINDRE = os.path.join("panels", "panel_x60_onset.txt")\n'

A2 = '    p.add_argument("--depuis", default=None)\n    a = p.parse_args()\n'
N2 = '    p.add_argument("--depuis", default=None)\n    p.add_argument("--joindre", default=JOINDRE,\n                   help="panneau a inclure en tete ; \\"\\" pour aucun")\n    a = p.parse_args()\n'

A3 = '    dis("=" * LARG)\n    dis("PANNEAU QUADRUPLE  x10 / x20 / x30 / x60")\n'
N3 = '    # Le panneau x60 est INCLUS tel quel, en tete. Un tableau que\n    # l utilisateur ne voit pas ne sert a rien : il ouvre le panneau\n    # dont il a l habitude. Plutot que de patcher le collecteur pour\n    # y ajouter des sections -- ce qui risquerait les donnees du gel\n    # pour de la mise en page -- on recopie sa sortie ici. Lui garde\n    # son fichier, intact, et ce panneau devient le sur-ensemble.\n    if a.joindre and os.path.isfile(a.joindre):\n        age = (dt.datetime.now()\n               - dt.datetime.fromtimestamp(os.path.getmtime(a.joindre)))\n        mn = age.total_seconds() / 60.0\n        for l in io.open(a.joindre, encoding="utf-8",\n                         errors="replace").read().split("\\n"):\n            dis(l.rstrip())\n        dis()\n        dis("=" * LARG)\n        dis("  ci-dessus : %s, ecrit il y a %.0f min" % (a.joindre, mn))\n        if mn > 60:\n            dis("  ATTENTION : ce panneau n a pas ete regenere depuis")\n            dis("  plus d une heure. Ses chiffres peuvent etre perimes")\n            dis("  alors que ceux qui suivent sont a jour -- ne pas les")\n            dis("  comparer sans regarder les deux horodatages.")\n        dis("  ci-dessous : les quatre unites cote a cote")\n        dis("=" * LARG)\n    elif a.joindre:\n        dis("  (%s introuvable -- panneau x60 non inclus)" % a.joindre)\n        dis()\n\n    dis("=" * LARG)\n    dis("PANNEAU QUADRUPLE  x10 / x20 / x30 / x60")\n'

ANCRES = ((A1, N1, "la constante de sortie"),
          (A2, N2, "les arguments"),
          (A3, N3, "le titre du panneau"))

INTOUCHABLES = ("def main(", "def setup_de(", "def table4(",
                "def cellule(", "_L = []", "--boucle", "SEANCE US")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    neuf = src
    for anc, nouv, nom in ANCRES:
        n = neuf.count(anc)
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1
        neuf = neuf.replace(anc, nouv, 1)
    print("Trois ancres, chacune unique.")

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    for t in INTOUCHABLES:
        if src.count(t) != neuf.count(t):
            print("KO : %s n apparait plus le meme nombre de fois." % t)
            print("Rien n a ete ecrit.")
            return 1
    print("Intacts : main, setup_de, table4, cellule, _L, --boucle.")

    dedans = False
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.FunctionDef) and noeud.name == "main":
            if "joindre" in ast.dump(noeud):
                dedans = True
            break
    if not dedans:
        print("KO : l inclusion n est pas dans main().")
        print("Rien n a ete ecrit.")
        return 1
    print("Arbre verifie : l inclusion est dans main().")

    print()
    print("panel_quadruple.txt contiendra desormais :")
    print("  1. le panneau x60 tel quel, en tete")
    print("  2. l age de ce panneau, avec avertissement au-dela d 1 h")
    print("  3. les dix sections a quatre entrees")
    print()
    print("panel_x60_onset.txt n est PAS modifie -- il est recopie.")
    print("Le service du gardien reprendra le nouveau contenu a sa")
    print("prochaine passe -- rien a relancer a la main.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

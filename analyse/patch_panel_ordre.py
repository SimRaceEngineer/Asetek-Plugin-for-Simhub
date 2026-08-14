# -*- coding: utf-8 -*-
"""
patch_panel_ordre.py -- les dix sections AVANT le panneau x60

  python patch_panel_ordre.py --essai
  python patch_panel_ordre.py

POURQUOI

    patch_panel_joindre a mis le panneau x60 en TETE et les dix
    sections quadruples en dessous. Le panneau x60 fait ~250 lignes :
    il faut donc scroller un ecran et demi avant d atteindre ce qui
    est neuf.

    Resultat concret : l utilisateur a ouvert l onglet, a lu le haut,
    et a dit "je ne vois toujours rien" -- deux fois. Le contenu
    etait la, invisible par sa position.

    Ce patch inverse : les dix sections d abord, le panneau x60 en
    queue. Il reste accessible -- le retirer le rendrait introuvable,
    puisque son onglet sert desormais le quadruple.

CE QUI NE CHANGE PAS

    Rien d autre. Meme contenu, meme calcul, meme fichier de sortie.
    Le bloc est deplace, pas reecrit -- et les mentions "ci-dessus" et
    "ci-dessous" sont echangees pour rester justes.

DEUX ANCRES, chacune verifiee unique. IDEMPOTENT. Sauvegarde
horodatee. ast.parse, puis controle que le bloc d inclusion existe
toujours UNE fois et qu il est bien apres les sections.

GENERE PAR DIFFERENCE : le script producteur a verifie que les deux
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
MARQUEUR = "INCLUS tel quel, EN QUEUE"

A1 = '    # Le panneau x60 est INCLUS tel quel, en tete. Un tableau que\n    # l utilisateur ne voit pas ne sert a rien : il ouvre le panneau\n    # dont il a l habitude. Plutot que de patcher le collecteur pour\n    # y ajouter des sections -- ce qui risquerait les donnees du gel\n    # pour de la mise en page -- on recopie sa sortie ici. Lui garde\n    # son fichier, intact, et ce panneau devient le sur-ensemble.\n    if a.joindre and os.path.isfile(a.joindre):\n        age = (dt.datetime.now()\n               - dt.datetime.fromtimestamp(os.path.getmtime(a.joindre)))\n        mn = age.total_seconds() / 60.0\n        for l in io.open(a.joindre, encoding="utf-8",\n                         errors="replace").read().split("\\n"):\n            dis(l.rstrip())\n        dis()\n        dis("=" * LARG)\n        dis("  ci-dessus : %s, ecrit il y a %.0f min" % (a.joindre, mn))\n        if mn > 60:\n            dis("  ATTENTION : ce panneau n a pas ete regenere depuis")\n            dis("  plus d une heure. Ses chiffres peuvent etre perimes")\n            dis("  alors que ceux qui suivent sont a jour -- ne pas les")\n            dis("  comparer sans regarder les deux horodatages.")\n        dis("  ci-dessous : les quatre unites cote a cote")\n        dis("=" * LARG)\n    elif a.joindre:\n        dis("  (%s introuvable -- panneau x60 non inclus)" % a.joindre)\n        dis()\n\n'
N1 = ''

A2 = '    txt = "\\n".join(_L) + "\\n"\n'
N2 = '    # Le panneau x60 est INCLUS tel quel, EN QUEUE. Un tableau que\n    # l utilisateur ne voit pas ne sert a rien : il ouvre le panneau\n    # dont il a l habitude. Plutot que de patcher le collecteur pour\n    # y ajouter des sections -- ce qui risquerait les donnees du gel\n    # pour de la mise en page -- on recopie sa sortie ici. Lui garde\n    # son fichier, intact, et ce panneau devient le sur-ensemble.\n    if a.joindre and os.path.isfile(a.joindre):\n        age = (dt.datetime.now()\n               - dt.datetime.fromtimestamp(os.path.getmtime(a.joindre)))\n        mn = age.total_seconds() / 60.0\n        dis()\n        dis("=" * LARG)\n        dis("  ci-dessus : les quatre unites cote a cote")\n        if mn > 60:\n            dis("  ATTENTION : ce panneau n a pas ete regenere depuis")\n            dis("  plus d une heure. Ses chiffres peuvent etre perimes")\n            dis("  alors que ceux qui suivent sont a jour -- ne pas les")\n            dis("  comparer sans regarder les deux horodatages.")\n        dis("  ci-dessous : %s, ecrit il y a %.0f min" % (a.joindre, mn))\n        for l in io.open(a.joindre, encoding="utf-8",\n                         errors="replace").read().split("\\n"):\n            dis(l.rstrip())\n        dis("=" * LARG)\n    elif a.joindre:\n        dis("  (%s introuvable -- panneau x60 non inclus)" % a.joindre)\n        dis()\n\n    txt = "\\n".join(_L) + "\\n"\n'

ANCRES = ((A1, N1, "le bloc d inclusion en tete"),
          (A2, N2, "l assemblage final"))

INTOUCHABLES = ("def main(", "def setup_de(", "def table4(",
                "def cellule(", "_L = []", "--boucle", "SEANCE US",
                "LES EPISODES", "a.joindre")


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
    print("Deux ancres, chacune unique.")

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

    # Le bloc doit exister UNE fois et se trouver APRES les
    # sections : deplace au mauvais endroit, il compilerait et
    # l ordre serait inchange sans que rien ne le signale.
    if neuf.count("a.joindre and os.path.isfile") != 1:
        print("KO : le bloc d inclusion n existe plus une seule fois.")
        print("Rien n a ete ecrit.")
        return 1
    if neuf.index("LES EPISODES") > neuf.index("a.joindre and os.path"):
        print("KO : le bloc d inclusion est encore AVANT les sections.")
        print("Rien n a ete ecrit.")
        return 1
    print("Ordre verifie : les sections, puis le panneau x60.")

    print()
    print("panel_quadruple.txt commencera desormais par les dix")
    print("sections a quatre entrees, et se terminera par le panneau")
    print("x60 recopie -- au lieu de l inverse.")
    print()
    print("panel_x60_onset.txt n est toujours PAS modifie.")
    print("ATTENTION -- le service NE reprendra PAS ce changement")
    print("tout seul. Le mode --boucle appelle main() dans le MEME")
    print("processus : il ne relit jamais son propre fichier. Le")
    print("gardien, lui, ne relance que ce qui est MORT.")
    print()
    print("Il faut donc arreter le processus panel_quadruple : le")
    print("gardien le relancera dans les 5 min avec le code neuf.")
    print("C est un lecteur, l arreter ne coute rien.")

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

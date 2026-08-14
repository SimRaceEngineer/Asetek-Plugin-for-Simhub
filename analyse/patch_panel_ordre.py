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

    Resultat concret : l onglet a ete ouvert, le haut lu, et la
    reponse a ete "je ne vois toujours rien" -- deux fois. Le contenu
    etait la, invisible par sa position.

    Ce patch inverse. Le panneau x60 reste, en queue : le retirer le
    rendrait introuvable, puisque son onglet sert desormais le
    quadruple.

POURQUOI CE PATCH NE RECOPIE PAS LE BLOC

    Le bloc a deplacer fait 1 500 caracteres. L embarquer en litteral
    echappe, c est 1 500 caracteres a recopier sans faute entre ici et
    le VPS -- et une faute donnerait une ancre introuvable, ou pire,
    un bloc silencieusement different de celui qui a ete teste.

    Le patch le DECOUPE donc dans le fichier cible, entre deux
    reperes, et le recolle ailleurs. Il ne connait pas son contenu et
    n a pas besoin de le connaitre : c est le fichier lui-meme qui
    fait foi.

CE QUI NE CHANGE PAS

    Meme contenu, meme calcul, meme fichier de sortie. Le bloc est
    deplace, pas reecrit. Seules les mentions "ci-dessus" et
    "ci-dessous" sont echangees, sans quoi elles mentiraient.

IDEMPOTENT. Sauvegarde horodatee. ast.parse, puis quatre controles :
le bloc existe une seule fois, il finit apres les sections, le
fichier ne perd aucune ligne, et rien d autre n a bouge.

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
DEBUT = "    # Le panneau x60 est INCLUS tel quel"
FIN = '    dis("=" * LARG)\n    dis("PANNEAU QUADRUPLE'
POSE = '    txt = "\\n".join(_L) + "\\n"\n'
MARQUEUR = "EN QUEUE"

A_HAUT = 'dis("  ci-dessus : %s, ecrit il y a %.0f min" % (a.joindre, mn))'
N_HAUT = 'dis("  ci-dessus : les quatre unites cote a cote")'
A_BAS = 'dis("  ci-dessous : les quatre unites cote a cote")'

LECT = '        for l in io.open(a.joindre'
SEP = '        dis()\n        dis("=" * LARG)\n        dis("  ci-'
SEPF = '        dis("=" * LARG)\n    elif a.joindre:'
FSEP = '        dis("=" * LARG)\n'
N_BAS = 'dis("  ci-dessous : %s, ecrit il y a %.0f min" % (a.joindre, mn))'


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
    n_lignes = src.count("\n")
    print("%s : %d lignes" % (a.fichier, n_lignes + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    for t, nom in ((DEBUT, "le debut du bloc"), (FIN, "la fin du bloc"),
                   (POSE, "l assemblage final"),
                   (A_HAUT, "la mention ci-dessus"),
                   (A_BAS, "la mention ci-dessous")):
        if src.count(t) != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1."
                  % (src.count(t), nom))
            print("Rien n a ete ecrit.")
            return 1
    if src.index(DEBUT) > src.index(FIN):
        print("KO : le bloc est deja apres l en-tete -- structure")
        print("     inattendue, on ne touche a rien.")
        print("Rien n a ete ecrit.")
        return 1
    print("Bloc localise, reperes uniques.")

    # Decoupe : on ne connait pas le contenu du bloc et on n en a pas
    # besoin. C est le fichier cible qui fait foi, pas une copie.
    d, f = src.index(DEBUT), src.index(FIN)
    bloc = src[d:f]
    reste = src[:d] + src[f:]

    bloc = (bloc.replace("INCLUS tel quel, en tete", "INCLUS tel quel, EN QUEUE")
                .replace(A_HAUT, "@@HAUT@@").replace(A_BAS, N_BAS)
                .replace("@@HAUT@@", N_HAUT))

    # L INTERIEUR du bloc doit s inverser aussi. A l origine il lit le
    # fichier PUIS ecrit le separateur ; une fois le bloc passe en
    # queue, ce separateur se retrouverait apres le contenu qu il est
    # cense annoncer, et ses libelles designeraient le contraire de ce
    # qu ils disent. On remonte donc le separateur avant la lecture.
    for t, nom in ((LECT, "la boucle de lecture"),
                   (SEP, "le debut du separateur"),
                   (SEPF, "la fin du separateur")):
        if bloc.count(t) != 1:
            print("KO : %d occurrence(s) de %s dans le bloc, il en"
                  " faut 1." % (bloc.count(t), nom))
            print("Rien n a ete ecrit.")
            return 1
    i = bloc.index(LECT)
    j = bloc.index(SEP)
    # On coupe a la FIN de la ligne du separateur, pas apres le
    # `elif` : l emporter reviendrait a poser la boucle de
    # lecture derriere lui, hors de son bloc.
    k = bloc.index(SEPF) + len(FSEP)
    if not i < j < k:
        print("KO : lecture et separateur ne sont pas dans l ordre")
        print("     attendu -- on ne reorganise rien a l aveugle.")
        print("Rien n a ete ecrit.")
        return 1
    bloc = bloc[:i] + bloc[j:k] + bloc[i:j] + bloc[k:]
    neuf = reste.replace(POSE, bloc + POSE, 1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # Un deplacement ne cree ni ne detruit de lignes. Si le compte
    # bouge, c est qu on a coupe autre chose que ce qu on croyait.
    if neuf.count("\n") != n_lignes:
        print("KO : le fichier passe de %d a %d lignes -- un"
              " deplacement n en change aucune."
              % (n_lignes, neuf.count("\n")))
        print("Rien n a ete ecrit.")
        return 1
    if neuf.count("a.joindre and os.path.isfile") != 1:
        print("KO : le bloc d inclusion n existe plus une seule fois.")
        print("Rien n a ete ecrit.")
        return 1
    if neuf.index("LES EPISODES") > neuf.index("a.joindre and os.path"):
        print("KO : le bloc est encore AVANT les sections.")
        print("Rien n a ete ecrit.")
        return 1
    for t in ("def main(", "def table4(", "--boucle", "SEANCE US",
              "LES EPISODES", "LA RICHESSE"):
        if src.count(t) != neuf.count(t):
            print("KO : %s n apparait plus le meme nombre de fois." % t)
            print("Rien n a ete ecrit.")
            return 1
    print("Verifie : meme nombre de lignes, bloc unique, place APRES")
    print("les sections, et rien d autre n a bouge.")

    print()
    print("panel_quadruple.txt commencera par les dix sections a")
    print("quatre entrees, et se terminera par le panneau x60")
    print("recopie -- au lieu de l inverse.")
    print()
    print("panel_x60_onset.txt n est toujours PAS modifie.")
    print()
    print("ATTENTION -- le service NE reprendra PAS ce changement tout")
    print("seul. Le mode --boucle appelle main() dans le MEME")
    print("processus : il ne relit jamais son propre fichier. Et le")
    print("gardien ne relance que ce qui est MORT.")
    print()
    print("Il faut donc arreter le processus panel_quadruple ; le")
    print("gardien le relancera sous 5 min avec le code neuf. C est un")
    print("lecteur, l arreter ne coute rien.")

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

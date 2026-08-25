#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cartes_chemins.py -- /cartes cherche ses fichiers la ou ils sont.

LE DEFAUT, MESURE ET NON SUPPOSE
--------------------------------
Le 25/08, les trois routes du 8095 repondaient 200 :

    /                          2,1 s   1 013 061 o
    /cartes                    0,0 s         740 o
    /carte?f=cartes_live.html  0,2 s         740 o

740 octets, c est la page "Aucune carte dans cartes", sans style et
sans barre. Et /carte?f= rendait la MEME taille : il n avait pas trouve
le fichier non plus et etait retombe sur l index.

Une seule cause explique les trois symptomes. La route travaille en
chemins RELATIFS -- open("price_action.py") pour le style et la barre,
_d = "cartes" pour la liste. Le panneau ne tourne pas depuis le dossier
de la stack, donc les trois echouent ensemble, et en silence puisque
tout est sous try/except.

C est pour ca que "avant il donnait tout" : le jour ou il donnait tout,
le repertoire courant etait le bon.

POURQUOI ON ANCRE PAR POSITION ET NON PAR MOTIF
    Deux versions de ce patch ont refuse avant celle-ci, et chaque
    refus a appris quelque chose.

    La premiere cherchait `_css, _bar`. La route a ete retouchee depuis
    sa pose : c est desormais `_css, _bloc`, elle prend le bloc
    hdr..tabs entier au lieu des onglets un par un.

    La seconde a trouve `_css, _bloc` DEUX fois -- la route /profils a
    la meme structure. Modifier "la premiere trouvee" aurait ete jouer
    a pile ou face sur laquelle des deux.

    On ancre donc sur l en-tete de la route, qui porte la chaine
    "/cartes" et ne peut exister qu une fois, et on cherche tout le
    reste A PARTIR de cette position. Le voisinage n est plus suppose :
    il est localise.

LA RACINE EST POSEE AVANT LE try
    Le dossier des cartes s en sert plus bas. Definie a l interieur du
    try, elle manquerait des que la lecture du style echouerait -- et
    on aurait remplace une panne silencieuse par une exception.

ET LE BOUTON CARTES LIVE
    Une route sans bouton vaut zero -- c est ecrit dans mistakes.md.
    Il vit dans la barre, bien plus haut dans le fichier, et lui est
    unique : il se remplace par motif.

USAGE
-----
    python patch_cartes_chemins.py                 <- simulation
    python patch_cartes_chemins.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\price_action.py"
SUFFIXE_BAK = ".bak_chemins"
MARQUEUR = "_racine_cartes"

TETE = ('            if parsed.path == "/cartes" or parsed.path == "/carte":\n'
        "                import os as _o\n"
        "                import re as _re\n"
        "                import time as _t")

RACINE = ("\n                # Ancre sur le dossier de CE fichier. En relatif,"
          "\n                # la route dependait du repertoire courant du"
          "\n                # panneau : le 25/08 elle rendait 740 octets,"
          "\n                # sans style, sans barre, et sans trouver la"
          "\n                # carte demandee. Posee AVANT le try : le"
          "\n                # dossier des cartes s en sert plus bas."
          "\n                _racine_cartes = _o.path.dirname("
          "_o.path.abspath(__file__))")

A_OPEN = ('                    _src = open("price_action.py", "r", '
          'encoding="utf-8",\n'
          '                                errors="ignore").read()')
B_OPEN = ("                    _src = open(_o.path.join(_racine_cartes,\n"
          '                                             "price_action.py"),'
          ' "r",\n'
          '                                encoding="utf-8",\n'
          '                                errors="ignore").read()')

A_DOSSIER = '                _d = "cartes"'
B_DOSSIER = '                _d = _o.path.join(_racine_cartes, "cartes")'

A_BOUTON = ('<div class="tab" onclick="window.open(\'/cartes\',\'_blank\')" '
            'style="color:#58a6ff;font-weight:bold;">CARTES</div>')
B_BOUTON = (A_BOUTON + '<div class="tab" onclick="window.open('
            "'/carte?f=cartes_live.html','_blank')\" "
            'style="color:#58a6ff;font-weight:bold;">CARTES LIVE</div>')


def applique(s):
    """(texte, erreur). Tout est cherche A PARTIR de la tete de route,
    sauf le bouton qui vit dans la barre, bien plus haut."""
    n = s.count(TETE)
    if n != 1:
        return None, ("en-tete de la route /cartes attendue 1 fois,"
                      " trouvee %d" % n)
    n = s.count(A_BOUTON)
    if n != 1:
        return None, "bouton CARTES attendu 1 fois, trouve %d" % n
    s = s.replace(A_BOUTON, B_BOUTON, 1)
    i = s.index(TETE) + len(TETE)
    s = s[:i] + RACINE + s[i:]
    i = s.index(TETE)
    for vieux, neuf, quoi in ((A_OPEN, B_OPEN, "le open de price_action.py"),
                              (A_DOSSIER, B_DOSSIER, "le dossier cartes")):
        j = s.find(vieux, i)
        if j < 0:
            return None, "%s introuvable apres la tete de route" % quoi
        s = s[:j] + neuf + s[j + len(vieux):]
    return s, ""


def lire(chemin):
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 68)
    print("patch_cartes_chemins -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 68)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))
    if MARQUEUR in s:
        print("")
        print("Deja corrige : les chemins sont ancres.")
        return 0

    neuf, err = applique(s)
    if neuf is None:
        print("")
        print("REFUS : %s." % err)
        print("Me montrer les lignes plutot que de me laisser deviner :")
        print("c est le fichier qui sert le 8095.")
        return 1
    print("        en-tete de route unique, bouton unique, motifs trouves.")
    print("")
    print("a faire :")
    print("   + _racine_cartes, ancre sur __file__, posee avant le try")
    print("   ~ price_action.py et le dossier cartes en chemin absolu")
    print("   + bouton CARTES LIVE a cote de CARTES")

    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer.")
        return 0

    bak = a.cible + SUFFIXE_BAK
    if not os.path.exists(bak):
        shutil.copy2(a.cible, bak)
        print("")
        print("sauvegarde : %s" % bak)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    print("ecrit : %s" % a.cible)

    relu = lire(a.cible)
    manques = [x for x in (MARQUEUR, "CARTES LIVE",
                           '_o.path.join(_racine_cartes, "cartes")')
               if x not in relu]
    if manques:
        print("relu   : INCOMPLET, manque %s -- RESTAURER %s"
              % (", ".join(manques), bak))
        return 1
    print("relu   : les trois marques attendues sont presentes.")
    try:
        compile(relu, a.cible, "exec")
        print("syntaxe: le fichier compile.")
    except SyntaxError as e:
        print("syntaxe: ERREUR ligne %s -- RESTAURER %s" % (e.lineno, bak))
        return 1

    print("")
    print("-" * 68)
    print("PREND EFFET AU PROCHAIN DEMARRAGE DU PANNEAU. Il se termine")
    print("seul toutes les ~40 min et le gardien le relance : il n y a")
    print("rien a arreter, et surtout pas a la main -- price_action lance")
    print("sans PA_ROLE=panel est un des interdits de la machine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

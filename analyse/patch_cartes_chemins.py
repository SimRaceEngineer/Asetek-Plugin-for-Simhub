#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cartes_chemins.py -- /cartes cherche ses fichiers la ou ils sont.

LE DEFAUT, MESURE ET NON SUPPOSE
--------------------------------
Le 25/08, les trois routes du 8095 repondaient 200 :

    /                          2,1 s   1 013 061 o
    /cartes                    0,0 s         740 o
    /carte?f=cartes_live.html  0,2 s         740 o

740 octets, c est la page "Aucune carte dans cartes\", sans style et
sans barre. Et `/carte?f=` rendait la MEME taille : il n avait pas
trouve le fichier non plus et etait retombe sur l index.

Une seule cause explique les trois symptomes. La route travaille en
chemins RELATIFS -- `open("price_action.py")` pour le style et la
barre, `listdir("cartes")` pour la liste. Le panneau ne tourne pas
depuis le dossier de la stack, donc les trois echouent ensemble, et en
silence puisque tout est sous try/except.

C est pour ca que "avant il donnait tout" : le jour ou il donnait tout,
le repertoire courant etait le bon.

LE CORRECTIF
    Les chemins sont ancres sur le dossier de price_action.py lui-meme,
    via __file__. Le repertoire courant n entre plus en jeu.

ET LE BOUTON CARTES LIVE
    Une route sans bouton vaut zero -- c est ecrit dans mistakes.md.
    Le panneau des papers rempli par le compte dedie prend donc sa
    place a cote de CARTES, sur le meme modele, meme couleur.

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

R = []

# 1. le style et la barre, lus dans price_action.py lui-meme
R.append(('''                _css, _bar = "", ""
                try:
                    _src = open("price_action.py", "r", encoding="utf-8",
                                errors="ignore").read()''',
          '''                # Ancre sur le dossier de CE fichier. En relatif, la
                # route dependait du repertoire courant du panneau : le
                # 25/08 elle rendait 740 octets sans style ni barre.
                _racine_cartes = _o.path.dirname(_o.path.abspath(__file__))
                _css, _bar = "", ""
                try:
                    _src = open(_o.path.join(_racine_cartes,
                                             "price_action.py"), "r",
                                encoding="utf-8",
                                errors="ignore").read()''', 1))

# 2. le dossier des cartes
R.append(('''                _d = "cartes"''',
          '''                _d = _o.path.join(_racine_cartes, "cartes")''', 1))

# 3. le bouton, a cote de CARTES
R.append(('''<div class="tab" onclick="window.open('/cartes','_blank')" style="color:#58a6ff;font-weight:bold;">CARTES</div>''',
          '''<div class="tab" onclick="window.open('/cartes','_blank')" style="color:#58a6ff;font-weight:bold;">CARTES</div><div class="tab" onclick="window.open('/carte?f=cartes_live.html','_blank')" style="color:#58a6ff;font-weight:bold;">CARTES LIVE</div>''', 1))


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

    manquants = []
    for i, (vieux, _n, att) in enumerate(R, 1):
        c = s.count(vieux)
        if c != att:
            manquants.append((i, att, c, vieux.strip().split("\n")[0][:58]))
    if manquants:
        print("")
        print("REFUS : la route /cartes n a pas la forme attendue.")
        for i, att, c, tete in manquants:
            print("   motif %d : attendu %d fois, trouve %d" % (i, att, c))
            print("      %s..." % tete)
        print("")
        print("Elle a ete posee par patch_route_cartes.py ; si elle a ete")
        print("retouchee depuis, me montrer les lignes. Je ne devine pas")
        print("dans le fichier qui sert le 8095.")
        return 1
    print("        les %d motifs sont la, aux bons comptes." % len(R))
    print("")
    print("a faire :")
    print("   ~ style, barre et dossier des cartes ancres sur __file__")
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
    for vieux, neuf, _x in R:
        s = s.replace(vieux, neuf, 1)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(s)
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

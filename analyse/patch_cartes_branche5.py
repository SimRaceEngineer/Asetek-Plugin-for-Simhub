#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cartes_branche5.py -- le panneau affiche la troisieme branche.

cartes_live ne connait que deux branches : le magic lui-meme et le meme
prefixe d un 4. La branche 5 tomberait donc dans la rubrique des
familles non repertoriees, avec un magic a sept chiffres et sans nom --
lisible, mais pas comparable.

Or c est precisement la comparaison qui compte :

    240004  branche 1   sans filtre
    240004  branche 2   sans filtre, ancien regime de sortie
    240004  branche 5   filtre CVD, meme sortie que la branche 1

Les trois sur trois lignes consecutives, meme magic, memes colonnes.
L ecart entre la 1 et la 5 se lit alors d un coup d oeil.

USAGE
-----
    python patch_cartes_branche5.py                 <- simulation
    python patch_cartes_branche5.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\cartes_live.py"
SUFFIXE_BAK = ".bak_branche5"
MARQUEUR = "5220000 <= m <= 5249999"

R = []

R.append(('''def base_et_branche(magic):
    """4240004 -> (240004, 2). 240004 -> (240004, 1)."""
    m = int(magic)
    if 4220000 <= m <= 4249999:
        return m - 4000000, 2
    return m, 1''',
          '''def base_et_branche(magic):
    """4240004 -> (240004, 2). 5240004 -> (240004, 5). 240004 -> (240004, 1).

    La branche 5 prend la MEME entree que la 1, au meme instant et au
    meme lot, avec la meme sortie -- le filtre CVD est leur seule
    difference. L ecart entre les deux ne mesure donc que lui.
    """
    m = int(magic)
    if 4220000 <= m <= 4249999:
        return m - 4000000, 2
    if 5220000 <= m <= 5249999:
        return m - 5000000, 5
    return m, 1''', 1))

R.append(('''        for br in (1, 2):
            c = constate(par.get((s["magic"], br)), po)
            if br == 2 and c is None:
                continue''',
          '''        for br in (1, 2, 5):
            c = constate(par.get((s["magic"], br)), po)
            if br != 1 and c is None and not par.get((s["magic"], br)):
                continue''', 1))

R.append(('''        for br in (1, 2):
            for ligne in bloc_constate(par.get((s["magic"], br)), po, br,
                                       cpt.get("login", 0)):
                a(ligne)''',
          '''        for br in (1, 2, 5):
            for ligne in bloc_constate(par.get((s["magic"], br)), po, br,
                                       cpt.get("login", 0)):
                a(ligne)''', 1))

R.append(('''    a("  BR      1 = miroir 1, le magic du paper. 2 = miroir 2, le meme")
    a("          magic prefixe d un 4 : MEME entree, MEME lot, MEME")
    a("          instant -- seule la SORTIE differe. L ecart entre les")
    a("          deux lignes ne mesure donc que la gestion de sortie.")''',
          '''    a("  BR      1 = miroir 1, le magic du paper. 2 = miroir 2, le meme")
    a("          magic prefixe d un 4 : MEME entree, MEME lot, MEME")
    a("          instant -- seule la SORTIE differe. L ecart entre les")
    a("          deux lignes ne mesure donc que la gestion de sortie.")
    a("          5 = miroir 5, le magic prefixe d un 5 : meme entree,")
    a("          meme sortie que la branche 1, mais l entree doit avoir")
    a("          passe le filtre CVD -- le delta de la bougie M1 en cours")
    a("          doit avoir depasse celui de la precedente close. L ecart")
    a("          entre la 1 et la 5 ne mesure donc que ce filtre.")''', 1))


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 66)
    print("patch_cartes_branche5 -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 66)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))
    if MARQUEUR in s:
        print("")
        print("Deja corrige : la branche 5 est connue.")
        return 0

    for i, (vieux, _n, att) in enumerate(R, 1):
        c = s.count(vieux)
        if c != att:
            print("")
            print("REFUS : motif %d attendu %d fois, trouve %d." % (i, att, c))
            print("   %s..." % vieux.strip().split("\n")[0][:56])
            return 1
    print("        les %d motifs sont la, aux bons comptes." % len(R))
    print("")
    print("a faire :")
    print("   ~ base_et_branche() reconnait la plage 5220000-5249999")
    print("   ~ le tableau et le detail parcourent les branches 1, 2 et 5")
    print("   + la legende explique ce que l ecart 1 contre 5 mesure")

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
    manques = [x for x in (MARQUEUR, "for br in (1, 2, 5):",
                           "passe le filtre CVD") if x not in relu]
    if manques:
        print("relu   : INCOMPLET, manque %s -- restaurer %s"
              % (", ".join(manques), bak))
        return 1
    print("relu   : les trois marques attendues sont presentes.")
    try:
        compile(relu, a.cible, "exec")
        print("syntaxe: le fichier compile.")
    except SyntaxError as e:
        print("syntaxe: ERREUR ligne %s -- restaurer %s" % (e.lineno, bak))
        return 1
    print("")
    print("-" * 66)
    print("Prend effet a la prochaine execution : python cartes_live.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

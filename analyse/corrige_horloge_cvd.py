#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""corrige_horloge_cvd.py -- le flux, ou juste l horloge ?

CE QUE LA MESURE DU 25/08 A REVELE
----------------------------------
La repartition des secondes ecoulees, separee entre autorisees et
refusees, donne :

    autorisees   23 %  22 %  26 %  29 %      presque plate
    refusees     28 %  37 %  20 %  15 %      65 % en premiere moitie

Les autorisees etant plates, le resultat n est PAS un artefact
d horloge : si la regle ne mesurait que le temps ecoule, elles se
tasseraient a 60 ou 70 % dans le dernier quart.

Mais les refusees, elles, sont massivement en debut de minute. Le
filtre encode donc partiellement une regle beaucoup plus simple : ne
pas entrer dans la premiere moitie de la minute. C est mecanique --
peu de ticks ecoules, delta partiel faible, la regle refuse.

CE QU IL FAUT SAVOIR AVANT DE CONSTRUIRE QUOI QUE CE SOIT
    Si les entrees precoces perdent et les tardives gagnent, une simple
    regle d horloge capterait l essentiel du gain et le CVD n
    apporterait rien qu une montre ne donne. Ce serait une bonne
    nouvelle -- plus simple, plus robuste, aucun indicateur a lire --
    mais ca changerait ce qu on met dans une branche filtrante.

    Ce correctif ajoute donc, sur LES MEMES entrees et sans rien
    relire : le PnL par quart de minute sans aucun filtre, puis ce que
    rapporterait la regle d horloge seule a trois seuils.

USAGE
-----
    python corrige_horloge_cvd.py                 <- simulation
    python corrige_horloge_cvd.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\cvd_v13_tick.py"
SUFFIXE_BAK = ".bak_horloge"
MARQUEUR = "LE FLUX, OU JUSTE L HORLOGE ?"

ANCRE = '''        print("")
        print("  Si les autorisees se tassaient dans le dernier quart, la")'''

BLOC = '''        # -- LA QUESTION QUI PRIME : le flux, ou juste l horloge ?
        # Les refusees sont massivement en debut de minute. Si les
        # entrees precoces perdaient et les tardives gagnaient, une
        # simple regle d horloge -- ne pas entrer avant la 30e seconde
        # -- capterait l essentiel du gain, et le CVD n ajouterait rien.
        # On compare donc les deux filtres SUR LES MEMES entrees.
        print("")
        print("-" * 74)
        print("LE FLUX, OU JUSTE L HORLOGE ?")
        print("-" * 74)
        qn = [base.tas() for _ in range(4)]
        for x in mesures:
            base.ajoute(qn[min(3, int(x["s"]) // 15)], x["pnl"])
        print("  PnL par quart de minute, TOUTES entrees, sans aucun filtre :")
        for i, t in enumerate(qn):
            print("     %02d-%02ds  n %3d   PnL %+9.2f   %+6.2f / trade"
                  % (i * 15, i * 15 + 14, t["n"], t["pnl"],
                     t["pnl"] / t["n"] if t["n"] else 0.0))
        for seuil in (15, 30, 45):
            hp, hr = base.tas(), base.tas()
            for x in mesures:
                base.ajoute(hp if x["s"] >= seuil else hr, x["pnl"])
            print("")
            print("  HORLOGE SEULE, entrer a partir de la %de seconde :"
                  % seuil)
            print("     gardees %3d  PnL %+9.2f  %+6.2f/tr    refusees %3d"
                  "  PnL %+9.2f" % (hp["n"], hp["pnl"],
                                    hp["pnl"] / hp["n"] if hp["n"] else 0.0,
                                    hr["n"], hr["pnl"]))
            print("     la regle d horloge rapporterait %+.2f" % (-hr["pnl"]))
        print("")
        print("  Si l horloge seule rapporte autant que le CVD, le CVD")
        print("  n apporte rien qu une montre ne donne. Si elle rapporte")
        print("  nettement moins, le flux porte quelque chose que le temps")
        print("  ecoule n explique pas.")

''' + ANCRE


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 66)
    print("corrige_horloge_cvd -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 66)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))

    if MARQUEUR in s:
        print("")
        print("Deja corrige.")
        return 0
    n = s.count(ANCRE)
    if n != 1:
        print("")
        print("REFUS : ancre attendue 1 fois, trouvee %d." % n)
        print("Le fichier n est pas celui que j attends -- il faut la")
        print("version v3, celle qui separe deja autorisees et refusees.")
        return 1
    print("        l ancre est unique.")
    print("")
    print("a faire :")
    print("   + PnL par quart de minute, toutes entrees, sans filtre")
    print("   + ce que rapporterait l horloge seule aux seuils 15, 30, 45")

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
    s = s.replace(ANCRE, BLOC, 1)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print("ecrit : %s" % a.cible)

    relu = lire(a.cible)
    if MARQUEUR not in relu or "HORLOGE SEULE" not in relu:
        print("relu   : INCOMPLET -- restaurer %s" % bak)
        return 1
    print("relu   : les deux marques attendues sont presentes.")
    try:
        compile(relu, a.cible, "exec")
        print("syntaxe: le fichier compile.")
    except SyntaxError as e:
        print("syntaxe: ERREUR ligne %s -- restaurer %s" % (e.lineno, bak))
        return 1
    print("")
    print("-" * 66)
    print("Relancer : python cvd_v13_tick.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

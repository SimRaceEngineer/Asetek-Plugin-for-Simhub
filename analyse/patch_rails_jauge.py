#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_rails_jauge.py -- ajoute la section "jauge H1" au panel rails.

Meme forme que patch_rails_magic.py et les cinq autres : deux ancres, une
verification d unicite, un ast.parse avant d ecrire, une sauvegarde.
Rien d invente, la convention de la maison est reprise telle quelle.

  ANCRE_IMPORT : la ligne _BR, qui existe une seule fois
  ANCRE_APPEL  : {_section_hourly(trades)}, qui reste unique quel que soit
                 l ordre des sections deja posees

La section est inseree AVANT le bloc horaire, donc en haut de page : la
jauge est un etat de la seance, pas un detail de fin de tableau.

IDEMPOTENT : relancer le script ne fait rien si la section est deja la.
"""
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "rails_trades_panel.py"
MODULE = "jauge_section.py"

ANCRE_IMPORT = "_BR = os.path.dirname(os.path.abspath(__file__))"
ANCRE_APPEL = "{_section_hourly(trades)}"

BLOC_IMPORT = '''# Section "jauge H1" (module separe, ajout 09/08).
try:
    import jauge_section as _jauge
except Exception:
    _jauge = None

'''

BLOC_APPEL = "{_jauge.render(trades) if _jauge else ''}\n"

MARQUEUR = "import jauge_section as _jauge"


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable -- lance depuis le dossier de la stack." % CIBLE)
        return 1
    if not os.path.isfile(MODULE):
        print("KO : %s introuvable. Le patch poserait un import mort." % MODULE)
        print("     Copie jauge_section.py a cote de %s avant de relancer." % CIBLE)
        return 1

    src = io.open(CIBLE, encoding="utf-8").read()

    if MARQUEUR in src:
        print("Section deja presente dans %s -- rien a faire." % CIBLE)
        return 0

    for nom, a in (("import", ANCRE_IMPORT), ("appel", ANCRE_APPEL)):
        c = src.count(a)
        if c != 1:
            print("KO : ancre %s trouvee %d fois (attendu 1) -- abandon" % (nom, c))
            return 1

    out = src.replace(ANCRE_IMPORT, BLOC_IMPORT + ANCRE_IMPORT, 1)
    out = out.replace(ANCRE_APPEL, BLOC_APPEL + ANCRE_APPEL, 1)

    try:
        ast.parse(out)
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (%s ligne %s) -- rien ecrit."
              % (e.msg, e.lineno))
        return 1

    bak = "%s.bak-jauge-%s" % (CIBLE, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copyfile(CIBLE, bak)
    io.open(CIBLE, "w", encoding="utf-8").write(out)
    print("OK : section jauge H1 ajoutee a %s" % CIBLE)
    print("     sauvegarde %s" % bak)
    print()
    print("La section lit docs/jauge_h1.json et ne calcule rien. Si le")
    print("fichier manque, elle affiche un message et le panel continue de")
    print("fonctionner normalement -- aucune section ne peut le casser.")
    print()
    print("Pense a lancer jauge_h1.py apres 17h30 courtier chaque jour,")
    print("sinon la jauge affichera la date de son dernier calcul en orange.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

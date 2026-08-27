#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_carte_html6.py -- la branche 6 entre dans le panneau HTML.

CE QU IL CORRIGE
----------------
patch_carte_branche6 a appris a base_et_branche a lire le prefixe 6, et
le panneau TEXTE affiche depuis la ligne :

    240003  ACCORD M15 HAUSSIER [MR]  6  |  n 27  70%  52%  +4.32  +116.61

Le panneau HTML, lui, ne connait que trois branches. Tout part de :

    BRANCHES = (1, 2, 5)                              ligne 556

qui pilote les badges de la table des ratios (797, 806), les colonnes de
la table croisee (722, 726) et ses en-tetes (728-732). La branche 6
existe dans les donnees et n a aucune colonne pour s afficher.

CE QUE CE PATCH POSE
--------------------
Six ancres, et l une d elles n est pas evidente :

    ('<th>n</th><th>taux</th><th>PnL/tr</th><th>PnL</th>' * 3)

Les quatre sous-titres sont repetes TROIS fois, une par branche. Passer
a quatre branches sans toucher ce 3 decalerait toute la ligne d en-tete
d un bloc -- les colonnes du miroir 6 porteraient les titres du 5, et
personne ne le verrait tout de suite. C est le genre d erreur qui rend
un tableau faux sans le rendre laid.

Couleur : un turquoise #39c5bb, distinct du bleu du miroir 1, de l ambre
du 2 et du violet du 5, et distinct aussi du vert et du rouge qui
signent les montants. Sans classe g6 et th.h6, la colonne sortirait
sans fond et se lirait comme une anomalie d affichage.

CE QU IL NE FAIT PAS
--------------------
Il n ajoute pas la ligne d ecart "6 moins 1". Elle vit apres la ligne
812, que je n ai pas lue -- et ecrire une ancre sur du code que je n ai
pas sous les yeux, c est exactement ce qui a fait echouer trois patchs
cette semaine.

USAGE
-----
    python patch_carte_html6.py                 <- simulation
    python patch_carte_html6.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import time

CIBLE_DEFAUT = "cartes_live.py"
MARQUEUR = "h6{background"

ANCRES = (
    # (nom, motif, remplacement)
    ("1  couleur du badge",
     re.compile(r"^#cl \.g5\{background:#a371f7\}$", re.M),
     "#cl .g5{background:#a371f7}\n#cl .g6{background:#39c5bb}"),

    ("2  couleur de l en-tete",
     re.compile(r"^#cl th\.h5\{background:#221a33;color:#a371f7;"
                r"text-align:center\}$", re.M),
     "#cl th.h5{background:#221a33;color:#a371f7;text-align:center}\n"
     "#cl th.h6{background:#0f2b29;color:#39c5bb;text-align:center}"),

    ("3  chip de legende",
     re.compile(r'<span class="cle g5">5 &middot; entree filtree CVD</span>'
                r'</div>'),
     '<span class="cle g5">5 &middot; entree filtree CVD</span>\n'
     '<span class="cle g6">6 &middot; trailing 0.50R</span></div>'),

    ("4  la liste des branches",
     re.compile(r"^BRANCHES = \(1, 2, 5\)$", re.M),
     "BRANCHES = (1, 2, 5, 6)"),

    ("5  l en-tete des blocs",
     re.compile(r'\(5, "entree filtree CVD"\)\)\)'),
     '(5, "entree filtree CVD"),\n'
     '                      (6, "trailing 0.50R")))'),

    # Celle-la est la piege : les quatre sous-titres sont repetes une
    # fois par branche. Trois branches -> * 3. Quatre -> * 4.
    ("6  la repetition des sous-titres",
     re.compile(r"\('<th>n</th><th>taux</th><th>PnL/tr</th>"
                r"<th>PnL</th>' \* 3\)"),
     "('<th>n</th><th>taux</th><th>PnL/tr</th><th>PnL</th>' * 4)"),
)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.cible):
        print("ABANDON : %s introuvable." % a.cible)
        return 2
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    if MARQUEUR in src:
        print("DEJA POSE : la classe th.h6 est presente dans %s." % a.cible)
        return 0
    if "6220000" not in src:
        print("REFUS : base_et_branche ne connait pas encore le prefixe 6.")
        print("        Appliquez d abord patch_carte_branche6.py : sans lui,")
        print("        une colonne 6 s afficherait toujours vide.")
        return 3

    crlf = "\r\n" in src
    for nom, rx, _ in ANCRES:
        c = len(rx.findall(src))
        if c != 1:
            print("REFUS : ancre %s attendue 1 fois, trouvee %d." % (nom, c))
            return 3

    neuf = src
    for nom, rx, rem in ANCRES:
        r = rem.replace("\n", "\r\n") if crlf else rem
        neuf = rx.sub(lambda _m, _r=r: _r, neuf, count=1)

    try:
        compile(neuf, a.cible, "exec")
    except SyntaxError as e:
        print("REFUS : le resultat ne compile pas -- ligne %s : %s"
              % (e.lineno, e.msg))
        return 4

    print("%d ancres posees, resultat compile." % len(ANCRES))
    for nom, _, _ in ANCRES:
        print("    %s" % nom)
    print("  %d -> %d octets  (+%d)" % (len(src), len(neuf),
                                        len(neuf) - len(src)))
    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancez avec --appliquer.")
        return 0

    sauve = "%s.avant_html6_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.cible, sauve)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        relu = f.read()
    ok = (MARQUEUR in relu and "BRANCHES = (1, 2, 5, 6)" in relu
          and "' * 4)" in relu)
    print("")
    print("sauvegarde   : %s" % os.path.basename(sauve))
    print("VERIFICATION : %s" % ("ok" if ok else "ECHEC"))
    if not ok:
        shutil.copy2(sauve, a.cible)
        print("Le fichier a ete REMIS dans son etat d origine.")
        return 5
    print("")
    print("boucle_cartes_live relit le module a chaque tour : la prochaine")
    print("generation portera la colonne. Rien a redemarrer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_carte_defaut.py -- /cartes sert papers_rendu, pas le dernier ecrit.

LE DEFAUT, LU DANS LE CODE ET NON SUPPOSE
-----------------------------------------
La route /cartes de price_action.py choisit ainsi la page a servir :

    _n.sort(key=lambda x: _o.path.getmtime(_d + "/" + x), reverse=True)
    if not _f and _n:
        _f = _n[0]

Le defaut est donc LE FICHIER LE PLUS RECEMMENT ECRIT du dossier
cartes. Tant que chaque panneau etait produit a la main, le dernier
ecrit etait celui qu on venait de demander : le defaut tombait juste
par accident.

Le 26/08 j ai mis cartes_live.py dans une boucle de 60 secondes pour
que sa page cesse de vieillir. Depuis, cartes_live.html est en
permanence le plus recent du dossier -- 10:07 contre 10:05 pour
papers_rendu.html le 27/08 au matin. Il gagne ce concours a chaque
tour, pour toujours. /cartes servait donc le panneau live a la place
du rendu des 23 papers, celui qu on lit reellement.

Le panneau complet n a jamais ete ecrase : chaque generateur ecrit son
propre nom de fichier. Il a seulement perdu sa place.

CE QU ON CHANGE, ET CE QU ON NE CHANGE PAS
------------------------------------------
On change UNIQUEMENT le choix du defaut. La liste continue d etre
triee par date : c est une information utile, elle montre d un coup d
oeil quel panneau respire et lequel est fige. C est le DEFAUT qui ne
doit pas en dependre.

L ordre de preference est explicite et ecrit une fois pour toutes :

    papers_rendu.html    le rendu des 23 traders papier
    papers_live.html     a defaut
    puis le plus recent  si aucun des deux n existe

Un ?f= explicite reste prioritaire sur tout : les boutons et les liens
de la liste continuent de fonctionner a l identique, cartes_live.html
compris.

POURQUOI UNE PREFERENCE NOMMEE ET NON UN AUTRE TRI
    Trier par nom ferait tomber le defaut sur le premier alphabetique
    -- aujourd hui cartes_live.html, exactement le meme probleme avec
    un autre critere. Un defaut se DECLARE, il ne s emerge pas d un
    classement.

APRES LA POSE
    price_action.py doit etre redemarre : la route est du code
    compile, pas un fichier relu a chaque requete. Et il ne se lance
    JAMAIS sans PA_ROLE=panel.

USAGE
-----
    python patch_carte_defaut.py                 <- simulation
    python patch_carte_defaut.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys
import time

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\price_action.py"
MARQUEUR = "_prefs_carte"

ANCRE = ("                if not _f and _n:\n"
         "                    _f = _n[0]\n")

NEUF = (
    "                # Le defaut ne suit plus l horodatage. Le 27/08, la\n"
    "                # boucle de cartes_live reecrivait sa page toutes les\n"
    "                # 60 s : elle etait donc TOUJOURS la plus recente, et\n"
    "                # /cartes servait le panneau live a la place de\n"
    "                # papers_rendu, celui qu on lit. Un defaut qui depend\n"
    "                # de la cadence d ecriture n est pas un defaut.\n"
    "                # La liste, elle, reste triee par date : voir quel\n"
    "                # panneau respire et lequel est fige a de la valeur.\n"
    "                _prefs_carte = (\"papers_rendu.html\",\n"
    "                                \"papers_live.html\")\n"
    "                if not _f:\n"
    "                    for _p in _prefs_carte:\n"
    "                        if _p in _n:\n"
    "                            _f = _p\n"
    "                            break\n"
    "                if not _f and _n:\n"
    "                    _f = _n[0]\n")


def lis(chemin):
    with io.open(chemin, "r", encoding="utf-8", newline="") as f:
        return f.read()


def ecris(chemin, texte):
    with io.open(chemin, "w", encoding="utf-8", newline="") as f:
        f.write(texte)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.cible):
        print("ABANDON : %s introuvable." % a.cible)
        return 2

    src = lis(a.cible)

    # price_action.py peut porter des fins de ligne Windows. Lu avec
    # newline="" elles sont conservees telles quelles : l ancre doit
    # alors etre construite dans le meme dialecte, sinon elle n est
    # trouvee nulle part et le patch refuse pour une mauvaise raison.
    global ANCRE, NEUF
    if "\r\n" in src:
        ANCRE = ANCRE.replace("\n", "\r\n")
        NEUF = NEUF.replace("\n", "\r\n")

    if MARQUEUR in src:
        print("DEJA POSE : le marqueur %s est present." % MARQUEUR)
        print("Rien a faire, et surtout rien a poser deux fois.")
        return 0

    n = src.count(ANCRE)
    if n != 1:
        print("REFUS : l ancre attendue 1 fois, trouvee %d fois." % n)
        print("Le voisinage a change depuis ma lecture. Je ne touche a")
        print("rien : un patch qui vise a l aveugle casse plus qu il ne")
        print("repare. Redonnez-moi les lignes autour de _f = _n[0].")
        return 3

    neuf = src.replace(ANCRE, NEUF, 1)

    # Un fichier de 16 000 lignes se casse par une indentation. On le
    # compile AVANT de le poser : une erreur ici coute zero, la meme
    # erreur sur le disque coute le panneau.
    try:
        compile(neuf, a.cible, "exec")
    except SyntaxError as e:
        print("REFUS : le resultat ne compile pas -- ligne %s : %s"
              % (e.lineno, e.msg))
        return 4

    print("ancre trouvee, resultat compile.")
    print("  avant : le defaut = le fichier le plus recemment ecrit")
    print("  apres : le defaut = papers_rendu.html, puis papers_live.html")
    print("  la liste reste triee par date, ?f= reste prioritaire")
    print("  ecart de taille : +%d octets" % (len(neuf) - len(src)))

    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancez avec --appliquer pour poser.")
        return 0

    sauve = "%s.avant_defaut_carte_%s" % (a.cible,
                                          time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.cible, sauve)
    ecris(a.cible, neuf)

    relu = lis(a.cible)
    ok = (MARQUEUR in relu) and (relu.count("_f = _n[0]") == 1)
    print("")
    print("sauvegarde  : %s" % os.path.basename(sauve))
    print("VERIFICATION : %s" % ("ok" if ok else "ECHEC"))
    if not ok:
        shutil.copy2(sauve, a.cible)
        print("Le fichier a ete REMIS dans son etat d origine.")
        return 5
    print("")
    print("price_action.py doit etre redemarre pour que la route change :")
    print("la route est du code compile, pas un fichier relu par requete.")
    print("Et il ne se lance JAMAIS sans PA_ROLE=panel.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

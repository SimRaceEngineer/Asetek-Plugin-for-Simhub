# -*- coding: utf-8 -*-
"""
patch_x60_papier.py -- le releve papier dans le panneau X60

  python patch_x60_papier.py --essai
  python patch_x60_papier.py

POURQUOI UN PATCH ET PAS LE FICHIER ENTIER

    x60_onset_v2.py est deja sur le Drive et deja en place. Il lui
    manque une trentaine de lignes : chainer le releve de papier_tf a
    la fin de son rapport. Renvoyer 25 ko pour ca ferait courir le
    risque d ecraser une version plus recente.

CE QU IL AJOUTE

    Une fonction _avec_papier(L), appelee AUX DEUX sorties de
    rapport() -- y compris celle du cas « aucun evenement x60 ».
    C est le point qui compte : sans ca, le releve papier
    disparaitrait les jours ou aucun x60 ne trade, c est-a-dire
    justement les jours ou il serait le seul contenu du panneau.

    Import doux : si papier_tf est absent ou casse, le panneau x60
    reste entier et le DIT. Perdre ce qui marche a cause d une section
    optionnelle serait le pire des echanges.

TROIS ANCRES, verifiees uniques avant la moindre ecriture.
IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "x60_onset.py"
MARQUEUR = "_avec_papier"

RE_DEF = re.compile(r'^def rapport\(\):$', re.M)

RE_TOT = re.compile(
    r'^([ \t]*)L\.append\("Il ne voit que ce qui se passe PENDANT qu il'
    r' tourne\."\)\n([ \t]*)return L$', re.M)

RE_FIN = re.compile(
    r'^([ \t]*)L\.append\("  serait fausse -- et fausse dans le sens'
    r' flatteur\."\)\n([ \t]*)return L$', re.M)

HELPER = '''def _avec_papier(L):
    """Ajoute le releve papier x10..x240 a la fin du panneau x60.

    Appele AUX DEUX sorties de rapport(), y compris celle du cas « aucun
    evenement x60 » : sinon le releve papier disparaitrait les jours ou
    aucun x60 ne trade, c est-a-dire justement les jours ou il serait le
    seul contenu du panneau.

    Import doux : si papier_tf est absent ou casse, le panneau x60 reste
    entier. Perdre ce qui marche a cause d une section optionnelle serait
    le pire des echanges."""
    try:
        import papier_tf
        L.append("")
        L.append("")
        L.extend(papier_tf.rapport())
    except ImportError:
        L.append("")
        L.append("  (papier_tf.py absent : pas de releve papier ici.)")
    except Exception as _e:
        L.append("")
        L.append("  Le releve papier n a pas pu etre lu : %s: %s"
                 % (type(_e).__name__, _e))
    return L


'''


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

    for nom, rx in (("def rapport()", RE_DEF),
                    ("la sortie « aucun evenement »", RE_TOT),
                    ("la sortie finale", RE_FIN)):
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Le fichier n a pas la forme attendue -- il s agit peut-")
            print("etre d une version anterieure a x60_onset_v2.py.")
            print("Rien n a ete ecrit.")
            return 1

    neuf = RE_TOT.sub(lambda m: (m.group(1) + 'L.append("Il ne voit que ce'
                                 ' qui se passe PENDANT qu il tourne.")\n'
                                 + m.group(2) + "return _avec_papier(L)"),
                      src, count=1)
    neuf = RE_FIN.sub(lambda m: (m.group(1) + 'L.append("  serait fausse --'
                                 ' et fausse dans le sens flatteur.")\n'
                                 + m.group(2) + "return _avec_papier(L)"),
                      neuf, count=1)
    m = RE_DEF.search(neuf)
    neuf = neuf[:m.start()] + HELPER + neuf[m.start():]

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Le releve de papier_tf sera ajoute a la fin du rapport x60,")
    print("donc dans l onglet X60 ONSET du 8095 -- y compris les jours")
    print("ou aucun x60 n a trade, ou il sera le seul contenu.")
    print("Sans papier_tf, le panneau x60 reste entier et le dit.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Relance x60_onset.py --rapport pour le voir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

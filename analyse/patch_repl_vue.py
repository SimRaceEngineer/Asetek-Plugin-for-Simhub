# -*- coding: utf-8 -*-
"""
patch_repl_vue.py -- rendre le quadruple VISIBLE, et le journal LU

  python patch_repl_vue.py --essai
  python patch_repl_vue.py

DEUX FICHIERS, DEUX PROBLEMES DIFFERENTS

  price_action.py  -- l onglet X60 ONSET lit panels/panel_x60_onset.txt.
                      Le panneau quadruple existe et se regenere toutes
                      les 5 min, mais aucun bouton ne le montre : la
                      liste des onglets est ecrite en dur, un fichier
                      sans bouton est invisible.

  repl_web.py      -- _DOCS_REPL nomme docs/JOURNAL.md explicitement,
                      puis SCANNE les dossiers panels et notes. Le
                      dossier docs n est PAS scanne. JOURNAL_14_08.md
                      y a donc ete copie pour rien : le REPL ne le lit
                      pas tant qu il n est pas nomme dans la liste.

CE QUE FAIT LE PATCH, ET POURQUOI C EST MINIME

  1. _x60_panel() lit desormais panel_quadruple.txt au lieu de
     panel_x60_onset.txt.

     Ce n est PAS une perte : depuis patch_panel_joindre, le quadruple
     RECOPIE l integralite du panneau x60 en tete, puis ajoute ses dix
     sections. L onglet montrera donc tout ce qu il montrait, plus le
     reste. Aucun HTML a toucher, aucun bouton a creer.

     panel_x60_onset.txt continue d exister et d etre produit par
     x60_onset -- on ne fait que ne plus le lire ici.

  2. Le titre passe a "X60 ONSET + QUADRUPLE". Un onglet qui affiche
     autre chose que ce que son titre annonce est un piege a lecture.

  3. docs/JOURNAL_14_08.md entre dans _DOCS_REPL, juste apres
     JOURNAL.md -- donc TOT, avant que le plafond ne morde.

CE QUE LA TROISIEME MODIFICATION COUTE, ET C EST ECRIT DANS LE FICHIER

  Les commentaires de repl_web.py le disent deja : "le plafond etant
  atteint, remonter 24 ko fait sauter le dernier fichier du dossier".
  _DOCS_MAX vaut 200 000 caracteres. Ajouter ~8 400 caracteres en
  poussera donc autant par la QUEUE du parcours -- la fin du scan de
  `notes`.

  C est un arbitrage, pas un gain gratuit. Il est defendable parce que
  le REPL raisonnait jusqu ici sur un JOURNAL.md du 13/08 qui decrit
  une stack qui a change : il conseillait sur une configuration morte.
  Mais si un document de `notes` compte plus que cette mise a jour,
  il ne faut PAS appliquer la partie 3. Elle est separable :

      python patch_repl_vue.py --sans-journal

QUATRE ANCRES, chacune verifiee unique dans SON fichier. IDEMPOTENT
par fichier -- l un peut etre deja fait et pas l autre. Sauvegarde
horodatee de chacun. ast.parse des deux.

CE QUI EST VERIFIE AVANT D ECRIRE

  - panels/panel_quadruple.txt existe (sinon l onglet afficherait
    "Aucun releve" au lieu du panneau x60 qu il montrait avant)
  - il contient bien le panneau x60 recopie (le marqueur de son
    en-tete), sinon on remplacerait un panneau complet par un
    panneau partiel
  - docs/JOURNAL_14_08.md existe
  - les deux fichiers cibles parsent apres modification

Ce patch ne touche NI un collecteur, NI un moteur : price_action est
en role panneau, repl_web ne fait que lire.
"""
import argparse
import ast
import io
import os
import shutil
import sys
from datetime import datetime

PA = "price_action.py"
RW = "repl_web.py"
QUAD = os.path.join("panels", "panel_quadruple.txt")
JOUR = os.path.join("docs", "JOURNAL_14_08.md")

A_FIC = '"panels", "panel_x60_onset.txt")'
N_FIC = '"panels", "panel_quadruple.txt")'
A_TIT = '_txt.strip(), "X60 ONSET", _f, _age)'
N_TIT = '_txt.strip(), "X60 ONSET + QUADRUPLE", _f, _age)'
A_DOC = '_os.path.join(_ICI, "docs", "JOURNAL.md"),'


def ecrire(chemin, texte):
    sauve = "%s.bak-%s" % (chemin, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(chemin, sauve)
    io.open(chemin, "w", encoding="utf-8").write(texte)
    print("  sauvegarde : %s" % sauve)


def une(src, anc, nom):
    n = src.count(anc)
    if n != 1:
        print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
        return False
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--essai", action="store_true")
    p.add_argument("--sans-journal", action="store_true",
                   dest="sans_journal",
                   help="ne pas toucher a _DOCS_REPL")
    a = p.parse_args()
    fait = []

    # ---------------- 1 et 2 : l onglet -----------------------------
    if not os.path.isfile(PA):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % PA)
        return 1
    src = io.open(PA, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (PA, src.count("\n") + 1))

    if N_FIC in src:
        print("  onglet : deja fait.")
    else:
        # Sans le fichier, l onglet afficherait "Aucun releve" a la
        # place du panneau x60 qu il montrait avant : on regresserait.
        if not os.path.isfile(QUAD):
            print("KO : %s absent. L onglet perdrait ce qu il affiche"
                  " deja." % QUAD)
            print("Rien n a ete ecrit.")
            return 1
        q = io.open(QUAD, encoding="utf-8", errors="replace").read()
        if "ONSET x60" not in q:
            print("KO : %s ne contient pas le panneau x60 recopie."
                  % QUAD)
            print("     Appliquer patch_panel_joindre.py d abord, sinon")
            print("     on remplacerait un panneau complet par un")
            print("     panneau partiel.")
            print("Rien n a ete ecrit.")
            return 1
        print("  %s present, et il contient bien le panneau x60." % QUAD)

        if not une(src, A_FIC, "le chemin du panneau"):
            print("Rien n a ete ecrit.")
            return 1
        if not une(src, A_TIT, "le titre de l onglet"):
            print("Rien n a ete ecrit.")
            return 1
        neuf = src.replace(A_FIC, N_FIC, 1).replace(A_TIT, N_TIT, 1)
        try:
            ast.parse(neuf)
        except SyntaxError as e:
            print("KO : %s ne compile pas (ligne %s) : %s"
                  % (PA, e.lineno, e.msg))
            print("Rien n a ete ecrit.")
            return 1
        # Le placeholder et la fonction doivent survivre : sans eux la
        # page ne montrerait plus rien du tout.
        for t in ("<!--X60_ONSET_ICI-->", "def _x60_panel("):
            if src.count(t) != neuf.count(t):
                print("KO : %s n apparait plus le meme nombre de fois." % t)
                print("Rien n a ete ecrit.")
                return 1
        print("  onglet : le chemin et le titre changent, le")
        print("           placeholder et _x60_panel sont intacts.")
        if not a.essai:
            ecrire(PA, neuf)
        fait.append("onglet X60 ONSET -> panel_quadruple.txt")

    # ---------------- 3 : le journal --------------------------------
    if a.sans_journal:
        print()
        print("--sans-journal : _DOCS_REPL n est pas touche.")
    elif not os.path.isfile(RW):
        print("KO : %s introuvable." % RW)
        return 1
    else:
        rw = io.open(RW, encoding="utf-8", errors="replace").read()
        print("%s : %d lignes" % (RW, rw.count("\n") + 1))
        if "JOURNAL_14_08" in rw:
            print("  journal : deja dans _DOCS_REPL.")
        elif not os.path.isfile(JOUR):
            print("KO : %s absent -- le nommer sans qu il existe ferait"
                  " charger un fichier vide." % JOUR)
            print("Rien n a ete ecrit dans %s." % RW)
        elif not une(rw, A_DOC, "la ligne JOURNAL.md de _DOCS_REPL"):
            print("Rien n a ete ecrit dans %s." % RW)
        else:
            # L indentation est RECOPIEE de la ligne trouvee : ma copie
            # de ce fichier n existe pas, je ne suppose rien sur son
            # espacement.
            i = rw.index(A_DOC)
            deb = rw.rfind("\n", 0, i) + 1
            ind = rw[deb:i]
            neuve = (A_DOC + "\n" + ind
                     + '_os.path.join(_ICI, "docs", "JOURNAL_14_08.md"),')
            rn = rw.replace(A_DOC, neuve, 1)
            try:
                ast.parse(rn)
            except SyntaxError as e:
                print("KO : %s ne compile pas (ligne %s) : %s"
                      % (RW, e.lineno, e.msg))
                print("Rien n a ete ecrit dans %s." % RW)
                return 1
            if rn.count("_os.path.join(") != rw.count("_os.path.join(") + 1:
                print("KO : le compte des entrees de _DOCS_REPL est faux.")
                print("Rien n a ete ecrit dans %s." % RW)
                return 1
            n = len(io.open(JOUR, encoding="utf-8",
                            errors="replace").read())
            print("  journal : %d caracteres, insere JUSTE APRES"
                  " JOURNAL.md," % n)
            print("            donc charge avant que le plafond ne morde.")
            print("            _DOCS_MAX etant atteint, autant de")
            print("            caracteres sauteront par la QUEUE du")
            print("            parcours -- la fin du scan de notes.")
            if not a.essai:
                ecrire(RW, rn)
            fait.append("JOURNAL_14_08.md dans _DOCS_REPL")

    print()
    if not fait:
        print("Rien a faire -- tout etait deja en place.")
        return 0
    for f in fait:
        print("  %s" % f)
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DE price_action.py.")
    print("Le gardien le relancera avec PA_ROLE=panel -- ou plutot")
    print("run_panel_loop.bat, qui le pose aussi et gagne toujours la")
    print("course. NE JAMAIS le lancer a la main sans PA_ROLE=panel :")
    print("sans elle, _run_trading est vrai et de vrais ordres partent.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

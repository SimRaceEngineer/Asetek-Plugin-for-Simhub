# -*- coding: utf-8 -*-
"""
patch_docs_dedup_x60.py -- rendre ~28 700 caracteres au REPL, sans
                           lui retirer une seule ligne d information

  python patch_docs_dedup_x60.py --essai
  python patch_docs_dedup_x60.py
  python patch_docs_dedup_x60.py --annuler

LE CONSTAT

    panel_quadruple.txt RECOPIE panel_x60_onset.txt en entier -- c est
    le patch --joindre du 14/08, pour que tout soit lisible dans un
    seul onglet. Le REPL charge donc le meme texte DEUX FOIS : une
    fois a l interieur du quadruple, une fois comme document separe.

    Ce n est pas le dedoublonnage de repl_web qui echoue : lui porte
    sur le NOM du fichier, et il fait son travail. Ici les deux copies
    ont des noms differents. C est une duplication de CONTENU, qu
    aucun controle de nom ne peut voir.

    Cout : ~28 756 caracteres, ~8 000 jetons par question, pour zero
    information. Et la place manque : ce soir la reponse du REPL s est
    coupee en cours de phrase.

POURQUOI RETIRER LA LIGNE 131 NE SUFFIT PAS

    _DOCS_REPL nomme panel_x60_onset.txt (ligne 131) PUIS balaye le
    dossier panels (ligne 132). Retirer l entree nommee ne ferait que
    deplacer le chargement : le balayage le reprendrait par ordre
    alphabetique.

    Mais les deux chemins consultent le MEME jeu de noms deja vus,
    `_vus`. Le pre-remplir exclut donc le fichier des deux cotes a la
    fois, en une seule ancre :

        _cibles, _introuvables, _vus = [], [], set()
        ->
        _DOCS_EXCLUS = {"panel_x60_onset.txt"}
        _cibles, _introuvables, _vus = [], [], set(_DOCS_EXCLUS)

CE QU ON NE PERD PAS, ET C EST VERIFIE AVANT D ECRIRE

    Le patch refuse d agir si panels/panel_quadruple.txt est absent ou
    s il ne contient pas le panneau x60 recopie. Sans ce controle, on
    supprimerait la seule copie au lieu de la seconde.

    Ton onglet ne change pas : price_action lit panel_quadruple.txt,
    qui contient toujours les deux. Seul le REPL cesse de lire la
    copie en double.

MARCHE ARRIERE

    --annuler remet _DOCS_EXCLUS a l ensemble vide. Le fichier
    redevient charge au prochain demarrage. Rejouable dans les deux
    sens autant de fois qu on veut.

UNE SEULE ANCRE, verifiee unique. ast.parse et controle AST.
Sauvegarde horodatee. Ne touche qu un lecteur.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "repl_web.py"
QUAD = os.path.join("panels", "panel_quadruple.txt")
X60 = os.path.join("panels", "panel_x60_onset.txt")
MARQUE = "ONSET x60"

ANCRE = "        _cibles, _introuvables, _vus = [], [], set()"
NEUVE = (
    '        # 14/08 : panel_quadruple.txt recopie panel_x60_onset.txt\n'
    '        # en entier (patch --joindre). Le charger AUSSI comme\n'
    '        # document separe coute ~28 700 caracteres, ~8 000 jetons\n'
    '        # par question, pour zero information -- et la completion\n'
    '        # se tronquait faute de place.\n'
    '        # Pre-remplir _vus l exclut des DEUX cotes a la fois : de\n'
    '        # l entree nommee plus haut (panels/panel_x60_onset.txt)\n'
    '        # et du balayage de `panels`. Les deux consultent _vus.\n'
    '        # Le commentaire qui justifie de le nommer avant le\n'
    '        # dossier reste vrai, il devient simplement sans objet.\n'
    '        # Annuler : remettre set() ci-dessous, ou relancer le\n'
    '        # patch avec --annuler.\n'
    '        _DOCS_EXCLUS = {"panel_x60_onset.txt"}\n'
    '        _cibles, _introuvables, _vus = [], [], set(_DOCS_EXCLUS)')

# Reperee par le NOM : c est ce qui rend --annuler possible une fois
# le patch applique.
R_EXC = re.compile(r"^([ \t]*_DOCS_EXCLUS[ \t]*=[ \t]*)(\{[^}]*\}|set\(\))",
                   re.M)


def lire(c):
    return io.open(c, encoding="utf-8", errors="replace").read()


def exclus_ast(src):
    """Rend le contenu de _DOCS_EXCLUS lu dans l AST, ou None."""
    try:
        arbre = ast.parse(src)
    except SyntaxError:
        return None
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id == "_DOCS_EXCLUS"):
            try:
                return set(ast.literal_eval(n.value))
            except Exception:
                return None
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--annuler", action="store_true")
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = lire(a.fichier)
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    voulu = set() if a.annuler else {"panel_x60_onset.txt"}

    # ---- le controle qui evite de supprimer la seule copie ----------
    if not a.annuler:
        if not os.path.isfile(QUAD):
            print("KO : %s absent." % QUAD)
            print("     Sans lui, exclure %s ferait perdre le panneau x60"
                  % X60)
            print("     au lieu d en retirer un doublon.")
            print("Rien n a ete ecrit.")
            return 1
        q = lire(QUAD)
        if MARQUE not in q:
            print("KO : %s ne contient pas le panneau x60 recopie" % QUAD)
            print("     (marqueur '%s' absent). Appliquer" % MARQUE)
            print("     patch_panel_joindre.py d abord.")
            print("Rien n a ete ecrit.")
            return 1
        n60 = os.path.getsize(X60) if os.path.isfile(X60) else 0
        print("  %s contient bien le panneau x60 (%d caracteres)."
              % (QUAD, len(q)))
        print("  Economie attendue : %d caracteres, ~%d jetons par"
              % (n60, int(n60 / 3.6)))
        print("  question -- sans perdre une ligne.")

    # ---- deja applique : on relit la valeur au lieu de sortir -------
    dedans = exclus_ast(src)
    if dedans is not None:
        print("  deja patche -- _DOCS_EXCLUS = %r" % (dedans or set()))
        if dedans == voulu:
            print()
            print("Rien a faire -- deja dans l etat demande.")
            return 0
        rempl = ('{"panel_x60_onset.txt"}' if voulu else "set()")
        neuf = R_EXC.sub(lambda m: m.group(1) + rempl, src, count=1)
        if neuf == src:
            print("KO : _DOCS_EXCLUS present mais non remplacable.")
            print("Rien n a ete ecrit.")
            return 1
    else:
        if a.annuler:
            print("  _DOCS_EXCLUS absent -- rien a annuler.")
            return 0
        n = src.count(ANCRE)
        if n != 1:
            print("KO : %d occurrence(s) de la ligne _cibles/_vus,"
                  " il en faut 1." % n)
            print("Rien n a ete ecrit.")
            return 1
        neuf = src.replace(ANCRE, NEUVE, 1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1
    apres = exclus_ast(neuf)
    if apres != voulu:
        print("KO : apres modification _DOCS_EXCLUS = %r, attendu %r."
              % (apres, voulu))
        print("Rien n a ete ecrit.")
        return 1
    # Le reste du chargeur ne doit pas avoir bouge.
    for t in ("_DOCS_REPL", "_lire_doc", "_static_ctx", "_DOCS_MAX"):
        if neuf.count(t) != src.count(t):
            print("KO : %s n apparait plus le meme nombre de fois." % t)
            print("Rien n a ete ecrit.")
            return 1

    print()
    print("  _DOCS_EXCLUS -> %r" % (voulu or set()))
    print("Marche arriere : %s"
          % ("python %s" % os.path.basename(__file__) if a.annuler
             else "python %s --annuler" % os.path.basename(__file__)))
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DE price_action.py.")
    print("NE JAMAIS le lancer a la main sans PA_ROLE=panel : sans")
    print("elle, _run_trading est vrai et de vrais ordres partent.")
    print("Au demarrage, repl_web imprime la liste des documents")
    print("charges : panel_x60_onset.txt ne doit plus y figurer,")
    print("panel_quadruple.txt si.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    # L horodatage est a la seconde : deux passages dans la meme
    # seconde donnaient le MEME nom, et la seconde sauvegarde ecrasait
    # la premiere -- c est-a-dire l original. Vu sur banc d essai en
    # enchainant appliquer puis --annuler. On suffixe plutot que
    # d ecraser.
    base = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    sauve, k = base, 1
    while os.path.exists(sauve):
        sauve = "%s-%d" % (base, k)
        k += 1
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

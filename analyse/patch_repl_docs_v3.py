# -*- coding: utf-8 -*-
"""
patch_repl_docs_v3.py -- les panneaux d abord, et dire quand une source manque

  python patch_repl_docs_v3.py --essai
  python patch_repl_docs_v3.py

CE QU ON A CONSTATE LE 12/08 A 11h09

    Le REPL parle, lit ses documents, et les cite avec les bons chiffres.
    Mais interroge sur ce qu il voit, il repond :

        NOTES_c14_trail.md, NOTES_gel_v9.md, orderflow_2026-08-10_0408.txt

    Aucun des quatre panneaux exportes -- donc pas rails trades, pas
    rails range, pas le panneau 3 periodes. Exactement ce qu on voulait
    pouvoir lui demander.

LA CAUSE, MESUREE

    G:\\My Drive\\ScalpEA\\panels n est PAS le dossier de nos quatre
    exports. C est une archive alimentee automatiquement toutes les deux
    heures depuis le 10/08 : une soixantaine de fichiers,

        rails_trades_2026-08-11_1608.txt   80 563
        orderflow_2026-08-12_1008.txt      17 781
        ...

    plusieurs megaoctets. Nos panel_*.txt y sont noyes.

    Et le tri alphabetique acheve l affaire : "orderflow_" passe avant
    "panel_". Le chargeur avale donc les archives orderflow une par une,
    17 400 caracteres chacune, et epuise le plafond de 200 000 AVANT
    d atteindre la lettre p.

    Les tailles le confirment : notes\\ ne pese que 12 619 caracteres
    (6 747 + 5 872). Les ~187 000 restants sont partis en archives
    orderflow quasi identiques entre elles.

    Ce dossier appartient a autre chose. On cesse de le lire.

CE QUE FAIT CETTE VERSION

    a) UN DOSSIER panels\\ LOCAL, dans la stack, remplace celui du Drive.
       Il ne contiendra que ce qu on y met :

           python export_panels.py --dest panels

       Aucun montage, aucune session, aucun depot automatique par un
       tiers, aucun tri qui puisse nous doubler.

    b) L ARCHIVE DU DRIVE EST RETIREE de la liste. Si tu veux un jour y
       revenir, ajoute une ligne -- mais il faudra alors filtrer sur
       panel_*, sinon le meme piege se referme.

    c) LES PANNEAUX PASSENT DEVANT les notes. Si le plafond doit couper,
       il coupera la fin des notes, pas ce qu on est venu chercher.

    d) TOUTE SOURCE ABSENTE EST ECRITE au demarrage, avec son chemin.
       La v2 sautait une source introuvable EN SILENCE -- c est ce qui a
       rendu ce diagnostic si long. Defaut de ma part, corrige ici.

    e) DEDOUBLONNAGE PAR NOM DE FICHIER, au cas ou deux sources
       porteraient les memes noms.

CE QUE CA COUTE, EN CLAIR

    Plafonds inchanges : 100 000 caracteres par document, 200 000 au
    total. Avec l archive ecartee, tout tient :

        panel_rails_trades.txt   101 163  -> tronque a 100 000
        panel_orderflow.txt       21 305
        panel_rails_trois.txt     15 735
        panel_rails_post0508.txt  11 586
        NOTES_c14_trail.md         6 747
        NOTES_gel_v9.md            5 872
                                 --------
                                 ~161 000 caracteres, ~40 000 jetons
                                 A CHAQUE QUESTION

    panel_rails_trades.txt pese a lui seul 62 % de ce total, pour un
    dump ticket par ticket. Le panneau 3 periodes (15 735) donne la
    lecture agregee des memes tickets. Si la facture te gene, retire le
    gros du dossier : le reste tombe a ~15 000 jetons.

A APPLIQUER SUR UN repl_web.py DEJA PATCHE PAR patch_repl_docs (v2).
IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
PREND EFFET AU PROCHAIN DEMARRAGE DU 8095.
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
MARQUEUR = "_introuvables"

# ---------------------------------------------------------------- 1 : la liste
RE_LISTE = re.compile(
    r'^([ \t]*)_DOCS_REPL = \[[ \t]*\n'
    r'[ \t]*_os\.path\.join\(_ICI, "notes"\),[ \t]*\n'
    r'[ \t]*_os\.path\.join\(_ICI, "docs", "JOURNAL\.md"\),[ \t]*\n'
    r'[ \t]*r"G:\\My Drive\\ScalpEA\\panels",[ \t]*\n'
    r'[ \t]*\][ \t]*$',
    re.M)

LISTE = '''    # v3 : G:\\My Drive\\ScalpEA\\panels a ete RETIRE. Ce n est pas notre
    # dossier : une archive automatique y depose rails_trades_*.txt et
    # orderflow_*.txt toutes les deux heures, ~80 000 et ~17 400
    # caracteres piece. Trie alphabetiquement, "orderflow_" passe avant
    # "panel_" -- le plafond etait epuise avant d atteindre nos exports.
    # On lit un dossier LOCAL, qui ne contient que ce qu on y met :
    #     python export_panels.py --dest panels
    # Les panneaux passent devant les notes : si ca coupe, ca coupera
    # la fin des notes, pas ce qu on est venu chercher.
    _DOCS_REPL = [
        _os.path.join(_ICI, "panels"),
        _os.path.join(_ICI, "notes"),
        _os.path.join(_ICI, "docs", "JOURNAL.md"),
    ]'''

# ------------------------------------------------------------- 2 : la collecte
RE_BOUCLE = re.compile(
    r'^([ \t]*)_cibles = \[\][ \t]*\n'
    r'[ \t]*for _d in _DOCS_REPL:[ \t]*\n'
    r'[ \t]*if _os\.path\.isdir\(_d\):[ \t]*\n'
    r'[ \t]*for _n in sorted\(_os\.listdir\(_d\)\):[ \t]*\n'
    r'[ \t]*if _n\.lower\(\)\.endswith\(\("\.md", "\.txt"\)\):[ \t]*\n'
    r'[ \t]*_cibles\.append\(_os\.path\.join\(_d, _n\)\)[ \t]*\n'
    r'[ \t]*elif _os\.path\.isfile\(_d\):[ \t]*\n'
    r'[ \t]*_cibles\.append\(_d\)[ \t]*$',
    re.M)

BOUCLE = '''    # v3 : on note ce qu on ne trouve PAS. La v2 sautait une source
    # absente sans un mot -- c est ce qui a rendu le dossier du Drive
    # invisible pendant qu on croyait le lire.
    # Dedoublonnage par nom : le dossier local et celui du Drive portent
    # les memes fichiers, le premier trouve gagne.
    _cibles, _introuvables, _vus = [], [], set()
    for _d in _DOCS_REPL:
        if _os.path.isdir(_d):
            _avant = len(_cibles)
            for _n in sorted(_os.listdir(_d)):
                if _n.lower().endswith((".md", ".txt")) and _n.lower() not in _vus:
                    _vus.add(_n.lower())
                    _cibles.append(_os.path.join(_d, _n))
            if len(_cibles) == _avant:
                _introuvables.append(_d + " (rien de neuf a lire)")
        elif _os.path.isfile(_d):
            if _os.path.basename(_d).lower() not in _vus:
                _vus.add(_os.path.basename(_d).lower())
                _cibles.append(_d)
        else:
            _introuvables.append(_d + " (INTROUVABLE)")'''

# -------------------------------------------------------------- 3 : le rapport
RE_RAPPORT = re.compile(
    r'^([ \t]*)if _absents:[ \t]*\n'
    r'[ \t]*print\("\[repl_web\]   illisibles : %s" % ", "\.join\(_absents\)\)'
    r'[ \t]*$',
    re.M)

RAPPORT = '''    if _absents:
        print("[repl_web]   illisibles : %s" % ", ".join(_absents))
    if _introuvables:
        print("[repl_web]   SOURCES ABSENTES : %s" % " | ".join(_introuvables))'''


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def recale(bloc, ind):
    """Reindente un bloc ecrit a 4 espaces vers l indentation reelle."""
    return "\n".join(ind + l[4:] if l.startswith("    ") else (ind + l if l else "")
                     for l in bloc.split("\n"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1

    src, enc = lire(a.fichier)
    print("%s : %d lignes, encodage %s" % (a.fichier, src.count("\n") + 1, enc))

    if "_DOCS_REPL" not in src:
        print("KO : patch_repl_docs (v2) n est pas applique sur ce fichier.")
        return 1

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    # Les trois ancres, verifiees AVANT d ecrire quoi que ce soit.
    for nom, rx in (("la liste _DOCS_REPL", RE_LISTE),
                    ("la boucle de collecte", RE_BOUCLE),
                    ("le rapport de demarrage", RE_RAPPORT)):
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Le bloc de la v2 a du etre edite a la main.")
            print("Rien n a ete ecrit.")
            return 1

    neuf = src
    for rx, bloc in ((RE_LISTE, LISTE), (RE_BOUCLE, BOUCLE),
                     (RE_RAPPORT, RAPPORT)):
        ind = rx.findall(neuf)[0]
        ind = ind if isinstance(ind, str) else ind[0]
        neuf = rx.sub(lambda m, b=bloc, i=ind: recale(b, i), neuf, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print("trois ancres trouvees, une seule fois chacune.")
    print()
    print("Nouvel ordre de lecture :")
    print("    1. panels\\        (local, dans la stack)")
    print("    2. notes\\")
    print("    3. docs\\JOURNAL.md")
    print()
    print("RETIRE : G:\\My Drive\\ScalpEA\\panels -- archive automatique,")
    print("~60 fichiers, plusieurs Mo. Triee, elle epuisait le plafond")
    print("en archives orderflow avant d atteindre nos panel_*.txt.")
    print()
    print("Toute source absente sera ECRITE au demarrage, ce qui n etait")
    print("pas le cas avant.")

    if not os.path.isdir("panels"):
        print()
        print("A FAIRE : le dossier panels\\ n existe pas encore ici.")
        print("    python export_panels.py --dest panels")
        print("Sans ca le patch s applique, mais il n y aura rien a lire")
        print("dedans -- et il le dira au demarrage.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc).write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DU 8095.")
    print("Au demarrage, la ligne [repl_web] documents REPL : N charges")
    print("doit compter les panneaux. Si elle affiche SOURCES ABSENTES,")
    print("le chemin cite est celui qui manque -- plus de silence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

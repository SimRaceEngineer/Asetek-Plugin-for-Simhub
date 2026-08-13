# -*- coding: utf-8 -*-
"""
patch_repl_sources.py -- le JOURNAL et le panneau x60 avant le reste

  python patch_repl_sources.py --essai
  python patch_repl_sources.py

REMPLACE patch_repl_journal_dabord.py, qui ne traitait que la moitie
du probleme. Si tu as deja applique celui-la, celui-ci le complete.

CE QUE LE REPL A RECU LE 13/08 A 12:11, D APRES LUI-MEME

    familles.txt, gradient_tf.txt, horloge_regime.txt, meneur.txt,
    panel_orderflow.txt, panel_rails_post0508.txt,
    panel_rails_trades.txt

    Sept fichiers. Ni panel_x60_onset.txt, ni docs/JOURNAL.md. Pas
    tronques : ABSENTS. Interroge, il a repondu cinq fois « ABSENT DE
    MON CONTEXTE » plutot que d inventer -- le modele s est bien
    comporte, c est le contexte qui etait ampute.

    C est aussi l explication de sa stratégie orderflow du matin :
    elle etait juste au vu de ce qu il avait, et il n avait ni le gel,
    ni le panneau x60.

POURQUOI

    La liste chargee est exactement l ordre alphabetique du dossier
    `panels`, et panel_x60_onset.txt vient juste apres
    panel_rails_trades.txt -- lequel fait ~99 000 caracteres a lui
    seul, pour un plafond total de 200 000.

    La boucle coupe ainsi :

        if _total + len(_t) > _DOCS_MAX:
            _coupes.append(basename + " (plafond total)")
            break

    Un `break`, pas un `continue` : ce qui vient apres n est pas
    tronque, il n est pas lu. Et docs/JOURNAL.md etait le dernier
    chemin de _DOCS_REPL, donc encore plus loin dans la file.

CE QUE LE PATCH FAIT

    _DOCS_REPL devient :

        docs/JOURNAL.md                  <- le plus court, le plus dense
        panels/panel_x60_onset.txt       <- l observation en cours
        panels                           <- le reste, alphabetique
        notes

    Le dedoublonnage du chargeur rend ca sans risque :

        if _os.path.basename(_d).lower() not in _vus:

    Il porte sur le NOM de fichier, premier arrive gagne. Nommer
    panel_x60_onset.txt explicitement le charge tot ; le parcours du
    dossier `panels` le saute ensuite. Aucune duplication.

LE COUT, QU IL FAUT DIRE

    Le plafond est atteint : quelqu un DOIT sauter. En remontant
    24 ko (9 de journal + ~15 de panneau x60), c est le dernier
    fichier du dossier qui devient le candidat -- soit
    panel_rails_trades.txt, ~99 ko.

    C est un arbitrage, pas une optimisation. Il se defend : le
    panneau rails est deja resume dans panel_rails_post0508.txt, alors
    que le journal et le panneau x60 n existent nulle part ailleurs.
    Si tu veux tout, il faut relever _DOCS_MAX -- au prix de la
    latence, deja de 74 s sur une question longue.

QUAND CA PREND EFFET

    C est du code Python : relancer le python du panneau suffit, sa
    boucle le redemarre en deux secondes. Le wrapper cmd n a pas a
    etre touche -- contrairement au patch des variables
    d environnement, ou il fallait le tuer lui.

UNE ANCRE, verifiee unique, sous ses DEUX formes possibles (d origine,
ou deja passee par patch_repl_journal_dabord). IDEMPOTENT. Sauvegarde
horodatee. ast.parse, puis controle sur l ARBRE de l ORDRE des deux
premiers elements -- une liste mal ordonnee compile parfaitement, et
c est precisement l ordre qu on corrige.
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
MARQUEUR = "JOURNAL et x60 d abord"

# Deux formes acceptees : la liste d origine, et celle que
# patch_repl_journal_dabord laisse derriere lui.
RE_ORIGINE = re.compile(
    r'^([ \t]*)_DOCS_REPL = \[\n'
    r'([ \t]*)_os\.path\.join\(_ICI, "panels"\),\n'
    r'[ \t]*_os\.path\.join\(_ICI, "notes"\),\n'
    r'[ \t]*_os\.path\.join\(_ICI, "docs", "JOURNAL\.md"\),\n'
    r'[ \t]*\]$', re.M)

RE_DEJA = re.compile(
    r'^([ \t]*)_DOCS_REPL = \[\n'
    r'([ \t]*)_os\.path\.join\(_ICI, "docs", "JOURNAL\.md"\),\n'
    r'[ \t]*_os\.path\.join\(_ICI, "panels"\),\n'
    r'[ \t]*_os\.path\.join\(_ICI, "notes"\),\n'
    r'[ \t]*\]$', re.M)

NEUF = '''@I@# JOURNAL et x60 d abord. La boucle s ARRETE au plafond total
@I@# (break, plus bas) : ce qui vient apres n est pas tronque, il
@I@# n est pas lu. Le 13/08 a 12:11, le REPL a recu SEPT fichiers --
@I@# l ordre alphabetique de `panels` jusqu a panel_rails_trades.txt,
@I@# qui pese ~99 ko a lui seul. panel_x60_onset.txt, juste apres
@I@# dans l alphabet, et docs/JOURNAL.md, dernier chemin de la liste,
@I@# etaient absents. Interroge, le modele a repondu cinq fois
@I@# "ABSENT DE MON CONTEXTE" : il lisait juste, il lisait ampute.
@I@# Nommer panel_x60_onset.txt avant le dossier est sans risque : le
@I@# dedoublonnage porte sur le NOM, premier arrive gagne, donc le
@I@# parcours de `panels` le saute ensuite.
@I@# Le cout est assume : le plafond etant atteint, remonter 24 ko
@I@# fait sauter le dernier fichier du dossier. Le panneau rails est
@I@# deja resume dans panel_rails_post0508 ; le journal et le panneau
@I@# x60 n existent nulle part ailleurs.
@I@_DOCS_REPL = [
@J@_os.path.join(_ICI, "docs", "JOURNAL.md"),
@J@_os.path.join(_ICI, "panels", "panel_x60_onset.txt"),
@J@_os.path.join(_ICI, "panels"),
@J@_os.path.join(_ICI, "notes"),
@I@]'''


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

    trouve = None
    for nom, rx in (("d origine", RE_ORIGINE),
                    ("deja passee par patch_repl_journal_dabord", RE_DEJA)):
        n = len(rx.findall(src))
        if n == 1:
            trouve = (nom, rx)
            break
        if n > 1:
            print("KO : %d occurrences de la liste %s. Rien n a ete ecrit."
                  % (n, nom))
            return 1
    if trouve is None:
        print("KO : _DOCS_REPL n a aucune des deux formes attendues.")
        print("     Colle-moi les lignes autour de `_DOCS_REPL = [` :")
        print("     Select-String -Path repl_web.py -Pattern '_DOCS_REPL'"
              " -Context 2,8")
        print("Rien n a ete ecrit.")
        return 1
    print("Liste reconnue sous sa forme %s." % trouve[0])

    m = trouve[1].search(src)
    neuf = (src[:m.start()]
            + NEUF.replace("@I@", m.group(1)).replace("@J@", m.group(2))
            + src[m.end():])

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # C est l ORDRE qu on corrige, et une liste mal ordonnee compile
    # aussi bien. Le controle porte donc sur l arbre, sur les DEUX
    # premieres places, pas sur la simple presence des chemins.
    elts = None
    for nd in ast.walk(arbre):
        if not (isinstance(nd, ast.Assign) and isinstance(nd.value, ast.List)):
            continue
        if "_DOCS_REPL" not in [t.id for t in nd.targets
                                if isinstance(t, ast.Name)]:
            continue
        elts = nd.value.elts
    if not elts or len(elts) < 2:
        print("KO : _DOCS_REPL introuvable ou trop courte dans l arbre.")
        print("Rien n a ete ecrit.")
        return 1
    if "JOURNAL.md" not in ast.dump(elts[0]):
        print("KO : JOURNAL.md n est pas en 1re position. Rien n a ete ecrit.")
        return 1
    if "panel_x60_onset.txt" not in ast.dump(elts[1]):
        print("KO : panel_x60_onset.txt n est pas en 2e position.")
        print("Rien n a ete ecrit.")
        return 1
    print("Arbre verifie : JOURNAL.md en 1re place, panel_x60_onset.txt"
          " en 2e.")

    base = os.path.dirname(os.path.abspath(a.fichier))
    for rel in (("docs", "JOURNAL.md"), ("panels", "panel_x60_onset.txt")):
        f = os.path.join(base, *rel)
        if os.path.isfile(f):
            print("  %-28s %7d caracteres"
                  % ("/".join(rel),
                     len(io.open(f, encoding="utf-8",
                                 errors="replace").read())))
        else:
            print("  %-28s ABSENT -- il sera liste comme introuvable"
                  % "/".join(rel))

    print()
    print("Ces deux-la passent devant. Le dedoublonnage du chargeur")
    print("(par NOM de fichier, premier arrive gagne) fait que le")
    print("parcours du dossier `panels` sautera le panneau x60 ensuite :")
    print("aucune duplication.")
    print()
    print("COUT : le plafond etant atteint, remonter ~24 ko fait sauter")
    print("le dernier fichier du dossier -- panel_rails_trades.txt,")
    print("~99 ko. C est un arbitrage : ce panneau est deja resume dans")
    print("panel_rails_post0508.txt, le journal et le panneau x60 n ont")
    print("aucun equivalent. Pour tout garder, relever _DOCS_MAX, au")
    print("prix de la latence -- deja 74 s sur une question longue.")
    print()
    print("Prend effet en relancant le PYTHON du panneau : c est du code,")
    print("sa boucle le redemarre en deux secondes.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Rollback : copier le .bak par-dessus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

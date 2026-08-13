# -*- coding: utf-8 -*-
"""
patch_repl_journal_dabord.py -- le JOURNAL avant les panneaux

  python patch_repl_journal_dabord.py --essai
  python patch_repl_journal_dabord.py

LE PROBLEME

    repl_web.py charge ses documents dans cet ordre :

        _DOCS_REPL = [
            panels,
            notes,
            docs/JOURNAL.md,      <- dernier
        ]

    et coupe ainsi (l.166-168) :

        if _total + len(_t) > _DOCS_MAX:
            _coupes.append(basename + " (plafond total)")
            break

    La boucle S ARRETE au plafond. Ce qui vient apres n est pas
    tronque : il n est pas charge du tout.

    Le 13/08 : 175 000 gardes sur 201 430, avec deja
    panel_rails_trades.txt et panel_x60_onset.txt marques
    « (plafond total) ». Le commentaire du fichier l annonce
    (l.118-120) : le panel rails fait ~99 000 caracteres a lui seul.

    Deposer docs/JOURNAL.md ne suffisait donc pas : place en dernier,
    il etait le premier sacrifie. Le REPL aurait continue de proposer
    des strategies deja refutees, sans que rien ne le signale --
    l absence d une source ne ressemble pas a une erreur, elle
    ressemble a une source vide.

CE QUE LE PATCH FAIT

    Il met docs/JOURNAL.md EN TETE de la liste. Il est le plus court
    des trois (9 ko contre ~99 ko pour le seul panel rails) et le seul
    a porter ce qui a ete mesure puis ECARTE. Un panneau tronque reste
    lisible ; un journal absent laisse re-proposer l entonnoir
    orderflow que le gel V9 a deja rejete.

    Rien d autre ne change : ni le plafond, ni la troncature par
    fichier, ni le texte d en-tete, ni les sources.

CE QUI EST DEPLACE, CE QUI NE L EST PAS

    panels et notes gardent leur ordre relatif. Seul le JOURNAL passe
    devant. Le cout est reel et assume : ~9 000 caracteres de panneau
    en moins dans le contexte.

QUAND CA PREND EFFET

    Contrairement au patch des variables d environnement, celui-ci
    porte sur du CODE PYTHON : il suffit de relancer le python du
    panneau, sa boucle le redemarre en deux secondes. Le wrapper cmd
    n a pas besoin d etre touche.

UNE ANCRE, verifiee unique. IDEMPOTENT. Sauvegarde horodatee.
ast.parse avant ecriture, puis controle sur l arbre que JOURNAL.md est
bien le PREMIER element de la liste -- l ordre est tout l objet du
patch, et une liste dans le mauvais ordre compile parfaitement.
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
MARQUEUR = "JOURNAL d abord"

RE_LISTE = re.compile(
    r'^([ \t]*)_DOCS_REPL = \[\n'
    r'([ \t]*)_os\.path\.join\(_ICI, "panels"\),\n'
    r'[ \t]*_os\.path\.join\(_ICI, "notes"\),\n'
    r'[ \t]*_os\.path\.join\(_ICI, "docs", "JOURNAL\.md"\),\n'
    r'[ \t]*\]$', re.M)

NEUF = '''@I@# JOURNAL d abord. La boucle de chargement s ARRETE au plafond
@I@# total (break, plus bas) : ce qui vient apres n est pas tronque,
@I@# il n est pas charge. Le 13/08, 175 000 gardes sur 201 430 avec
@I@# deux panneaux deja marques "(plafond total)" -- le journal, en
@I@# dernier, n aurait jamais ete lu. Or c est le seul document qui
@I@# porte ce qui a ete mesure puis ECARTE : sans lui le REPL
@I@# re-propose l entonnoir orderflow que le gel V9 a rejete, et
@I@# rien ne le signale (une source absente ressemble a une source
@I@# vide). Il fait 9 ko contre ~99 ko pour le seul panel rails :
@I@# le cout est un panneau un peu plus rogne, ce qui reste lisible.
@I@_DOCS_REPL = [
@J@_os.path.join(_ICI, "docs", "JOURNAL.md"),
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

    n = len(RE_LISTE.findall(src))
    if n != 1:
        print("KO : %d occurrence(s) de _DOCS_REPL sous sa forme attendue,"
              " il en faut 1." % n)
        print("     La liste a peut-etre change depuis. Rien n a ete ecrit.")
        return 1

    m = RE_LISTE.search(src)
    neuf = (src[:m.start()]
            + NEUF.replace("@I@", m.group(1)).replace("@J@", m.group(2))
            + src[m.end():])

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # L ORDRE est tout l objet du patch, et une liste dans le mauvais
    # ordre compile parfaitement. On verifie donc sur l arbre que
    # JOURNAL.md est le PREMIER element -- pas seulement qu il est la.
    premier = None
    for nd in ast.walk(arbre):
        if not (isinstance(nd, ast.Assign) and isinstance(nd.value, ast.List)):
            continue
        noms = [t.id for t in nd.targets if isinstance(t, ast.Name)]
        if "_DOCS_REPL" not in noms:
            continue
        elts = nd.value.elts
        if not elts:
            continue
        premier = ast.dump(elts[0])
    if premier is None:
        print("KO : _DOCS_REPL introuvable dans l arbre. Rien n a ete ecrit.")
        return 1
    if "JOURNAL.md" not in premier:
        print("KO : JOURNAL.md n est pas le PREMIER element de _DOCS_REPL.")
        print("     C est tout l objet du patch, et une liste dans le")
        print("     mauvais ordre compile aussi bien. Rien n a ete ecrit.")
        return 1
    print("Arbre verifie : JOURNAL.md est le premier element de _DOCS_REPL.")

    jm = os.path.join(os.path.dirname(os.path.abspath(a.fichier)),
                      "docs", "JOURNAL.md")
    if os.path.isfile(jm):
        print("docs/JOURNAL.md present : %d caracteres."
              % len(io.open(jm, encoding="utf-8", errors="replace").read()))
    else:
        print("NOTE : docs/JOURNAL.md n existe pas encore. Le patch reste")
        print("       valable -- une source absente est simplement listee")
        print("       comme telle au demarrage.")

    print()
    print("Le JOURNAL passe devant panels et notes.")
    print("panels et notes gardent leur ordre relatif entre eux.")
    print()
    print("Cout assume : ~9 000 caracteres de panneau en moins dans le")
    print("contexte. Un panneau tronque reste lisible ; un journal")
    print("absent laisse re-proposer ce qui a deja ete ecarte.")
    print()
    print("Prend effet en relancant le PYTHON du panneau -- c est du code,")
    print("pas une variable d environnement. Sa boucle le redemarre en")
    print("deux secondes, le wrapper cmd n a pas a etre touche.")

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

# -*- coding: utf-8 -*-
"""
patch_repl_print.py -- aucun print de repl_web ne doit tuer le REPL

  python patch_repl_print.py --essai
  python patch_repl_print.py

CE QU ON A ETABLI

    diag_repl_ask.py, lance dans le dossier de la stack :

        passe 1 : sortie OUVERTE -> REUSSI
        passe 2 : sortie FERMEE  -> REUSSI

    Donc ask() n est pas en cause. Et les six documents se chargent :

        [repl_web] documents REPL : 6 charges (158900 caracteres)

    La difference avec le serveur est le MOMENT. Dans le diagnostic,
    _ensure_init() a tourne pendant la passe 1, sortie ouverte. Sur le
    8095, il tourne a la PREMIERE question -- et ses print lèvent,
    puisque la sortie du processus n est pas ecrivable (fenetre console
    fermee apres un Start-Process).

    Or ces print sont places AVANT _inited = True. L initialisation
    n aboutit donc jamais, et toutes les questions echouent, pour
    toujours, avec le meme message :

        repl ask error: I/O operation on closed file

CE QUE FAIT CE PATCH

    Il definit dans repl_web -- et dans ce seul module -- un print qui
    ne peut pas lever :

        def print(*_a, **_k):
            try:
                _bi.print(*_a, **_k)
            except Exception:
                pass

    Toutes les fonctions du module l utilisent automatiquement, y
    compris celles ecrites avant lui : Python resout les noms globaux a
    l appel, pas a la definition.

POURQUOI PAS "ENLEVER CE PRINT"

    Parce que le prochain print pose le meme piege. Le defaut n est pas
    ce message-la, c est qu un diagnostic puisse tuer ce qu il
    diagnostique. C est la troisieme fois aujourd hui : mon print dans
    _ctx_repl, puis ceux-ci. On corrige la classe, pas le cas.

CE QUE CA NE CHANGE PAS

    La portee est repl_web. Le reste du processus -- moteur, trailing
    SAR, gates -- garde le print normal. Aucun message n est supprime :
    quand la sortie est ecrivable, tout s affiche comme avant.

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
MARQUEUR = "_print_sur"

RE_ANCRE = re.compile(r'^import ai_master_agent as ai[ \t]*$', re.M)

NEUF = '''


# 12/08/2026 -- UN PRINT QUI NE PEUT PAS TUER LE REPL
#
# La sortie standard du 8095 n est pas toujours ecrivable : lance par
# Start-Process, il survit a la fermeture de sa fenetre console, et
# tout print leve alors "I/O operation on closed file".
#
# _ensure_init() imprime ce qu il a charge AVANT de poser _inited =
# True. Un print qui leve laissait donc l initialisation inachevee, et
# toutes les questions echouaient ensuite, definitivement.
#
# Un diagnostic ne doit jamais pouvoir casser ce qu il diagnostique.
# Portee : ce module seulement. Le moteur garde le print normal.
import builtins as _bi

_print_sur = True


def print(*_a, **_k):
    """print du module : ecrit si possible, se tait sinon. Jamais d erreur."""
    try:
        _bi.print(*_a, **_k)
    except Exception:
        pass'''


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


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

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    trouve = RE_ANCRE.findall(src)
    if len(trouve) != 1:
        print("KO : %d occurrence(s) de l ancre, il en faut 1." % len(trouve))
        print("Attendu, sans indentation :")
        print("    import ai_master_agent as ai")
        print("Rien n a ete ecrit.")
        return 1

    neuf = RE_ANCRE.sub(lambda m: m.group(0) + NEUF, src, count=1)

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # Post-condition : un seul print de module, au niveau du module.
    defs = [n for n in arbre.body
            if isinstance(n, ast.FunctionDef) and n.name == "print"]
    if len(defs) != 1:
        print("KO : %d definition(s) de print au niveau module, il en faut 1."
              % len(defs))
        print("Rien n a ete ecrit.")
        return 1

    print("ancre trouvee. print de module ajoute juste apres.")
    print()
    print("Effet : les print de repl_web n echouent plus jamais.")
    print("_ensure_init() atteindra _inited = True meme si la sortie")
    print("du processus est fermee -- c est ce qui bloquait toutes les")
    print("questions depuis 12h04.")
    print()
    print("Le moteur, lui, garde le print normal. Portee : ce module.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc).write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Redemarre le 8095.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

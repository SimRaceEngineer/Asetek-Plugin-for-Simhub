# -*- coding: utf-8 -*-
"""
patch_panel_boucle.py -- donne a panel_quadruple.py le mode --boucle

  python patch_panel_boucle.py --essai
  python patch_panel_boucle.py

POURQUOI

    Le gardien verifie qu un processus est VIVANT et le relance sinon.
    panel_quadruple.py, tel qu il a ete livre, genere son rapport et
    sort. Ajoute au gardien en l etat, il serait relance a chaque
    passe et le journal du gardien se remplirait d une ligne toutes
    les cinq minutes -- pour rien.

    Avec --boucle il reste en vie et se regenere lui-meme, comme
    papier_tf et x60_onset avec leur --loop. Le gardien le traite
    alors comme les autres services.

CE QUE LE PATCH FAIT, ET RIEN D AUTRE

    1. `import time`, dont la boucle a besoin.
    2. une ligne d usage dans la docstring.
    3. le bloc de lancement, qui retire --boucle d argv AVANT argparse
       et enveloppe main() dans une boucle.

    --boucle est retire d argv parce que c est une affaire de
    LANCEMENT, pas de rapport : le reste du script n a pas a le
    connaitre, et argparse le refuserait.

    Une passe qui echoue n interrompt pas la boucle. Sinon le
    processus mourrait, le gardien le relancerait, l erreur se
    reproduirait -- on aurait un cycle au lieu d un message.

TROIS ANCRES, chacune verifiee unique. IDEMPOTENT. Sauvegarde
horodatee. ast.parse, puis controle SUR L ARBRE que la boucle est bien
au niveau module et que main() n a pas ete touche.

Ce patch ne modifie qu un LECTEUR. Aucun ordre, aucun collecteur.
"""
import argparse
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "panel_quadruple.py"
MARQUEUR = "--boucle"

A1 = """import os
import sys
"""
N1 = """import os
import sys
import time
"""

A2 = """  python panel_quadruple.py --sortie panels/panel_quadruple.txt
"""
N2 = """  python panel_quadruple.py --sortie panels/panel_quadruple.txt
  python panel_quadruple.py --boucle 5        (service du gardien)
"""

A3 = '''if __name__ == "__main__":
    sys.exit(main())
'''
N3 = '''if __name__ == "__main__":
    # --boucle est retire d argv AVANT argparse : le mode boucle est
    # une affaire de lancement, pas de rapport, et le reste du script
    # n a pas a le connaitre. Le gardien peut ainsi le traiter comme
    # les autres services -- un processus qui reste en vie -- au lieu
    # de le relancer a chaque passe et d inonder son journal.
    _argv = sys.argv[1:]
    _min = 0
    if "--boucle" in _argv:
        _i = _argv.index("--boucle")
        try:
            _min = int(_argv[_i + 1])
        except (IndexError, ValueError):
            sys.stderr.write("KO : --boucle attend un nombre de minutes\\n")
            sys.exit(1)
        del _argv[_i:_i + 2]
        sys.argv = [sys.argv[0]] + _argv
    if _min > 0:
        while True:
            del _L[:]
            try:
                main()
            except Exception as e:
                # Un rapport qui echoue ne doit pas tuer la boucle :
                # le gardien relancerait, l erreur se reproduirait, et
                # on aurait un cycle au lieu d un message.
                sys.stderr.write("passe en echec : %s\\n" % e)
            time.sleep(_min * 60)
    sys.exit(main())
'''

ANCRES = ((A1, N1, "le bloc d imports"),
          (A2, N2, "la ligne d usage de la docstring"),
          (A3, N3, "le bloc de lancement"))

INTOUCHABLES = ("def main(", "def setup_de(", "def table4(",
                "def cellule(", "_L = []")


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

    neuf = src
    for anc, nouv, nom in ANCRES:
        n = neuf.count(anc)
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1
        neuf = neuf.replace(anc, nouv, 1)
    print("Trois ancres, chacune unique.")

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    for t in INTOUCHABLES:
        if src.count(t) != neuf.count(t):
            print("KO : %s n apparait plus le meme nombre de fois." % t)
            print("Rien n a ete ecrit.")
            return 1
    print("Intacts : main, setup_de, table4, cellule, _L.")

    # Posee dans une fonction, la boucle compilerait sans jamais
    # tourner -- et le gardien relancerait un processus qui sort
    # aussitot, toutes les cinq minutes, sans que rien ne le signale.
    dessus = False
    for noeud in arbre.body:
        if isinstance(noeud, ast.If):
            d = ast.dump(noeud)
            if "__main__" in d and "While" in d and "sleep" in d:
                dessus = True
    if not dessus:
        print("KO : la boucle n est pas au niveau module sous")
        print("     if __name__ -- elle ne tournerait jamais.")
        print("Rien n a ete ecrit.")
        return 1
    print("Arbre verifie : la boucle est au niveau module.")

    print()
    print("Ce que ca ajoute :")
    print("  --boucle N   regenere le panneau toutes les N minutes et")
    print("               reste en vie, pour que le gardien le traite")
    print("               comme un service et non comme un script mort")
    print()
    print("Sans argument, le comportement ne change pas : une passe,")
    print("puis sortie. Les scripts qui l appellent deja ne voient")
    print("aucune difference.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

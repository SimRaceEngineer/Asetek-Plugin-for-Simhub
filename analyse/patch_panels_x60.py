# -*- coding: utf-8 -*-
"""
patch_panels_x60.py -- panels_auto rafraichit aussi le panneau X60

  python patch_panels_x60.py --essai
  python patch_panels_x60.py

CE QU IL AJOUTE

    Un troisieme appel dans le cycle : x60_onset.py --rapport, qui
    regenere panels/panel_x60_onset.txt -- et avec lui le releve papier
    x10..x240, puisque les deux sont chaines.

    Ca remplace rafraichir_x60.py, le processus separe lance le 12/08 a
    minuit. Un processus de moins, et c est la direction generale.

DEUX DECISIONS QUI COMPTENT

    1. IL TOURNE MEME SI LA JOINTURE A ECHOUE.

       rails_join et export_panels sont enchaines : exporter sur un
       corpus non joint donnerait les panneaux de la veille, donc le
       cycle saute l export quand la jointure echoue. C est juste, et
       ca ne concerne pas le x60 : il ne lit que docs/x60_onset/
       events.jsonl et docs/papier_tf/trades.jsonl, que rails_join ne
       touche pas.

       Le lier a la jointure ferait disparaitre le panneau x60 a chaque
       incident sur les rails, sans aucune raison. L appel est donc
       place APRES le if/else, pas dedans.

    2. IL EST OPTIONNEL.

       Si x60_onset.py n est pas la, panels_auto le DIT au demarrage et
       continue. Refuser de demarrer priverait les quatre panneaux
       principaux de rafraichissement a cause d un cinquieme, ce qui
       serait un mauvais echange.

UNE LIMITE A CONNAITRE

    --dest ne s applique pas au panneau x60 : x60_onset.py ecrit dans
    le dossier panels/ calcule depuis SA propre position, pas depuis un
    argument. Avec --dest par defaut les deux coincident. Si tu changes
    --dest un jour, les quatre panneaux iront ailleurs et le x60 non --
    le patch l affiche au demarrage plutot que de te le laisser
    decouvrir.

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

CIBLE = "panels_auto.py"
MARQUEUR = "x60_onset.py"

RE_CHECK = re.compile(
    r'^([ \t]*)for f in \("rails_join\.py", "export_panels\.py"\):\n'
    r'[ \t]*if not os\.path\.isfile\(f\):\n'
    r'[ \t]*print\("KO : %s introuvable -- lance depuis le dossier de la"\n'
    r'[ \t]*" stack\." % f\)\n'
    r'[ \t]*return 1$', re.M)

RE_BANNIERE = re.compile(
    r'^([ \t]*)print\("rails_join puis export_panels, dans cet ordre\."\)$',
    re.M)

RE_BOUCLE = re.compile(
    r'^([ \t]*)print\("\[%s\] cycle %d  export SAUTE : la jointure a echoue,"\n'
    r'[ \t]*" un export ici afficherait le corpus de la veille\."\n'
    r'[ \t]*% \(maintenant\(\), n\)\)$', re.M)

CHECK = '''

@I@# x60_onset est OPTIONNEL. Son panneau est utile, mais son absence ne
@I@# doit pas priver les quatre autres de rafraichissement : refuser de
@I@# demarrer pour un cinquieme panneau serait un mauvais echange.
@I@x60 = os.path.isfile("x60_onset.py")'''

BANNIERE = '''@I@print("rails_join puis export_panels, dans cet ordre.")
@I@if x60:
@I@    print("puis x60_onset --rapport, qui regenere le panneau X60 et,")
@I@    print("avec lui, le releve papier x10..x240 qui y est chaine.")
@I@    if a.dest != DEST:
@I@        print("ATTENTION : --dest ne s applique PAS au panneau x60.")
@I@        print("x60_onset ecrit dans le dossier panels/ calcule depuis")
@I@        print("sa propre position. Les quatre autres iront dans %s."
@I@              % a.dest)
@I@else:
@I@    print("x60_onset.py absent : le panneau X60 ne sera pas rafraichi.")'''

# @I@ = l indentation du print d origine, DANS le else. @O@ = un cran
# en moins, donc APRES le if/else. Les confondre poserait l appel x60
# dans la branche d echec : il ne tournerait que quand la jointure rate,
# l exact inverse de ce qu on veut. C est arrive au premier essai.
BOUCLE = '''@I@print("[%s] cycle %d  export SAUTE : la jointure a echoue,"
@I@      " un export ici afficherait le corpus de la veille."
@I@      % (maintenant(), n))

@O@# HORS du if/else : le x60 ne lit que ses propres journaux, que
@O@# rails_join ne touche pas. Le lier a la jointure ferait disparaitre
@O@# son panneau a chaque incident sur les rails, sans aucune raison.
@O@if x60:
@O@    ok3, r3 = lancer(["x60_onset.py", "--rapport"], a.delai)
@O@    print("[%s] cycle %d  x60 + papier: %s"
@O@          % (maintenant(), n, r3 if ok3 else "ECHEC -- " + r3))'''


def pose(gabarit, indent):
    """@I@ = l indentation capturee par l ancre, @O@ = un cran de moins.
    Des jetons plutot qu un formatage % : les gabarits contiennent
    eux-memes du %s et du %d destines au fichier cible, les imbriquer
    les ferait manger."""
    return (gabarit.replace("@O@", indent[:-4] if len(indent) >= 4 else "")
            .replace("@I@", indent))


def _hors_du_else(arbre):
    """L appel x60 est-il FRERE du `if ok1:` et non son else ?

    On cherche le While de la boucle, on y prend le corps, et on verifie
    qu un `if x60:` s y trouve au meme niveau qu un `if` qui contient
    « export_panels ». Chercher dans le texte ne dirait rien : les deux
    placements produisent le meme code, indente differemment."""
    for n in ast.walk(arbre):
        if not isinstance(n, ast.While):
            continue
        corps = n.body
        a_export = any(isinstance(x, ast.If)
                       and "export_panels" in ast.dump(x) for x in corps)
        a_x60 = any(isinstance(x, ast.If)
                    and "x60_onset" in ast.dump(x)
                    and "export_panels" not in ast.dump(x) for x in corps)
        if a_export and a_x60:
            return True
    return False


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

    for nom, rx in (("le controle de presence", RE_CHECK),
                    ("la banniere", RE_BANNIERE),
                    ("la fin du cycle", RE_BOUCLE)):
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Le fichier n a pas la forme attendue. Rien n a ete ecrit.")
            return 1

    neuf = RE_CHECK.sub(lambda m: m.group(0) + pose(CHECK, m.group(1)),
                        src, count=1)
    neuf = RE_BANNIERE.sub(lambda m: pose(BANNIERE, m.group(1)),
                           neuf, count=1)
    neuf = RE_BOUCLE.sub(lambda m: pose(BOUCLE, m.group(1)), neuf, count=1)

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # Le controle qui compte : l appel x60 doit etre au meme niveau que
    # le `if ok1:`, pas dans sa branche else. Compiler ne suffit pas --
    # les deux versions compilent, et la mauvaise ne tourne que quand la
    # jointure echoue. On le verifie sur l arbre, pas sur le texte.
    if not _hors_du_else(arbre):
        print("KO : l appel a x60_onset s est pose DANS le else de la")
        print("jointure. Il ne tournerait que quand rails_join echoue.")
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Le cycle appellera x60_onset.py --rapport apres l export.")
    print("HORS du if/else : il tourne meme quand la jointure echoue,")
    print("parce qu il ne lit que ses propres journaux.")
    print()
    print("Optionnel : sans x60_onset.py, panels_auto le dit et continue.")
    print()
    print("Ensuite, tue rafraichir_x60.py -- il ferait double emploi :")
    print("  Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" |")
    print("    Where-Object CommandLine -like '*rafraichir_x60*' |")
    print("    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Redemarre panels_auto.py pour que ca prenne effet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

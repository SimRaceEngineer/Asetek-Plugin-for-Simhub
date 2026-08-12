# -*- coding: utf-8 -*-
"""
patch_repl_ctx_v2.py -- un avertissement ne doit jamais casser la question

  python patch_repl_ctx_v2.py --essai
  python patch_repl_ctx_v2.py

CE QUI S EST PASSE

    La v1 ajoutait un print() quand le contexte est tronque. Resultat au
    premier essai :

        [erreur] repl ask error: I/O operation on closed file

    La sortie standard du processus 8095 n est pas ecrivable -- il est
    lance par Start-Process, detache de la console. Mon print a donc
    leve, et la question entiere est tombee avec lui.

    C est ma faute, et c est une faute de conception, pas une coquille :
    un diagnostic ne doit jamais pouvoir casser ce qu il diagnostique.

CE QUE CETTE VERSION CORRIGE

    a) Le print devient best-effort : try / except / pass. Si la sortie
       est fermee, on perd le message, pas la question.

    b) LE MESSAGE PASSE DANS LE TEXTE. La marque de fin de contexte
       porte desormais les deux chiffres :

           [... contexte tronque : 175000 gardes sur 402913 ...]

       Elle va au modele, qui peut la citer. C est plus robuste qu une
       sortie console qu on ne lit jamais -- et ici, qu on ne peut meme
       pas ecrire.

CE QU ON APPREND AU PASSAGE

    Que l erreur ait eu lieu prouve que la troncature MORD : le contexte
    depasse 175 000 caracteres. Nos six documents n en font que ~159 400,
    donc ai._gather_static_context() -- patterns et replay -- en apporte
    beaucoup. Une fois ce patch pose, le chiffre exact sera dans la
    reponse de DeepSeek : il suffira de lui demander.

    Tant qu on ne connait pas ce total, inutile de deplacer le plafond au
    hasard. On mesure d abord.

S APPLIQUE SUR UN ai_master_repl.py DEJA PATCHE PAR patch_repl_ctx.py.
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

CIBLE = "ai_master_repl.py"
MARQUEUR = "_ctx_dit"

RE_CORPS = re.compile(
    r'^([ \t]*)print\("\[repl\] contexte tronque : %d -> %d caracteres"[ \t]*\n'
    r'[ \t]*% \(len\(s\), REPL_CTX_MAX\)\)[ \t]*\n'
    r'[ \t]*return s\[:REPL_CTX_MAX\] \+ '
    r'"\\n\\n\[\.\.\. contexte tronque, il manque la suite \.\.\.\]"[ \t]*$',
    re.M)

NEUF = '''    # 12/08 (v2) : le print de la v1 a casse la premiere question --
    # "I/O operation on closed file". Le 8095 est lance par
    # Start-Process, sa sortie standard n est pas ecrivable. Un
    # diagnostic ne doit jamais pouvoir casser ce qu il diagnostique.
    _ctx_dit = "[... contexte tronque : %d gardes sur %d ...]" % (
        REPL_CTX_MAX, len(s))
    try:
        print("[repl] " + _ctx_dit)
    except Exception:
        pass    # sortie fermee : on perd le message, pas la question
    # Le meme texte part AUSSI dans le contexte, ou le modele peut le
    # citer. Plus fiable qu une console qu on ne lit pas.
    return s[:REPL_CTX_MAX] + "\\n\\n" + _ctx_dit'''


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

    if "REPL_CTX_MAX" not in src:
        print("KO : patch_repl_ctx.py n est pas applique sur ce fichier.")
        return 1

    trouve = RE_CORPS.findall(src)
    if len(trouve) != 1:
        print("KO : %d occurrence(s) du corps de _ctx_repl, il en faut 1."
              % len(trouve))
        print("Rien n a ete ecrit.")
        return 1

    ind = trouve[0]
    corps = "\n".join(ind + l[4:] if l.startswith("    ") else (ind + l if l else "")
                      for l in NEUF.split("\n"))
    neuf = RE_CORPS.sub(lambda m: corps, src, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print("corps de _ctx_repl trouve : indentation %d espaces" % len(ind))
    print()
    print("Le print devient best-effort. La question ne peut plus tomber")
    print("a cause de lui.")
    print()
    print("Que la v1 ait plante prouve que la troncature MORD :")
    print("le contexte depasse 175 000 caracteres. Apres redemarrage,")
    print("demande a DeepSeek de citer la ligne")
    print("    [... contexte tronque : X gardes sur Y ...]")
    print("et on saura enfin ce que pese _gather_static_context().")

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

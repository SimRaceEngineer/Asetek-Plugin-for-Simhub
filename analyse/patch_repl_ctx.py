# -*- coding: utf-8 -*-
"""
patch_repl_ctx.py -- le plafond qui coupait 5 documents sur 6, en silence

  python patch_repl_ctx.py --essai
  python patch_repl_ctx.py

CE QU ON CHERCHAIT DEPUIS 11h

    Le REPL chargeait bien ses six documents -- panels\\ local lu, export
    a 11:18:51 confirme par DeepSeek lui-meme. Mais interroge, il ne
    voyait que panel_orderflow.txt.

    La cause est ici, dans ai_master_repl.build_system_message :

        + "\\n\\n" + static_ctx[:25000]

    25 000 caracteres. panel_orderflow.txt en pese 20 453 : il rentre,
    et les trois autres panneaux plus les deux notes tombent. Sans un
    mot.

    C est aussi pourquoi les notes passaient AVANT ce matin : a elles
    deux elles ne font que 12 619 caracteres. Le plafond ne se voyait
    pas tant qu on restait petit.

CE QUE FAIT CE PATCH

    a) Le plafond passe a 175 000 caracteres. Nos six documents en font
       ~159 400 ; la marge laisse la place au snapshot JSON qui suit.

    b) LA TRONCATURE S ECRIT. Quand elle mord, le processus imprime

           [repl] contexte tronque : 210000 -> 175000 caracteres

       C est le vrai correctif. Un plafond n est pas un bug ; un plafond
       muet en est un, et c est le troisieme de la journee apres la
       source absente sautee sans un mot et le dossier du Drive avale en
       archives. Meme faute, meme remede : dire ce qu on jette.

    c) Le texte tronque porte une marque explicite en fin de contexte,
       pour que le modele sache qu il lui manque quelque chose plutot
       que de raisonner sur un document coupe net.

LE COUT, QU IL FAUT REGARDER

    175 000 caracteres, c est environ 44 000 jetons de message systeme
    PAR QUESTION, contre 6 000 aujourd hui. Avec nos six documents on
    sera a ~40 000. C est le prix pour qu il voie les panneaux ; si ca
    te gene, retire panel_rails_trades.txt de panels\\ (99 150 a lui
    seul) et redemarre : on retombe a ~15 000.

CE QUE CA NE TOUCHE PAS

    build_system_message n est appelee que par le REPL -- repl_web.py
    ligne 185 et le main() console de ce meme fichier. Le cycle de
    trading ne passe pas par la. Aucun trader, aucun closer.

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
MARQUEUR = "REPL_CTX_MAX"

RE_DEF = re.compile(r'^def build_system_message\(static_ctx, ctx\):[ \t]*$', re.M)

RE_COUPE = re.compile(
    r'^([ \t]*)\+ "\\n\\n" \+ static_ctx\[:25000\][ \t]*$', re.M)

AIDE = '''# 12/08/2026 -- le plafond du contexte statique du REPL.
#
# Il valait 25000 en dur dans build_system_message. Le jour ou on a
# donne les panneaux au REPL, panel_orderflow.txt (20 453) passait et
# les cinq autres documents tombaient -- sans un mot nulle part. On a
# cherche la cause pendant deux heures.
#
# Le chiffre n est pas le correctif. Le correctif, c est qu il PARLE.
REPL_CTX_MAX = 175000


def _ctx_repl(static_ctx):
    """Tronque le contexte statique, et le dit sur la sortie du processus."""
    s = static_ctx or ""
    if len(s) <= REPL_CTX_MAX:
        return s
    print("[repl] contexte tronque : %d -> %d caracteres"
          % (len(s), REPL_CTX_MAX))
    return s[:REPL_CTX_MAX] + "\\n\\n[... contexte tronque, il manque la suite ...]"


'''


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

    for nom, rx in (("def build_system_message", RE_DEF),
                    ('la ligne + "\\n\\n" + static_ctx[:25000]', RE_COUPE)):
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1

    ind = RE_COUPE.findall(src)[0]

    neuf = RE_DEF.sub(lambda m: AIDE + m.group(0), src, count=1)
    neuf = RE_COUPE.sub(lambda m: ind + '+ "\\n\\n" + _ctx_repl(static_ctx)',
                        neuf, count=1)
    # La docstring de la fonction annonce elle aussi [:25000]. Une
    # docstring qui ment est un piege pour le prochain qui lira ; on la
    # corrige, mais son absence n est pas une raison de refuser le patch.
    neuf = neuf.replace(
        "system = PRO_SYSTEM_PROMPT + static_ctx[:25000] (comme le cycle Pro)",
        "system = PRO_SYSTEM_PROMPT + _ctx_repl(static_ctx) (cf REPL_CTX_MAX)")

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    if RE_COUPE.search(neuf):
        print("KO : la coupe a 25000 est toujours dans le code.")
        print("Rien n a ete ecrit.")
        return 1

    print("les deux ancres sont uniques.")
    print()
    print("Plafond : 25 000 -> 175 000 caracteres.")
    print("Nos six documents en font ~159 400, donc tout passe.")
    print("Quand ca coupera, le processus ecrira :")
    print("    [repl] contexte tronque : X -> 175000 caracteres")
    print()
    print("COUT : ~40 000 jetons de message systeme PAR QUESTION,")
    print("contre ~6 000 aujourd hui. Pour revenir en arriere, retire")
    print("panel_rails_trades.txt de panels\\ (99 150 a lui seul).")

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

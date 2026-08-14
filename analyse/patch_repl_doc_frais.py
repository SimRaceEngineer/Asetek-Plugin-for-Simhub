# -*- coding: utf-8 -*-
r"""
patch_repl_doc_frais.py -- un document relu A CHAQUE QUESTION du REPL

  python patch_repl_doc_frais.py --essai
  python patch_repl_doc_frais.py
  python patch_repl_doc_frais.py --retire        (marche arriere)

LE PROBLEME

    Les documents du REPL sont charges UNE FOIS, dans `_static_ctx`, au
    demarrage de price_action.py. C est voulu : ils pesent 385 000
    caracteres et les relire a chaque question serait absurde.

    Mais la carte des profils change quand on la regenere, et un
    redemarrage du panneau pour rafraichir un fichier de 30 Ko est une
    interruption disproportionnee -- surtout sur une machine ou le
    panneau est supervise et ou l on ne relance rien a la main.

CE QUE FAIT LE PATCH

    Il ajoute UN document, et un seul, relu au moment de la question :

        cartes/panel_profils.txt

    Concretement, la ligne qui passe le contexte fige au constructeur
    de message systeme devient

        (_static_ctx or "") + _doc_frais()

    et `_doc_frais()` lit le fichier a chaque appel. Le surcout est une
    lecture disque de ~30 Ko par question -- invisible a cote des 385 000
    caracteres deja transmis et des dizaines de secondes de raisonnement.

POURQUOI cartes/ ET SURTOUT PAS notes/

    Le chargeur du demarrage balaie `panels/` et `notes/`. Un fichier
    depose la serait charge DEUX fois : une fois fige au boot, une fois
    frais a la question. Le modele verrait deux versions du meme tableau
    avec des chiffres differents, sans savoir laquelle croire.

    `cartes/` n est balaye par personne. C est deja le dossier de sortie
    par defaut de profils_croises.py -- donc

        python profils_croises.py --actif TOUS

    suffit a rafraichir, et la question suivante voit le nouveau texte.
    Aucun redemarrage.

    Si un NOTES_carte_profils.txt a ete depose dans notes/, il faut le
    supprimer : sinon la version figee coexiste avec la fraiche.

LE GARDE-FOU DE TAILLE

    Le document frais est tronque a --max caracteres (200 000 par
    defaut) et le patch le dit dans la sortie. Un fichier qui gonflerait
    sans limite pousserait le contexte au-dela de ce que le modele
    accepte, et l erreur arriverait en pleine question, pas ici.

OU LE CODE EST INSERE

    La fonction generee est ajoutee A LA FIN du fichier. Python resout
    les noms globaux a l APPEL, pas a la definition : une fonction
    definie en bas est parfaitement visible depuis une fonction ecrite
    plus haut. Ca evite de deviner un point d insertion au milieu d un
    fichier de 608 lignes qu on ne connait pas par coeur.

    Et elle n emprunte AUCUN nom au module : ses imports sont locaux.
    Le 14/08 a 21:18, un patch a fait tomber la page en ecrivant
    `_os.environ` apres avoir "verifie" que os etait importe -- avec
    ast.walk, qui descend dans les fonctions.

UNE ANCRE, verifiee unique. REJOUABLE dans les deux sens. ast.parse et
controle AST. Sauvegarde horodatee, suffixee en cas de collision.

Ne prend effet qu au prochain demarrage de price_action.py -- JAMAIS a
la main sans PA_ROLE=panel.
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
DOC = "cartes/panel_profils.txt"
MAXC = 200000

# L ancre : le contexte fige, LA OU IL EST PASSE au constructeur du
# message systeme -- et nulle part ailleurs.
#
# `_static_ctx or ""` apparait DEUX fois dans repl_web.py : ligne 204,
# ou le contexte est construit (`_static_ctx = (_static_ctx or "") + ...`),
# et ligne 311, ou il est consomme. Remplacer la premiere ferait relire
# le document a la construction, c est-a-dire une seule fois -- soit
# exactement ce qu on veut eviter, et sans que rien ne le signale.
#
# On ancre donc sur `_static_ctx or "", ctx` : la virgule suivie de ctx
# n existe qu au site d appel.
R_ANCRE = re.compile(r'_static_ctx or "", ctx')
MIEN = "_ctx_plus_frais(), ctx"


def bloc(doc, maxc):
    return '''

# ---------------------------------------------------------------------
# 15/08 : un document relu A CHAQUE QUESTION.
#
# `_static_ctx` est construit une fois au demarrage : c est bien pour
# 385 000 caracteres de panneaux, c est genant pour la carte des
# profils, qui change des qu on la regenere. Ce document-ci, et lui
# seul, est relu a la question.
#
# Il vit dans cartes/ et NON dans notes/ : le chargeur du demarrage
# balaie notes/, et le fichier y serait charge deux fois -- une version
# figee et une fraiche, avec des chiffres differents.
#
# Imports LOCAUX a dessein : cette fonction n emprunte aucun nom au
# module. Un patch du 14/08 a fait tomber la page en supposant qu un
# nom existait au niveau ou il ecrivait.
_DOC_FRAIS = %r
_DOC_FRAIS_MAX = %d


def _doc_frais():
    """Le contenu du document frais, ou "" s il n existe pas.

    Toute erreur de lecture rend "" : une carte absente ne doit jamais
    empecher le REPL de repondre."""
    import io as _i
    import os as _o
    try:
        if not _o.path.isfile(_DOC_FRAIS):
            return ""
        t = _i.open(_DOC_FRAIS, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""
    if not t.strip():
        return ""
    coupe = ""
    if len(t) > _DOC_FRAIS_MAX:
        t = t[:_DOC_FRAIS_MAX]
        coupe = " (TRONQUE a %%d caracteres)" %% _DOC_FRAIS_MAX
    return ("\\n\\n===== %%s -- relu a l instant%%s =====\\n"
            "Ce document est regenere hors ligne ; s il contredit un\\n"
            "panneau plus ancien du contexte, c est lui qui fait foi.\\n"
            "%%s\\n") %% (_DOC_FRAIS, coupe, t)


def _ctx_plus_frais():
    """Le contexte fige, plus le document frais."""
    return (_static_ctx or "") + _doc_frais()
''' % (doc, maxc)


def lire(c):
    return io.open(c, encoding="utf-8", errors="replace").read()


def sauver(c, t):
    base = "%s.bak-%s" % (c, datetime.now().strftime("%Y%m%d-%H%M%S"))
    s, k = base, 1
    while os.path.exists(s):
        s = "%s-%d" % (base, k)
        k += 1
    shutil.copy2(c, s)
    io.open(c, "w", encoding="utf-8").write(t)
    print("Sauvegarde : %s" % s)


def defini(src, nom):
    """La fonction est-elle definie au NIVEAU MODULE ? On regarde le
    corps du module, pas ast.walk -- une fonction imbriquee portant le
    meme nom ne compte pas. C est exactement l erreur du 14/08."""
    try:
        arbre = ast.parse(src)
    except SyntaxError:
        return None
    return any(isinstance(n, ast.FunctionDef) and n.name == nom
               for n in arbre.body)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--doc", default=DOC,
                   help="le document relu a chaque question")
    p.add_argument("--max", type=int, default=MAXC, dest="maxc")
    p.add_argument("--essai", action="store_true")
    p.add_argument("--retire", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = lire(a.fichier)
    n0 = src.count("\n") + 1
    print("%s : %d lignes" % (a.fichier, n0))

    pose = defini(src, "_ctx_plus_frais")
    if pose is None:
        print("KO : %s ne compile pas AVANT modification." % a.fichier)
        print("     Je ne touche pas a un fichier dans cet etat.")
        return 1

    if a.retire:
        if not pose:
            print("Le document frais n est pas installe -- rien a retirer.")
            return 0
        m = re.search(r"\n\n# -{69}\n# 15/08 : un document relu A CHAQUE"
                      r" QUESTION\..*?return \(_static_ctx or \"\"\)"
                      r" \+ _doc_frais\(\)\n", src, re.S)
        if not m:
            print("KO : le bloc n est pas retrouve tel quel.")
            print("     Il a ete edite depuis. Reprends une sauvegarde")
            print("     repl_web.py.bak-*.")
            return 1
        # "" et non "\n" : le bloc commence deja par ses deux sauts
        # de ligne. Le remplacer par un saut en laissait un de trop,
        # et la marche arriere ne rendait pas un fichier identique.
        neuf = src.replace(m.group(0), "", 1)
        neuf = neuf.replace(MIEN, '_static_ctx or "", ctx', 1)
    else:
        if pose:
            print("Le document frais est deja installe -- rien a faire.")
            print("Pour le retirer : --retire")
            return 0
        n = len(R_ANCRE.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de `_static_ctx or \"\", ctx`,"
                  " il en faut 1." % n)
            print("     C est le SITE D APPEL du constructeur de message")
            print("     systeme. La construction du contexte, elle, porte")
            print("     `(_static_ctx or \"\") + ...` et ne doit pas bouger.")
            print("Rien n a ete ecrit.")
            return 1
        neuf = R_ANCRE.sub(MIEN, src, count=1) + bloc(a.doc, a.maxc)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    attendu = not a.retire
    for nom in ("_doc_frais", "_ctx_plus_frais"):
        if defini(neuf, nom) is not attendu:
            print("KO : %s defini = %r, attendu %r."
                  % (nom, defini(neuf, nom), attendu))
            print("Rien n a ete ecrit.")
            return 1
    if neuf.count(MIEN) != (1 if attendu else 0):
        print("KO : %s apparait %d fois." % (MIEN, neuf.count(MIEN)))
        print("Rien n a ete ecrit.")
        return 1

    print()
    if a.retire:
        print("  document frais RETIRE ; le contexte redevient fige")
    else:
        print("  document frais : %s" % a.doc)
        print("  relu a chaque question, tronque a %d caracteres" % a.maxc)
        print("  le reste du contexte reste fige au demarrage")
        print("  regenerer : python profils_croises.py --actif TOUS")
        print("Marche arriere : --retire")
        if os.path.isdir("notes"):
            doubles = [f for f in os.listdir("notes")
                       if "carte" in f.lower() or "profils" in f.lower()]
            if doubles:
                print()
                print("  ATTENTION : notes\\%s existe." % doubles[0])
                print("  Il serait charge FIGE au demarrage en plus de la")
                print("  version fraiche -- deux tableaux contradictoires")
                print("  dans le meme contexte. A supprimer.")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DE price_action.py.")
    print("NE JAMAIS le lancer a la main sans PA_ROLE=panel.")
    print("Ensuite, plus aucun redemarrage n est necessaire pour")
    print("rafraichir ce document : regenerer suffit.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauver(a.fichier, neuf)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

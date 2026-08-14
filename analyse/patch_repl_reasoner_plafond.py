# -*- coding: utf-8 -*-
"""
patch_repl_reasoner_plafond.py -- le 8000 qui rendait des reponses vides

  python patch_repl_reasoner_plafond.py --essai
  python patch_repl_reasoner_plafond.py
  python patch_repl_reasoner_plafond.py --jetons 60000
  python patch_repl_reasoner_plafond.py --jetons 8000      (marche arriere)

CE QUI S EST PASSE, LE 14/08 A 21:10

    (vide / completion=8000/8000 PLAFOND ATTEINT | prompt=205719)

    130 secondes de raisonnement, 8 000 jetons consommes, reponse
    VIDE. Sur un modele de raisonnement, `max_tokens` couvre le
    RAISONNEMENT ET la reponse dans la meme enveloppe : le budget est
    parti en reflexion, il n en restait rien pour ecrire.

DEUX PATCHES QUI SE DEFONT -- et ils sont de moi tous les deux

    patch_council_plafond a porte COUNCIL_MAX_TOKENS a 60000 le matin
    du 14/08. Vrai, verifie, inscrit au journal.

    patch_repl_modeles a introduit, la meme journee, un dictionnaire
    REPL_MAX_TOKENS PROPRE AU REPL avec 8000 ECRIT EN DUR -- et c est
    lui que la ligne d appel consulte. Le REPL n a jamais vu les
    60000.

    Le commentaire laisse au-dessus dit meme : "8000 est la valeur de
    COUNCIL_MAX_TOKENS du module -- on revient simplement au defaut".
    C etait exact a la minute ou il a ete ecrit. Ca a cesse de l etre
    l heure suivante. Le commentaire est reste, la valeur a diverge,
    et rien dans l un ou l autre fichier ne pouvait le montrer.

    C est la raison pour laquelle ce patch ne remplace PAS un nombre
    par un autre nombre.

CE QUE FAIT LE PATCH

    REPL_MAX_TOKENS lit desormais une variable d environnement avec un
    defaut explicite, exactement comme COUNCIL_SHADOW_MAX_TOKENS :

        "deepseek_reasoner": _plafond_reasoner()

    ou la fonction lit REPL_REASONER_MAX_TOKENS et retombe sur le
    defaut. Deux constantes jumelles qui divergent en silence, c est
    ce qui vient de couter une soiree : on en supprime une.

POURQUOI 32000 ET PAS 60000

    Sur un raisonneur, max_tokens couvre le raisonnement ET la
    reponse. 32000 est ce qui a ete demande ("obtenir une reponse meme
    de 30000"). Monter a 60000 se fait en une commande le jour ou
    32000 se revele court -- mais un palier qu on leve en connaissance
    de cause vaut mieux qu un chiffre confortable qui masque la
    surprise suivante.

    La marche arriere est --jetons 8000, et elle est exacte : le
    patch imprime la valeur PRECEDENTE, pas une valeur supposee. Un
    autre patch de la journee annoncait une marche arriere codee en
    dur ; corrige aussi.

UNE ANCRE, verifiee unique. REJOUABLE dans les deux sens. ast.parse et
controle AST de la valeur obtenue. Sauvegarde horodatee, suffixee si
collision.

Ce patch ne touche qu un LECTEUR. Aucun ordre, aucun collecteur.
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
VAR = "REPL_REASONER_MAX_TOKENS"

# L etat d origine, tel que patch_repl_modeles l a laisse.
A_DUR = ('REPL_MAX_TOKENS = {"deepseek": 3000, "deepseek_reasoner": 8000}')

# Les deux lignes de commentaire qui precedent. Elles disent "8000 est
# la valeur de COUNCIL_MAX_TOKENS ; on revient simplement au defaut" --
# vrai a la minute ou c a ete ecrit, faux l heure suivante quand l autre
# patch a porte COUNCIL a 60000. Les laisser en place ferait cohabiter
# deux commentaires qui se contredisent au-dessus de la meme valeur.
# On les remplace quand on les trouve ; sinon on ne touche que le code.
A_COMM = (
    '# 2.5-flash -- "brule le budget en reflexion et rend vide". 8000 est la\n'
    "# valeur de COUNCIL_MAX_TOKENS ; on revient simplement au defaut.\n")

# Une fois patche, la valeur se relit par le NOM et non par le chiffre
# -- c est ce qui rend --jetons 8000 possible apres coup.
R_DEF = re.compile(
    r'(_REASONER_DEFAUT\s*=\s*)(\d+)')


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


def bloc(n):
    return (
        '# 14/08 21:10 : "(vide / completion=8000/8000 PLAFOND ATTEINT |\n'
        '# prompt=205719)". 130 s de raisonnement, reponse VIDE. Sur un\n'
        "# raisonneur, max_tokens couvre le RAISONNEMENT ET la reponse :\n"
        "# le budget est parti en reflexion, il n en restait rien pour\n"
        "# ecrire.\n"
        "#\n"
        "# Le 8000 etait ECRIT EN DUR ici alors que patch_council_plafond\n"
        "# avait porte COUNCIL_MAX_TOKENS a 60000 le matin meme. Deux\n"
        "# constantes jumelles, une seule levee, aucune facon de le voir\n"
        "# depuis l un ou l autre fichier. On supprime la jumelle : la\n"
        "# valeur se regle par variable d environnement, defaut explicite.\n"
        "_REASONER_DEFAUT = %d\n"
        "\n"
        "\n"
        "def _plafond_reasoner():\n"
        '    """Le plafond de completion du raisonneur. Variable d\n'
        "    environnement %s, defaut _REASONER_DEFAUT.\n"
        "\n"
        "    L import est LOCAL a dessein. Une premiere version utilisait\n"
        "    le module os du niveau superieur ; repl_web ne l importe que\n"
        "    DANS une fonction, et la page est tombee sur `name '_os' is\n"
        "    not defined` au chargement. Importer ici rend la fonction\n"
        "    independante de ce que le module contient.\n"
        "\n"
        "    Une valeur illisible retombe sur le defaut plutot que de\n"
        '    casser la page."""\n'
        "    import os as _o\n"
        "    try:\n"
        '        return int(_o.environ.get("%s", _REASONER_DEFAUT))\n'
        "    except (TypeError, ValueError):\n"
        "        return _REASONER_DEFAUT\n"
        "\n"
        "\n"
        'REPL_MAX_TOKENS = {"deepseek": 3000,\n'
        '                   "deepseek_reasoner": _plafond_reasoner()}'
    ) % (n, VAR, VAR)


def valeur_ast(src):
    """Rend _REASONER_DEFAUT lu dans l AST, ou None."""
    try:
        arbre = ast.parse(src)
    except SyntaxError:
        return None
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id == "_REASONER_DEFAUT"
                and isinstance(n.value, ast.Constant)):
            return n.value.value
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--jetons", type=int, default=32000)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if a.jetons < 1000:
        print("KO : --jetons %d est absurde." % a.jetons)
        return 1
    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = lire(a.fichier)
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    # LE GARDE-FOU QUI A ECHOUE, garde ici pour memoire.
    #
    # La version precedente cherchait sous quel nom os etait importe et
    # ecrivait `os.environ` ou `_os.environ` en consequence. Elle
    # utilisait ast.walk, qui descend DANS les fonctions : elle a trouve
    # `import os as _os` a l interieur de _ensure_init() et en a conclu
    # que _os existait au niveau module. Il n y existe pas. La page est
    # tombee sur `name '_os' is not defined` des le chargement.
    #
    # Le controle etait juste dans son intention et faux dans sa portee :
    # il verifiait que os etait importe QUELQUE PART, pas LA OU J ECRIS.
    #
    # Il n y a plus rien a verifier : _plafond_reasoner importe os
    # elle-meme. On se contente de dire ce qu on voit au niveau module.
    arbre0 = ast.parse(src)
    haut = [al.asname or al.name
            for n in arbre0.body if isinstance(n, ast.Import)
            for al in n.names if al.name == "os"]
    print("  os au niveau module : %s"
          % (", ".join(haut) if haut else "ABSENT -- sans importance,"
             " la fonction generee l importe elle-meme"))

    avant = valeur_ast(src)
    if avant is not None:
        print("  deja patche -- _REASONER_DEFAUT = %d." % avant)
        if avant == a.jetons:
            print()
            print("Rien a faire -- deja a la valeur demandee.")
            return 0
        neuf = R_DEF.sub(lambda m: m.group(1) + str(a.jetons), src, count=1)
        if neuf == src:
            print("KO : _REASONER_DEFAUT present mais non remplacable.")
            print("Rien n a ete ecrit.")
            return 1
    else:
        n = src.count(A_DUR)
        if n != 1:
            print("KO : %d occurrence(s) de la ligne REPL_MAX_TOKENS"
                  " d origine, il en faut 1." % n)
            print("     Attendu exactement :")
            print("     %s" % A_DUR)
            print("Rien n a ete ecrit.")
            return 1
        if src.count(A_COMM + A_DUR) == 1:
            neuf = src.replace(A_COMM + A_DUR, bloc(a.jetons), 1)
            print("  le commentaire perime au-dessus est remplace lui")
            print("  aussi -- il annoncait 8000 comme etant la valeur de")
            print("  COUNCIL_MAX_TOKENS, qui vaut 60000 depuis ce matin.")
        else:
            neuf = src.replace(A_DUR, bloc(a.jetons), 1)
            print("  ATTENTION : le commentaire perime au-dessus n a pas")
            print("  ete trouve tel quel, il reste en place. Il annonce")
            print("  8000 comme la valeur de COUNCIL_MAX_TOKENS -- c est")
            print("  faux depuis ce matin. A relire a la main.")

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1
    obtenu = valeur_ast(neuf)
    if obtenu != a.jetons:
        print("KO : apres modification _REASONER_DEFAUT = %r." % obtenu)
        print("Rien n a ete ecrit.")
        return 1
    for t in ("REPL_MAX_TOKENS", "_mt = REPL_MAX_TOKENS.get(mk, 3000)"):
        if neuf.count(t) != src.count(t):
            print("KO : %s apparait %d fois, %d avant."
                  % (t, neuf.count(t), src.count(t)))
            print("Rien n a ete ecrit.")
            return 1

    print()
    print("  plafond du raisonneur : %s -> %d"
          % ("8000 (en dur)" if avant is None else str(avant), a.jetons))
    print("  reglable sans patch : %s=<n> dans l environnement" % VAR)
    print("  deepseek non-raisonneur : 3000, inchange")
    print("Marche arriere : --jetons %d"
          % (8000 if avant is None else avant))
    print()
    print("Sur un raisonneur, max_tokens couvre le RAISONNEMENT ET la")
    print("reponse. Si une reponse revient encore vide avec PLAFOND")
    print("ATTEINT, c est qu il faut monter davantage -- pas que le")
    print("modele n a rien a dire.")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DE price_action.py.")
    print("NE JAMAIS le lancer a la main sans PA_ROLE=panel : sans")
    print("elle, _run_trading est vrai et de vrais ordres partent.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauver(a.fichier, neuf)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

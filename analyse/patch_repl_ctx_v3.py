# -*- coding: utf-8 -*-
"""
patch_repl_ctx_v3.py -- le grand contexte pour le REPL SEUL

  python patch_repl_ctx_v3.py --essai
  python patch_repl_ctx_v3.py
  python patch_repl_ctx_v3.py --web 400000

LE PROBLEME

    REPL_CTX_MAX = 175000 coupe le contexte assemble. Ce soir les dix-
    sept documents font 344 121 caracteres : le modele en voit dix, et
    la liste est exactement celle d avant qu on leve _DOCS_MAX et
    _DOCS_MAX_UN. Les deux plafonds leves aujourd hui etaient EN AVAL
    d un troisieme, pose par patch_repl_ctx.py -- le mien.

    Le fichier raconte deja l histoire, lignes 256-261 : la meme chose
    est arrivee avec cinq documents, et avait coute deux heures. Le
    correctif d alors n etait pas le chiffre, c etait le marqueur qui
    PARLE. Il a parle : le modele l a cite en un message.

POURQUOI ON NE MONTE PAS SIMPLEMENT LA CONSTANTE

    build_system_message n est pas appelee que par le REPL. La
    docstring de patch_repl_ctx.py l affirme -- "n est appelee que par
    le REPL -- repl_web.py" -- et c est FAUX :

        nemotron_trader.py     304 : _repl.build_system_message(...)
        reasoning_ab_trader.py 280 : _repl.build_system_message(...)

    Ces deux-la tournent en boucle. Monter REPL_CTX_MAX doublerait
    leur prompt a chaque cycle, pour des documents qu ils ne
    demandent pas : ils importent ai_master_repl, alors que les
    panneaux sont ajoutes a repl_web._static_ctx. Ils ne les ont
    jamais vus, et ce patch ne les leur donne pas.

CE QUE FAIT LE PATCH

    _ctx_repl et build_system_message prennent un ctx_max OPTIONNEL,
    par defaut None. None => REPL_CTX_MAX, c est-a-dire le
    comportement actuel, bit pour bit, pour tout appelant qui ne le
    passe pas -- donc pour les deux traders.

    Seul repl_web.py le passe, avec REPL_CTX_WEB (400 000), constante
    ajoutee a cote de REPL_CTX_MAX pour que les deux chiffres vivent
    au meme endroit.

    REPL_CTX_MAX N EST PAS MODIFIEE. Le patch le verifie avant
    d ecrire et refuse si elle a bouge.

CE QUE CA COUTE, ET A QUI

    Au REPL seul : le prompt passe de 175 000 a ~344 000 caracteres,
    soit environ +47 000 jetons. Si la fenetre du modele ne suit pas,
    la reponse se tronquera ou l API refusera -- marche arriere
    --web 175000, qui remet le REPL au niveau des traders.

    Aux traders : rien. C est verifie, pas suppose : le patch controle
    que leurs fichiers ne sont pas touches et que la valeur par defaut
    est bien None.

HUIT ANCRES, chacune verifiee unique. REJOUABLE. Sauvegarde horodatee
des deux fichiers. ast.parse, puis controle AST des signatures.

Ce patch ne touche NI un collecteur NI un moteur d ordres.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

# Reperee par le NOM et non par la valeur : c est ce qui permet a
# --web 175000 de rendre la main une fois le patch applique.
R_WEB = re.compile(
    r"^(REPL_CTX_WEB[ \t]*=[ \t]*)(\d+)([ \t]*(?:#[^\r\n]*)?)$", re.M)

REPL = "ai_master_repl.py"
WEB = "repl_web.py"

# --- ai_master_repl.py -------------------------------------------------
A_CONST = "REPL_CTX_MAX = 175000"
A_DEF = "def _ctx_repl(static_ctx):"
A_S = '    s = static_ctx or ""'
A_IF = "    if len(s) <= REPL_CTX_MAX:"
A_DIT = "        REPL_CTX_MAX, len(s))"
A_RET = '    return s[:REPL_CTX_MAX] + "\\n\\n" + _ctx_dit'
A_BSM = "def build_system_message(static_ctx, ctx):"
A_DOC = ('    """system = PRO_SYSTEM_PROMPT + _ctx_repl(static_ctx)'
         " (cf REPL_CTX_MAX)")
A_APP = '        + "\\n\\n" + _ctx_repl(static_ctx)'

# --- repl_web.py -------------------------------------------------------
A_WEB = '        system_msg = repl.build_system_message(_static_ctx or "", ctx)'

TRADERS = ("nemotron_trader.py", "reasoning_ab_trader.py")


def lire(c):
    return io.open(c, encoding="utf-8", errors="replace").read()


def ecrire(c, t):
    s = "%s.bak-%s" % (c, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(c, s)
    io.open(c, "w", encoding="utf-8").write(t)
    print("  sauvegarde : %s" % s)


def unique(src, anc, nom):
    n = src.count(anc)
    if n != 1:
        print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
        return False
    return True


def sig(arbre, nom):
    """Rend (noms des arguments, nombre de defauts) d une fonction."""
    for n in ast.walk(arbre):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return ([a.arg for a in n.args.args], len(n.args.defaults))
    return (None, None)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--web", type=int, default=400000)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    for c in (REPL, WEB):
        if not os.path.isfile(c):
            print("KO : %s introuvable -- lance depuis le dossier de la"
                  " stack." % c)
            return 1

    # Empreinte des traders AVANT : on la recomparera a la fin. Ce
    # patch promet de ne rien leur faire ; une promesse se verifie.
    avant_traders = {}
    for t in TRADERS:
        if os.path.isfile(t):
            avant_traders[t] = len(lire(t))

    # ------------------------------------------------------------------
    src = lire(REPL)
    print("%s : %d lignes" % (REPL, src.count("\n") + 1))

    if "REPL_CTX_WEB" in src:
        # Deja patche : on ne rejoue pas les ancres, mais on doit
        # pouvoir CHANGER la valeur -- sinon --web 175000 ne rend pas
        # la main et la marche arriere annoncee est morte. C est
        # exactement le defaut corrige ce matin sur l autre patch.
        m = R_WEB.search(src)
        if not m:
            print("KO : REPL_CTX_WEB present mais illisible.")
            print("Rien n a ete ecrit.")
            return 1
        actuel = int(m.group(2))
        print("  deja patche -- REPL_CTX_WEB = %d." % actuel)
        avant_web = actuel
        if actuel == a.web:
            neuf = src
            fait_repl = False
        else:
            neuf = R_WEB.sub(
                lambda x: x.group(1) + str(a.web) + x.group(3), src, count=1)
            try:
                ast.parse(neuf)
            except SyntaxError as e:
                print("KO : %s ne compile pas (ligne %s) : %s"
                      % (REPL, e.lineno, e.msg))
                print("Rien n a ete ecrit.")
                return 1
            print("  REPL_CTX_WEB %d -> %d" % (actuel, a.web))
            fait_repl = True
    else:
        avant_web = None      # premiere application : rien avant
        for anc, nom in ((A_CONST, "REPL_CTX_MAX = 175000"),
                         (A_DEF, "def _ctx_repl"),
                         (A_S, "s = static_ctx or ''"),
                         (A_IF, "if len(s) <= REPL_CTX_MAX"),
                         (A_DIT, "REPL_CTX_MAX, len(s))"),
                         (A_RET, "return s[:REPL_CTX_MAX]"),
                         (A_BSM, "def build_system_message"),
                         (A_DOC, "docstring de build_system_message"),
                         (A_APP, "appel + _ctx_repl(static_ctx)")):
            if not unique(src, anc, nom):
                print("Rien n a ete ecrit.")
                return 1

        neuf = src
        neuf = neuf.replace(
            A_CONST,
            A_CONST + "\n"
            "# 14/08 : les panneaux ont grossi a 344 000 caracteres et le\n"
            "# modele n en voyait que 175 000 -- meme panne qu au 12/08,\n"
            "# un cran plus haut. On ne monte PAS le chiffre ci-dessus :\n"
            "# nemotron_trader et reasoning_ab_trader passent par la meme\n"
            "# fonction et n ont pas besoin des panneaux. Seul repl_web\n"
            "# demande le grand contexte, en le passant explicitement.\n"
            "REPL_CTX_WEB = %d" % a.web, 1)
        neuf = neuf.replace(A_DEF, "def _ctx_repl(static_ctx, ctx_max=None):", 1)
        neuf = neuf.replace(
            A_S, A_S + "\n    lim = ctx_max or REPL_CTX_MAX", 1)
        neuf = neuf.replace(A_IF, "    if len(s) <= lim:", 1)
        neuf = neuf.replace(A_DIT, "        lim, len(s))", 1)
        neuf = neuf.replace(
            A_RET, '    return s[:lim] + "\\n\\n" + _ctx_dit', 1)
        neuf = neuf.replace(
            A_BSM, "def build_system_message(static_ctx, ctx, ctx_max=None):", 1)
        neuf = neuf.replace(
            A_DOC,
            '    """system = PRO_SYSTEM_PROMPT + _ctx_repl(static_ctx,'
            " ctx_max)", 1)
        neuf = neuf.replace(
            A_APP, '        + "\\n\\n" + _ctx_repl(static_ctx, ctx_max)', 1)
        fait_repl = True

        try:
            arbre = ast.parse(neuf)
        except SyntaxError as e:
            print("KO : %s ne compile pas (ligne %s) : %s"
                  % (REPL, e.lineno, e.msg))
            print("Rien n a ete ecrit.")
            return 1

        # Les signatures, au niveau de l AST et pas du texte.
        args, ndef = sig(arbre, "_ctx_repl")
        if args != ["static_ctx", "ctx_max"] or ndef != 1:
            print("KO : signature _ctx_repl = %r, %r defaut(s)."
                  % (args, ndef))
            print("Rien n a ete ecrit.")
            return 1
        args, ndef = sig(arbre, "build_system_message")
        if args != ["static_ctx", "ctx", "ctx_max"] or ndef != 1:
            print("KO : signature build_system_message = %r, %r defaut(s)."
                  % (args, ndef))
            print("Rien n a ete ecrit.")
            return 1

        # LA verification qui protege les traders : le defaut vaut None,
        # donc un appel a deux arguments garde REPL_CTX_MAX.
        vals = {}
        for n in ast.walk(arbre):
            if (isinstance(n, ast.Assign) and len(n.targets) == 1
                    and isinstance(n.targets[0], ast.Name)
                    and n.targets[0].id in ("REPL_CTX_MAX", "REPL_CTX_WEB")
                    and isinstance(n.value, ast.Constant)):
                vals[n.targets[0].id] = n.value.value
        if vals.get("REPL_CTX_MAX") != 175000:
            print("KO : REPL_CTX_MAX vaut %r -- elle ne doit PAS bouger,"
                  " les traders en dependent." % vals.get("REPL_CTX_MAX"))
            print("Rien n a ete ecrit.")
            return 1
        if vals.get("REPL_CTX_WEB") != a.web:
            print("KO : REPL_CTX_WEB vaut %r." % vals.get("REPL_CTX_WEB"))
            print("Rien n a ete ecrit.")
            return 1
        for n in ast.walk(arbre):
            if isinstance(n, ast.FunctionDef) and n.name in (
                    "_ctx_repl", "build_system_message"):
                d = n.args.defaults[-1]
                if not (isinstance(d, ast.Constant) and d.value is None):
                    print("KO : le defaut de ctx_max dans %s n est pas None"
                          " -- les traders changeraient de comportement."
                          % n.name)
                    print("Rien n a ete ecrit.")
                    return 1
        print("  ctx_max ajoute, defaut None ; REPL_CTX_MAX inchangee a"
              " 175000.")
        print("  REPL_CTX_WEB = %d" % a.web)

    # ------------------------------------------------------------------
    web = lire(WEB)
    print("%s : %d lignes" % (WEB, web.count("\n") + 1))
    if "repl.REPL_CTX_WEB" in web:
        print("  deja patche -- repl_web passe deja ctx_max.")
        wneuf = web
        fait_web = False
    elif not unique(web, A_WEB, "l appel a build_system_message"):
        print("Rien n a ete ecrit.")
        return 1
    else:
        wneuf = web.replace(
            A_WEB,
            "        system_msg = repl.build_system_message(\n"
            '            _static_ctx or "", ctx, ctx_max=repl.REPL_CTX_WEB)',
            1)
        try:
            ast.parse(wneuf)
        except SyntaxError as e:
            print("KO : %s ne compile pas (ligne %s) : %s"
                  % (WEB, e.lineno, e.msg))
            print("Rien n a ete ecrit.")
            return 1
        fait_web = True
        print("  repl_web passe ctx_max=repl.REPL_CTX_WEB.")

    if not fait_repl and not fait_web:
        print()
        print("Rien a faire -- tout etait deja en place.")
        return 0

    print()
    print("Effet : le REPL web voit jusqu a %d caracteres au lieu de"
          " 175000." % a.web)
    print("        nemotron_trader et reasoning_ab_trader : INCHANGES,")
    print("        ils appellent avec deux arguments -> REPL_CTX_MAX.")
    # Le message etait CODE EN DUR a 175000. Juste a la premiere
    # application -- revenir a 175000 c est revenir au comportement d
    # avant. Faux des la seconde : apres un passage de 400000 a
    # 250000, la marche arriere est 400000. Le message aurait fait
    # descendre SOUS le point de depart en pretendant y revenir.
    print("Marche arriere : --web %d"
          % (avant_web if avant_web is not None else 175000))
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DE price_action.py.")
    print("NE JAMAIS le lancer a la main sans PA_ROLE=panel : sans")
    print("elle, _run_trading est vrai et de vrais ordres partent.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    if fait_repl:
        ecrire(REPL, neuf)
    if fait_web:
        ecrire(WEB, wneuf)

    # La promesse, verifiee apres coup et pas seulement annoncee.
    for t, n in avant_traders.items():
        if len(lire(t)) != n:
            print("ANOMALIE : %s a change de taille. Ce patch ne devait"
                  " pas y toucher." % t)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

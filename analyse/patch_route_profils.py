# -*- coding: utf-8 -*-
r"""
patch_route_profils.py -- la carte des profils sur le 8095, route /profils

  python patch_route_profils.py --essai
  python patch_route_profils.py
  python patch_route_profils.py --retire        (marche arriere)

CE QU IL AJOUTE

    Une route `/profils` dans `_do_GET_impl` de price_action.py, ecrite
    sur le modele EXACT de `/raw` et `/rails_cycle` : meme cascade de
    `if parsed.path == "..."`, meme indentation a 12 espaces, meme trio
    send_response / send_header / end_headers, meme `return` final.

    Elle est inseree JUSTE AVANT `/raw`, qui devient ainsi la seconde.
    Aucune route existante n est touchee, deplacee, ni renumerotee.

LE SERVEUR NE CALCULE RIEN

    La route relit `cartes/panel_profils.html` a chaque requete et le
    renvoie tel quel. Elle ne genere pas la carte. Recalculer 384
    grilles dans le fil HTTP pendant que les traders tournent, ce
    serait offrir une latence au pire moment possible.

    Consequence agreable : regenerer la carte par
    `python carte_html.py` suffit a rafraichir la page. Aucun
    redemarrage du panneau apres coup -- le redemarrage n est
    necessaire QU UNE FOIS, pour que la route existe.

AUCUN NOM EMPRUNTE AU MODULE

    Le bloc genere n utilise que des builtins : `open`, `Exception`,
    `str`, `len`. Pas de `os`, pas de `io`, pas de `Path`.

    C est une lecon payee comptant le 14/08 a 21:18 : un patch
    precedent avait ecrit `_os.environ` apres avoir "verifie" que os
    etait importe -- avec ast.walk, qui descend DANS les fonctions. Il
    avait trouve `import os as _os` a l interieur d une fonction et en
    avait conclu qu il existait au niveau module. La page est tombee au
    chargement. Ici il n y a rien a verifier, donc rien a se tromper.

    Le chemin est ecrit `cartes/panel_profils.html`, avec des barres
    obliques : Python les accepte sous Windows, et une barre inverse
    dans une chaine non brute est une source d echappement parasite.

SI LE FICHIER MANQUE

    La route repond 200 avec une page qui dit quoi lancer, plutot
    qu une trace de pile ou un 500 muet. Le panneau ne doit jamais
    tomber parce qu une carte n a pas ete generee.

UNE ANCRE, verifiee unique. REJOUABLE dans les deux sens (--retire).
ast.parse et controle AST du bloc obtenu. Sauvegarde horodatee,
suffixee en cas de collision.

Ce patch touche un fichier VIVANT. Il n ajoute aucun ordre, aucun
collecteur, aucun etat : une route de lecture, et rien d autre. Il ne
prend effet qu au prochain demarrage de price_action.py -- JAMAIS a la
main sans PA_ROLE=panel.
"""
import argparse
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "price_action.py"
ROUTE = "/profils"
FICHIER = "cartes/panel_profils.html"

# L ancre : la premiere route de la cascade. On s insere juste avant.
ANCRE = '            if parsed.path == "/raw":\n'

BLOC = '''            # 2026-08-14 : carte des profils, generee HORS LIGNE par
            # carte_html.py. Le serveur ne calcule rien ici -- il relit un
            # fichier. Recalculer 384 grilles dans le fil HTTP pendant que
            # les traders tournent serait une latence offerte au pire
            # moment. Regenerer la carte suffit a rafraichir la page :
            # aucun redemarrage n est necessaire apres celui-ci.
            #
            # Que des builtins ici -- pas de os, pas de io. Un patch du
            # 14/08 a fait tomber la page en empruntant un nom de module
            # qui n existait pas au niveau ou il ecrivait.
            if parsed.path == "%s":
                try:
                    with open("%s", "rb") as _h:
                        body = _h.read()
                except Exception as _e:
                    body = ("<html><body style='background:#0d1117;"
                            "color:#f85149;font-family:Consolas,monospace;"
                            "padding:24px;line-height:1.6'>"
                            "<b>carte indisponible</b><br>%%s<br><br>"
                            "Elle se genere hors ligne, depuis le dossier "
                            "de la stack :<br>"
                            "<code style='color:#58a6ff'>python carte_html.py"
                            "</code><br><br>La route relit le fichier a "
                            "chaque requete : une fois genere, il suffit de "
                            "rafraichir cette page."
                            "</body></html>" %% _e).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

''' % (ROUTE, FICHIER)


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


def route_presente(src):
    """Cherche la route dans l AST, pas dans le texte. Une occurrence de
    la chaine "/profils" dans un commentaire ou une autre page HTML ne
    doit pas se faire passer pour une route installee."""
    try:
        arbre = ast.parse(src)
    except SyntaxError:
        return None
    for n in ast.walk(arbre):
        if not isinstance(n, ast.If):
            continue
        c = n.test
        if (isinstance(c, ast.Compare) and len(c.ops) == 1
                and isinstance(c.ops[0], ast.Eq)
                and isinstance(c.comparators[0], ast.Constant)
                and c.comparators[0].value == ROUTE):
            return True
    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    p.add_argument("--retire", action="store_true",
                   help="retire la route et remet le fichier d avant")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = lire(a.fichier)
    n0 = src.count("\n") + 1
    print("%s : %d lignes" % (a.fichier, n0))

    presente = route_presente(src)
    if presente is None:
        print("KO : %s ne compile pas AVANT modification." % a.fichier)
        print("     Ce n est pas moi qui l ai casse, mais je ne touche")
        print("     pas a un fichier dans cet etat.")
        return 1

    if a.retire:
        if not presente:
            print("La route %s n est pas installee -- rien a retirer."
                  % ROUTE)
            return 0
        if src.count(BLOC) != 1:
            print("KO : le bloc n est pas retrouve tel quel (%d fois)."
                  % src.count(BLOC))
            print("     Il a ete edite depuis. Retire-le a la main ou")
            print("     reprends une sauvegarde price_action.py.bak-*.")
            return 1
        neuf = src.replace(BLOC, "", 1)
    else:
        if presente:
            print("La route %s est deja installee -- rien a faire." % ROUTE)
            print("Pour la retirer : --retire")
            return 0
        n = src.count(ANCRE)
        if n != 1:
            print("KO : %d occurrence(s) de l ancre, il en faut 1." % n)
            print("     Attendu exactement, indentation comprise :")
            print("     %s" % ANCRE.rstrip("\n"))
            print("Rien n a ete ecrit.")
            return 1
        neuf = src.replace(ANCRE, BLOC + ANCRE, 1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    attendu = not a.retire
    if route_presente(neuf) is not attendu:
        print("KO : apres modification, route presente = %r, attendu %r."
              % (route_presente(neuf), attendu))
        print("Rien n a ete ecrit.")
        return 1

    # Les routes voisines ne doivent pas avoir bouge. Si l une d elles
    # disparait, c est que le remplacement a mordu ailleurs.
    for t in ('if parsed.path == "/raw":',
              'if parsed.path == "/rails_cycle":',
              "def _do_GET_impl(self):"):
        if neuf.count(t) != src.count(t):
            print("KO : %r apparait %d fois, %d avant."
                  % (t, neuf.count(t), src.count(t)))
            print("Rien n a ete ecrit.")
            return 1

    n1 = neuf.count("\n") + 1
    d = BLOC.count("\n")
    attendu_d = -d if a.retire else d
    if n1 - n0 != attendu_d:
        print("KO : %+d lignes, attendu %+d." % (n1 - n0, attendu_d))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("  %s la route %s (%+d lignes)"
          % ("retire" if a.retire else "ajoute", ROUTE, n1 - n0))
    if not a.retire:
        print("  elle relit %s a chaque requete" % FICHIER)
        print("  elle ne genere rien : `python carte_html.py` s en charge")
        print("Marche arriere : --retire")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DE price_action.py.")
    print("NE JAMAIS le lancer a la main sans PA_ROLE=panel : sans")
    print("elle, _run_trading est vrai et de vrais ordres partent.")
    print("Ensuite : http://localhost:8095%s" % ROUTE)

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauver(a.fichier, neuf)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
patch_onglet_x60.py -- l onglet X60 ONSET dans la page 8095

  python patch_onglet_x60.py --essai
  python patch_onglet_x60.py

MEME TECHNIQUE QUE patch_onglets_rails.py, ET POUR LA MEME RAISON

    HTML_PAGE est une chaine ORDINAIRE de pres de dix mille lignes, sans
    prefixe f -- verifie a l epoque avec ast : ('Constant', 4094, 13859).
    Rien n y est interpole. On pose donc un MARQUEUR dans le HTML et on
    le remplace au moment de servir la page.

QUATRE ANCRES, toutes verifiees uniques avant la moindre ecriture :
l onglet RAILS X3 (le patch se pose juste apres), le bloc p-railsx3,
la ligne de service qui passe deja par _page_rails, et la constante
elle-meme -- ou se pose la fonction de rendu.

    Ce patch SUPPOSE que patch_onglets_rails.py est deja applique : il
    se greffe sur son marqueur et sur sa fonction _page_rails. Il le
    verifie et REFUSE de s appliquer sinon, plutot que de creer une
    deuxieme mecanique parallele pour la meme chose.

CE QUE L ONGLET AFFICHE

    panels/panel_x60_onset.txt, produit par x60_onset.py --rapport.
    Tant qu aucun evenement n a ete enregistre, il affiche « Aucun
    evenement » et dit quoi lancer -- ce qui est la verite, et se voit,
    plutot qu un panneau vide qu on croirait casse.

    Le fichier est un instantane : le panneau ne relance rien. C est
    x60_onset.py --rapport qui le regenere, et panels_auto peut s en
    charger.

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

CIBLE = "price_action.py"
MARQUEUR = "p-x60onset"
PREREQUIS = "<!--RAILS_X3_ICI-->"

RE_ONGLET = re.compile(
    r'^([ \t]*)<div class="tab" onclick="showTab\(\'railsx3\'\)"'
    r'([^>]*)>RAILS X3</div>[ \t]*$', re.M)

RE_PANNEAU = re.compile(
    r'^([ \t]*)<div class="panel" id="p-railsx3">'
    r'<!--RAILS_X3_ICI--></div>[ \t]*$', re.M)

RE_PAGE = re.compile(
    r'^([ \t]*)return \(page\.replace\("<!--RAILS_RANGE_ICI-->", _rr_panel\(\)\)$',
    re.M)

RE_CONST = re.compile(r'^HTML_PAGE = """', re.M)

TETE = '''# 12/08/2026 -- l onglet X60 ONSET.
# Le contenu vient de panels/panel_x60_onset.txt, produit par
# x60_onset.py --rapport. Le panneau ne relance rien : lire un
# instantane coute quelques millisecondes, relancer l observateur
# couterait la page.
def _x60_panel():
    try:
        import panel_texte
        import io as _io
        import os as _os
        import time as _t
        _f = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                           "panels", "panel_x60_onset.txt")
        if not _os.path.isfile(_f):
            return ("<div style='padding:14px;color:#fbbc04'>Aucun releve "
                    "x60 pour l instant.<br>Lance <code>python "
                    "x60_onset.py --loop</code> : il ne voit que ce qui se "
                    "passe pendant qu il tourne.</div>")
        _txt = _io.open(_f, encoding="utf-8", errors="replace").read()
        _age = int(_t.time() - _os.path.getmtime(_f))
        return panel_texte.rendre(_txt.strip(), "X60 ONSET", _f, _age)
    except Exception as _e:
        return ("<div style='padding:14px;color:#f28b82'>X60 ONSET "
                "indisponible : %s: %s</div>" % (type(_e).__name__, _e))


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

    if PREREQUIS not in src:
        print("KO : patch_onglets_rails.py n est pas applique.")
        print("Ce patch se greffe sur son marqueur et sur sa fonction")
        print("_page_rails. Sans lui il faudrait creer une deuxieme")
        print("mecanique pour la meme chose -- on ne fait pas ca.")
        print("Rien n a ete ecrit.")
        return 1

    ancres = (("l onglet RAILS X3", RE_ONGLET),
              ("le bloc p-railsx3", RE_PANNEAU),
              ("la ligne _page_rails", RE_PAGE),
              ("la constante HTML_PAGE", RE_CONST))
    for nom, rx in ancres:
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1
        print("  %-24s : %s" % (nom, rx.search(src).group(0).strip()[:66]))

    mo, mp = RE_ONGLET.search(src), RE_PANNEAU.search(src)
    ind_o, style = mo.group(1), mo.group(2)
    neuf = RE_ONGLET.sub(
        lambda m: (m.group(0) + "\n" + ind_o
                   + '<div class="tab" onclick="showTab(\'x60onset\')"%s>'
                     'X60 ONSET</div>' % style),
        src, count=1)

    ind_p = mp.group(1)
    neuf = RE_PANNEAU.sub(
        lambda m: (m.group(0) + "\n" + ind_p
                   + '<div class="panel" id="p-x60onset">'
                     '<!--X60_ONSET_ICI--></div>'),
        neuf, count=1)

    neuf = RE_PAGE.sub(
        lambda m: (m.group(1)
                   + 'return (page.replace("<!--X60_ONSET_ICI-->", '
                     '_x60_panel())\n'
                   + m.group(1)
                   + '            .replace("<!--RAILS_RANGE_ICI-->",'
                     ' _rr_panel())'),
        neuf, count=1)

    md = RE_CONST.search(neuf)
    if not md:
        print("KO : la constante HTML_PAGE a disparu en cours de route.")
        return 1
    neuf = neuf[:md.start()] + TETE + neuf[md.start():]

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Onglet X60 ONSET ajoute apres RAILS X3.")
    print("Contenu : panels\\panel_x60_onset.txt, rendu par panel_texte")
    print("-- donc en couleurs, avec l age du releve en tete.")
    print()
    print("Tant qu aucun x60 n a ete observe, l onglet le DIT et donne la")
    print("commande a lancer. Un panneau vide passerait pour casse.")

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

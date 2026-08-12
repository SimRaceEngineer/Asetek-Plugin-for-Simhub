# -*- coding: utf-8 -*-
"""
patch_onglets_rails.py -- les onglets RAILS RANGE et RAILS X3 dans la page

  python patch_onglets_rails.py --essai
  python patch_onglets_rails.py

CE QU IL FAIT

    1. Juste apres l onglet RAILS TRADES, deux onglets de plus.
    2. Juste avant le bloc <div class="panel" id="p-railstr">, deux
       blocs de contenu portant chacun un MARQUEUR.
    3. La ligne qui sert la page passe par _page_rails(), qui remplace
       les deux marqueurs par le contenu des panneaux.

COMMENT LE CONTENU ENTRE DANS LA PAGE

    HTML_PAGE (ligne 4094) est une chaine ORDINAIRE de 9 766 lignes,
    sans prefixe f -- verifie avec ast : ('Constant', 4094, 13859). Les
    accolades n y seraient jamais interpretees.

    Elle est servie brute, une seule fois, ligne 23165 :

        self.wfile.write(HTML_PAGE.encode("utf-8"))

    D ou les marqueurs, remplaces au moment de servir. Pas de f-string,
    pas de route HTTP, pas de branche JavaScript -- showTab affiche le
    div #p-<id> et c est tout.

    Une premiere version tentait l interpolation et a REFUSE de
    s appliquer, en detectant que la chaine n etait pas une f-string.
    Elle avait raison : elle aurait affiche du code dans la page.

QUATRE ANCRES, toutes verifiees uniques avant la moindre ecriture :
l onglet RAILS TRADES, le bloc p-railstr, la ligne de service, et la
constante elle-meme -- ou se posent les trois fonctions.

Le patch IMPRIME chaque ligne reconnue avant d ecrire : une ancre qui
attrape la mauvaise ligne est pire qu une ancre qui n attrape rien.

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
MARQUEUR = "p-railsrange"

RE_ONGLET = re.compile(
    r'^([ \t]*)<div class="tab" onclick="showTab\(\'railstr\'\)"'
    r'([^>]*)>RAILS TRADES</div>[ \t]*$', re.M)

RE_PANNEAU = re.compile(
    r'^([ \t]*)<div class="panel" id="p-railstr"', re.M)

RE_ECRIT = re.compile(
    r'^([ \t]*)self\.wfile\.write\(HTML_PAGE\.encode\("utf-8"\)\)[ \t]*$',
    re.M)

# Les trois fonctions se posent juste AVANT la constante : elle est
# unique, deja verifiee, et au niveau du module. Une regle du genre
# "avant la premiere def" dependrait de la forme du fichier.
RE_CONST = re.compile(r'^HTML_PAGE = """', re.M)

ONGLETS = (
    '<div class="tab" onclick="showTab(\'railsrange\')"%s>RAILS RANGE</div>\n'
    '%s<div class="tab" onclick="showTab(\'railsx3\')"%s>RAILS X3</div>')

PANNEAUX = (
    '<div class="panel" id="p-railsrange"><!--RAILS_RANGE_ICI--></div>\n'
    '%s<div class="panel" id="p-railsx3"><!--RAILS_X3_ICI--></div>\n'
    '%s')

TETE = '''# 12/08/2026 -- les deux onglets rails manquants.
# Le contenu vient des fichiers texte deja exportes (instantane), pas
# d un script relance a chaque chargement. Un import qui echoue ne fait
# tomber que son panneau, jamais la page.
def _rr_panel():
    try:
        import rails_range_panel as _m
        return _m.render_panel()
    except Exception as _e:
        return ("<div style='padding:14px;color:#f28b82'>RAILS RANGE "
                "indisponible : %s: %s</div>" % (type(_e).__name__, _e))


def _r3_panel():
    try:
        import rails_trois_panel as _m
        return _m.render_panel()
    except Exception as _e:
        return ("<div style='padding:14px;color:#f28b82'>RAILS X3 "
                "indisponible : %s: %s</div>" % (type(_e).__name__, _e))


def _page_rails(page):
    """Remplace les deux marqueurs au moment de servir la page.

    HTML_PAGE est une chaine ordinaire : rien n y est interpole. On
    substitue donc ici, une fois par requete. Chaque panneau lit un
    fichier texte deja exporte -- quelques millisecondes."""
    try:
        return (page.replace("<!--RAILS_RANGE_ICI-->", _rr_panel())
                    .replace("<!--RAILS_X3_ICI-->", _r3_panel()))
    except Exception:
        return page          # jamais casser la page pour deux panneaux


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

    for m in ("rails_range_panel.py", "rails_trois_panel.py"):
        if not os.path.isfile(m):
            print("KO : %s manque. Copie-le depuis le Drive d abord." % m)
            return 1

    src, enc = lire(a.fichier)
    print("%s : %d lignes, encodage %s" % (a.fichier, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    ancres = (("l onglet RAILS TRADES", RE_ONGLET),
              ("le bloc p-railstr", RE_PANNEAU),
              ("la ligne de service", RE_ECRIT),
              ("la constante HTML_PAGE", RE_CONST))
    for nom, rx in ancres:
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1
        print("  %-24s : %s" % (nom, rx.search(src).group(0).strip()[:70]))

    mo, mp, me = (RE_ONGLET.search(src), RE_PANNEAU.search(src),
                  RE_ECRIT.search(src))

    ind_o, style = mo.group(1), mo.group(2)
    neuf = RE_ONGLET.sub(
        lambda m: m.group(0) + "\n" + ind_o + (ONGLETS % (style, ind_o, style)),
        src, count=1)

    ind_p = mp.group(1)
    neuf = RE_PANNEAU.sub(
        lambda m: ind_p + (PANNEAUX % (ind_p, ind_p)) + m.group(0),
        neuf, count=1)

    ind_e = me.group(1)
    neuf = RE_ECRIT.sub(
        lambda m: ind_e + 'self.wfile.write(_page_rails(HTML_PAGE)'
                          '.encode("utf-8"))',
        neuf, count=1)

    md = RE_CONST.search(neuf)
    if not md:
        print("KO : la constante HTML_PAGE a disparu en cours de route.")
        print("Rien n a ete ecrit.")
        return 1
    neuf = neuf[:md.start()] + TETE + neuf[md.start():]

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Deux onglets ajoutes apres RAILS TRADES :")
    print("    RAILS RANGE  -> panels\\panel_rails_post0508.txt")
    print("    RAILS X3     -> panels\\panel_rails_trois.txt")
    print()
    print("Contenu lu depuis le texte exporte : instantane, et c est")
    print("exactement ce que lit le REPL. L age est affiche en tete du")
    print("panneau -- orange au-dela de 20 min, rouge au-dela d une")
    print("heure. Un panneau qui tait sa date laisse croire qu il est")
    print("frais.")

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

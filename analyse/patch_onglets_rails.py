# -*- coding: utf-8 -*-
"""
patch_onglets_rails.py -- les onglets RAILS RANGE et RAILS X3 dans la page

  python patch_onglets_rails.py --essai
  python patch_onglets_rails.py

CE QU IL FAIT

    Deux insertions, pas une de plus.

    1. Juste apres l onglet RAILS TRADES, deux onglets de plus.
    2. Juste avant le bloc <div class="panel" id="p-railstr">, deux
       blocs de contenu batis sur le meme moule.

    Les panneaux sont INLINE, pas en iframe : leur contenu est lu depuis
    les fichiers texte deja exportes, ce qui est instantane. Pas de route
    HTTP a ajouter, pas de branche JavaScript -- showTab affiche le div
    #p-<id> et c est tout.

POURQUOI IL PEUT REFUSER, ET POURQUOI C EST VOULU

    L insertion doit tomber DANS une f-string triple, sinon les
    accolades resteraient du texte et la page afficherait le nom de la
    fonction entre accolades au lieu du panneau.

    Le patch remonte donc le fichier depuis le point d insertion pour
    verifier qu il est bien dans une f-string ouverte. S il n en trouve
    pas, il REFUSE et le dit. Mieux vaut un patch qui refuse qu une page
    qui affiche du code.

    Il verifie aussi que rails_range_panel et rails_trois_panel sont
    importables avant d ecrire quoi que ce soit.

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

ONGLETS = (
    '<div class="tab" onclick="showTab(\'railsrange\')"%s>RAILS RANGE</div>\n'
    '%s<div class="tab" onclick="showTab(\'railsx3\')"%s>RAILS X3</div>')

PANNEAUX = (
    '<div class="panel" id="p-railsrange">{_rr_panel()}</div>\n'
    '%s<div class="panel" id="p-railsx3">{_r3_panel()}</div>\n'
    '%s')

# Les deux fonctions sont definies au niveau du module : un import qui
# echoue ne doit pas faire tomber toute la page, seulement ce panneau.
TETE = '''

# 12/08/2026 -- les deux onglets rails manquants.
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

'''


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def dans_fstring(src, pos):
    """La position est-elle dans une f-string triple ouverte ?

    On compte les ouvertures et fermetures de triples guillemets avant
    le point d insertion. Impair = on est dedans. Grossier, mais il ne
    s agit que de refuser un patch douteux, pas d analyser du Python."""
    avant = src[:pos]
    triples = re.findall(r'(f?)("""|\'\'\')', avant)
    if len(triples) % 2 == 0:
        return False, "pas dans une chaine triple"
    ouvrante = triples[-1]
    if ouvrante[0] != "f":
        return False, "chaine triple ouverte mais SANS le prefixe f"
    return True, "f-string triple ouverte"


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

    for nom, rx in (("l onglet RAILS TRADES", RE_ONGLET),
                    ("le bloc p-railstr", RE_PANNEAU)):
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1

    mo = RE_ONGLET.search(src)
    mp = RE_PANNEAU.search(src)
    print("  ancre onglet  : %s" % mo.group(0).strip()[:82])
    print("  ancre panneau : %s" % mp.group(0).strip()[:82])

    for nom, pos in (("onglet", mo.start()), ("panneau", mp.start())):
        ok, pourquoi = dans_fstring(src, pos)
        print("  contexte %-8s : %s" % (nom, pourquoi))
        if not ok:
            print()
            print("KO : l insertion ne tomberait pas dans une f-string.")
            print("Les accolades resteraient du texte et la page")
            print("afficherait le code au lieu du panneau.")
            print("Rien n a ete ecrit.")
            return 1

    ind_o, style = mo.group(1), mo.group(2)
    neuf = RE_ONGLET.sub(
        lambda m: m.group(0) + "\n" + ind_o + (ONGLETS % (style, ind_o, style)),
        src, count=1)

    ind_p = mp.group(1)
    neuf = RE_PANNEAU.sub(
        lambda m: ind_p + (PANNEAUX % (ind_p, ind_p)) + m.group(0),
        neuf, count=1)

    # Les deux fonctions vont juste avant la premiere def du module.
    rd = re.compile(r'^def [A-Za-z_]', re.M)
    md = rd.search(neuf)
    if not md:
        print("KO : aucune def trouvee pour poser les deux fonctions.")
        return 1
    neuf = neuf[:md.start()] + TETE.lstrip("\n") + "\n" + neuf[md.start():]

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
    print("panneau, en orange au-dela de 20 min, en rouge au-dela d une")
    print("heure -- un panneau qui ne dit pas son age laisse croire")
    print("qu il est frais.")

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

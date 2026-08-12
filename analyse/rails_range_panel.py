# -*- coding: utf-8 -*-
"""
rails_range_panel.py -- l onglet RAILS RANGE de la page 8095

Lit le fichier deja exporte et l affiche dans un <pre>.

POURQUOI LIRE LE TXT ET NON RELANCER LE SCRIPT

    rails_range.py met plusieurs secondes a tourner. Le rendre a chaque
    chargement de page rendrait toute la page lente, pour un panneau
    qu on ne regarde pas a chaque fois.

    Le fichier est deja produit par export_panels.py, et panels_auto.py
    le rafraichit toutes les 15 minutes. On lit donc exactement ce que
    lit le REPL -- une seule version des chiffres, pas deux.

POURQUOI SI SIMPLE

    La sortie console porte deja ses avertissements et ses ? sur les
    cellules trop petites. La reecrire en HTML, ce serait risquer d en
    perdre un en chemin -- et un avertissement perdu est pire qu un
    panneau moche.

    rails_trois_panel.py est ecrit exactement pareil.

L AGE EST AFFICHE. Un panneau qui ne dit pas quand il a ete produit
laisse croire qu il est frais.
"""
import html as _html
import io
import os
import time

FICHIER = os.path.join("panels", "panel_rails_post0508.txt")
TITRE = "RAILS RANGE"


def _lire():
    """(texte, age_en_secondes). age None si le fichier manque."""
    if not os.path.isfile(FICHIER):
        return ("%s introuvable.\n\nIl est produit par export_panels.py "
                "et rafraichi par panels_auto.py." % FICHIER), None
    try:
        t = io.open(FICHIER, encoding="utf-8", errors="replace").read()
    except Exception as e:
        return "%s illisible : %s" % (FICHIER, e), None
    return t.strip(), int(time.time() - os.path.getmtime(FICHIER))


def render_panel():
    txt, age = _lire()
    if age is None:
        entete, couleur = "fichier absent", "#f28b82"
    elif age > 3600:
        entete = "exporte il y a %d min -- PERIME" % (age // 60)
        couleur = "#f28b82"
    elif age > 1200:
        entete, couleur = "exporte il y a %d min" % (age // 60), "#fbbc04"
    else:
        entete, couleur = "exporte il y a %d min" % (age // 60), "#8ab4f8"
    return (
        '<div style="padding:10px 14px">'
        '<h2 style="color:%s;margin:0 0 4px 0">%s</h2>'
        '<div style="color:#9aa0a6;font-size:12px;margin-bottom:10px">'
        '%s &middot; %s</div>'
        '<pre style="white-space:pre;overflow-x:auto;font-size:12px;'
        'line-height:1.35;color:#e8eaed;background:#1b1b1d;padding:12px;'
        'border-radius:6px">%s</pre></div>'
        % (couleur, TITRE, entete, FICHIER, _html.escape(txt))
    )


render = render_panel


if __name__ == "__main__":
    t, a = _lire()
    print("age : %s s" % a)
    print(t[:800])

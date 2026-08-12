# -*- coding: utf-8 -*-
"""
rails_range_panel.py -- l onglet RAILS RANGE de la page 8095

Lit le fichier deja exporte et le met en page comme RAILS TRADES.

POURQUOI LIRE LE TXT ET NON RELANCER LE SCRIPT

    rails_range.py met plusieurs secondes a tourner. Le rendre a chaque
    chargement de page rendrait toute la page lente, pour un panneau
    qu on ne regarde pas a chaque fois.

    Le fichier est deja produit par export_panels.py, et panels_auto.py
    le rafraichit toutes les 15 minutes. On lit donc exactement ce que
    lit le REPL -- une seule version des chiffres, pas deux.

LA MISE EN PAGE EST DANS panel_texte.py

    Elle etait d abord un <pre> brut : juste, mais serre et gris. Le
    module panel_texte deduit les colonnes de la geometrie du texte et
    rend de vrais tableaux, sans toucher a un seul chiffre.

    S il manque, on retombe sur le <pre>. Un panneau moche vaut mieux
    qu un panneau absent -- et le repli le DIT, il ne se tait pas.

    rails_trois_panel.py est ecrit exactement pareil ; seules changent
    les deux constantes ci-dessous.

L AGE EST AFFICHE. Un panneau qui ne dit pas quand il a ete produit
laisse croire qu il est frais.
"""
import html as _html
import io
import os
import time

# Le chemin est calcule depuis CE fichier : le 8095 ne demarre pas
# toujours depuis le dossier de la stack, et un chemin relatif y donnait
# un panneau vide sans dire pourquoi.
_ICI = os.path.dirname(os.path.abspath(__file__))
FICHIER = os.path.join(_ICI, "panels", "panel_rails_post0508.txt")
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


def _brut(txt, age, raison):
    """Le rendu d avant, garde comme repli. Il dit pourquoi il sert."""
    return (
        '<div style="padding:10px 14px">'
        '<h2 style="color:#8ab4f8;margin:0 0 4px 0">%s</h2>'
        '<div style="color:#fbbc04;font-size:12px;margin-bottom:10px">'
        'mise en page reduite (%s) &middot; les chiffres sont intacts'
        '</div>'
        '<pre style="white-space:pre;overflow-x:auto;font-size:12px;'
        'line-height:1.35;color:#e8eaed;background:#1b1b1d;padding:12px;'
        'border-radius:6px">%s</pre></div>'
        % (TITRE, _html.escape(str(raison)), _html.escape(txt))
    )


def render_panel():
    txt, age = _lire()
    try:
        import panel_texte
        return panel_texte.rendre(txt, TITRE, FICHIER, age)
    except Exception as e:
        return _brut(txt, age, "%s: %s" % (type(e).__name__, e))


render = render_panel


if __name__ == "__main__":
    t, a = _lire()
    print("age : %s s, %d caracteres" % (a, len(t)))
    print("rendu : %d caracteres" % len(render_panel()))

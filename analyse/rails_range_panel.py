# -*- coding: utf-8 -*-
"""
rails_range_panel.py -- l onglet RAILS RANGE de la page 8095

Rend la sortie de rails_range.py telle quelle, dans un <pre>.

POURQUOI SI SIMPLE

    On aurait pu reecrire le panneau en HTML, avec des tableaux et des
    couleurs. On ne l a pas fait, pour deux raisons.

    La sortie console est deja lisible et deja relue : c est elle qui a
    servi toute la journee, elle porte ses avertissements et ses ? sur
    les cellules trop petites. La reecrire, ce serait risquer d en perdre
    un morceau en chemin -- et un avertissement perdu est pire qu un
    panneau moche.

    Et surtout, il n existe alors qu UNE version des chiffres. Si le
    panneau web et la console divergeaient un jour, personne ne saurait
    lequel croire.

    rails_trois_panel.py est ecrit exactement pareil. Deux fichiers
    jumeaux, ca se relit d un coup d oeil.
"""
import html as _html
import os
import subprocess
import sys

SCRIPT = "rails_range.py"
TICKETS = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
TITRE = "RAILS RANGE"
DELAI = 120


def _sortie():
    """(texte, ok). En cas d echec on rend l erreur, jamais du vide."""
    if not os.path.isfile(SCRIPT):
        return "%s introuvable dans %s" % (SCRIPT, os.getcwd()), False
    argv = [sys.executable, SCRIPT, "--fichier", TICKETS]
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=DELAI)
    except subprocess.TimeoutExpired:
        return "%s n a pas repondu en %d s." % (SCRIPT, DELAI), False
    except Exception as e:
        return "%s: %s" % (type(e).__name__, e), False
    if r.returncode != 0:
        court = (r.stderr or r.stdout or "").strip()
        return "%s a rendu le code %d :\n\n%s" % (SCRIPT, r.returncode,
                                                  court[-2000:]), False
    return (r.stdout or "").strip(), True


def render_panel():
    txt, ok = _sortie()
    if not txt:
        txt = "%s n a rien ecrit." % SCRIPT
        ok = False
    couleur = "#8ab4f8" if ok else "#f28b82"
    return (
        '<div style="padding:10px 14px">'
        '<h2 style="color:%s;margin:0 0 4px 0">%s</h2>'
        '<div style="color:#9aa0a6;font-size:12px;margin-bottom:10px">'
        'sortie de %s sur %s -- memes chiffres que la console, '
        'aucune reecriture</div>'
        '<pre style="white-space:pre;overflow-x:auto;font-size:12px;'
        'line-height:1.35;color:#e8eaed;background:#1b1b1d;padding:12px;'
        'border-radius:6px">%s</pre></div>'
        % (couleur, TITRE, SCRIPT, TICKETS, _html.escape(txt))
    )


render = render_panel          # les deux noms, comme les autres panneaux


if __name__ == "__main__":
    t, ok = _sortie()
    print(t if ok else "ECHEC : " + t)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cartes_live_couleur.py -- cartes_live cesse d etre un mur gris.

LE DEFAUT
---------
`page_html()` echappait le texte et le posait dans un <pre>. Une seule
couleur, aucune hierarchie : les titres de section, l en-tete du
tableau, les lignes ATTENDU et CONSTATE et les trois branches avaient
exactement le meme gris. Sur cent quatre-vingts lignes, on ne voit
rien -- et surtout pas ce qu on est venu comparer.

POURQUOI UN COLORISEUR ET NON UN NOUVEAU RENDU
    Le texte reste la source de verite. `cartes\panel_papers_live.txt`
    est lu tel quel par ailleurs, et le rendu texte est aligne au
    caractere pres. Le refaire en HTML, ce serait deux rendus a tenir
    d accord -- et un jour ils divergeraient.

    Ce patch ne touche donc QUE page_html : il relit le texte deja
    produit, reconnait sa structure, et l habille. L alignement est
    preserve par white-space:pre.

POURQUOI ON NE REECRIT PAS LE FICHIER ENTIER
    cartes_live.py a deja recu le patch de la branche 5 le 25/08 --
    base_et_branche connait la plage 5220000 et les boucles font
    (1, 2, 5). Deposer une version complete depuis le depot ecraserait
    ce travail. On remplace une fonction, pas un fichier.

CE QUE LA COULEUR DIT, ET C EST LE POINT
    Chaque ligne du tableau porte un liseret a gauche selon sa branche :

        bleu    miroir 1  -- exempte des modules de sortie
        ambre   miroir 2  -- soumis aux modules de sortie
        violet  miroir 5  -- meme sortie que le 1, entree filtree CVD

    Les trois lignes d un meme magic se lisent alors d un coup d oeil,
    et l ecart 1 contre 5 -- qui ne mesure QUE le filtre d entree --
    saute aux yeux au lieu de se chercher.

    Les montants signes passent en vert ou en rouge. La regle est
    etroite a dessein : signe collant a un nombre a decimales, precede
    d un blanc. Sans ca, "2026-08-25" verrait son "-08" vire au rouge.

USAGE
-----
    python patch_cartes_live_couleur.py                <- simulation
    python patch_cartes_live_couleur.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\cartes_live.py"
SUFFIXE_BAK = ".bak_couleur"
MARQUEUR = "COULEURS_V1"
DEBUT = "def page_html(txt):"
SUITE = "\ndef defaut("

NEUVE = r'''def page_html(txt):
    """COULEURS_V1 -- un FRAGMENT, pas une page complete : la route
    /carte prepose elle-meme le style et la barre du tableau de bord.
    Tout est porte par #cl pour ne rien deborder sur le reste."""
    return _CSS + _LEGENDE + "\n".join(_habille(txt)) + "</div></div>"


_CSS = """<style>
#cl{padding:14px 18px;background:#0d1117;color:#c9d1d9;
    font:12.5px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;
    overflow-x:auto}
#cl h1{font:600 19px system-ui,sans-serif;color:#58a6ff;margin:2px 0 4px}
#cl .sous{color:#8b949e;font:13px system-ui,sans-serif;margin:0 0 16px}
#cl h2{font:600 12px system-ui,sans-serif;letter-spacing:.09em;
    text-transform:uppercase;color:#0d1117;background:#58a6ff;
    padding:6px 12px;border-radius:5px;margin:26px 0 10px;
    display:inline-block}
#cl hr{border:0;border-top:1px solid #30363d;margin:9px 0}
#cl .l{white-space:pre}
#cl .v{height:9px}
#cl .tete{color:#8b949e;font-weight:600}
#cl .tab{border-left:3px solid #30363d;padding-left:9px;margin-left:-12px}
#cl .tab:hover{background:#161b22}
#cl .b1{border-left-color:#58a6ff}
#cl .b2{border-left-color:#d29922}
#cl .b5{border-left-color:#a371f7}
#cl .mag{color:#d29922;font-weight:600}
#cl .cst{color:#58a6ff}
#cl .att{color:#8b949e}
#cl .det{color:#e6edf3;font-weight:600}
#cl .fort{color:#e6edf3;font-weight:600}
#cl .vert{color:#3fb950;font-weight:600}
#cl .rouge{color:#f85149;font-weight:600}
#cl .cle{display:inline-block;padding:2px 9px;border-radius:11px;
    font:11px system-ui,sans-serif;margin-right:7px;
    border-left:3px solid}
</style>"""

_LEGENDE = ("""<div id="cl"><h1>Cartes live -- papers sur le compte dedie</h1>
<div class="sous">Meme entree, meme lot, meme instant pour les trois
branches. Seule la ligne CONSTATE est reelle.</div>
<div style="margin:0 0 16px">
<span class="cle" style="border-color:#58a6ff;background:#0f2438">"""
            """miroir 1 &middot; exempt des sorties</span>
<span class="cle" style="border-color:#d29922;background:#2b2210">"""
            """miroir 2 &middot; soumis aux sorties</span>
<span class="cle" style="border-color:#a371f7;background:#221a33">"""
            """miroir 5 &middot; entree filtree CVD</span>
</div><div>""")

_SIGNE = re.compile(r"(?<![\w.])([+-]\d+\.\d{2})(?!\d)")
_MAGIC = re.compile(r"^(\s*)(\d{6,7})")


def _echappe(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _nombres(e):
    """Vert au-dessus de zero, rouge en dessous. La regle est etroite
    a dessein : sans le point decimal et le blanc devant, le "-08" de
    "2026-08-25" passerait en rouge."""
    def f(m):
        v = m.group(1)
        if float(v) == 0.0:
            return v          # un zero n est ni un gain ni une perte
        return '<b class="%s">%s</b>' % ("vert" if v[0] == "+" else "rouge", v)
    return _SIGNE.sub(f, e)


def _ligne(l):
    e = _nombres(_echappe(l))
    if not l.strip():
        return '<div class="v"></div>'
    s = l.strip()
    cls = "l "
    if "CONSTATE" in l:
        cls += "cst"
    elif s.startswith("ATTENDU"):
        cls += "att"
    elif _MAGIC.match(l) and l[:1] != " ":
        # ligne du tableau. La branche vit aux colonnes 40-41, posee
        # par le format "%-8d %-30s %-2d |" du rendu texte.
        br = l[40:42].strip() if len(l) > 41 else ""
        cls += "tab" + (" b%s" % br if br in ("1", "2", "5") else "")
        e = _MAGIC.sub(r'\1<b class="mag">\2</b>', e, count=1)
    elif _MAGIC.match(l):
        cls += "det"
        e = _MAGIC.sub(r'\1<b class="mag">\2</b>', e, count=1)
    elif s.startswith("MAGIC") or "A T T E N D U" in l:
        cls += "tete"
    elif len(s) > 12 and s == s.upper():
        cls += "fort"
    return '<div class="%s">%s</div>' % (cls.strip(), e)


def _habille(txt):
    """Un trait plein de '=' encadre un titre : les trois lignes
    deviennent un seul <h2>. Un trait de '-' devient un filet."""
    L = txt.split("\n")
    out = []
    i, n = 0, len(L)
    while i < n:
        nu = L[i].strip()
        if nu and set(nu) == set("="):
            if i + 2 < n and set(L[i + 2].strip() or " ") == set("="):
                out.append("<h2>%s</h2>" % _echappe(L[i + 1].strip()))
                i += 3
                continue
            i += 1
            continue
        if nu and set(nu) == set("-"):
            out.append("<hr>")
            i += 1
            continue
        out.append(_ligne(L[i]))
        i += 1
    return out


'''


def lire(chemin):
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        return f.read()


def applique(s):
    n = s.count(DEBUT)
    if n != 1:
        return None, "def page_html attendue 1 fois, trouvee %d" % n
    i = s.index(DEBUT)
    j = s.find(SUITE, i)
    if j < 0:
        return None, "def defaut( introuvable apres page_html"
    if "import re" not in s:
        return None, "le module re n est pas importe dans le fichier"
    return s[:i] + NEUVE + s[j + 1:], ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 68)
    print("patch_cartes_live_couleur -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 68)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))
    print("        branche 5 dans le fichier : %s"
          % ("oui" if "5220000" in s or "5249999" in s else "NON"))
    if MARQUEUR in s:
        print("")
        print("Deja pose : page_html est deja la version en couleurs.")
        return 0

    neuf, err = applique(s)
    if neuf is None:
        print("")
        print("REFUS : %s." % err)
        return 1
    print("        page_html unique, defaut() trouvee derriere elle.")
    print("")
    print("a faire :")
    print("   ~ page_html remplacee, le reste du fichier intact")
    print("   + titres de section en bandeau, filets entre les blocs")
    print("   + liseret par branche : 1 bleu, 2 ambre, 5 violet")
    print("   + montants signes en vert et rouge")
    print("   + legende des trois branches en tete de page")

    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer.")
        return 0

    bak = a.cible + SUFFIXE_BAK
    if not os.path.exists(bak):
        shutil.copy2(a.cible, bak)
        print("")
        print("sauvegarde : %s" % bak)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    print("ecrit : %s" % a.cible)

    relu = lire(a.cible)
    manques = [x for x in (MARQUEUR, "_habille", "b5", "def defaut(")
               if x not in relu]
    if manques:
        print("relu  : INCOMPLET, manque %s -- RESTAURER %s"
              % (", ".join(manques), bak))
        return 1
    try:
        compile(relu, a.cible, "exec")
        print("relu  : les quatre marques y sont, et le fichier compile.")
    except SyntaxError as e:
        print("relu  : ERREUR DE SYNTAXE ligne %s -- RESTAURER %s"
              % (e.lineno, bak))
        return 1

    print("")
    print("-" * 68)
    print("Relancer `python cartes_live.py` pour reecrire la page, puis")
    print("rafraichir l onglet CARTES LIVE. Rien a redemarrer : la route")
    print("relit le dossier cartes a chaque requete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

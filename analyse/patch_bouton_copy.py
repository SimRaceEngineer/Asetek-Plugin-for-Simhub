# -*- coding: utf-8 -*-
"""
patch_bouton_copy.py -- bouton Copy et vraies couleurs sur rails et x60

  python patch_bouton_copy.py --essai
  python patch_bouton_copy.py

LE MANQUE

    RAILS RANGE, RAILS X3 et X60 ONSET n avaient pas de bouton Copy,
    contrairement aux autres onglets du 8095. Les trois passent par
    panel_texte.rendre() : le bouton se pose donc UNE fois, ici, et
    apparait sur les trois.

CE QU IL COPIE, ET POURQUOI

    LE TEXTE BRUT, pas le rendu. Une zone <textarea> hors ecran porte
    la source telle qu elle sort du fichier .txt. Copier le HTML rendu
    donnerait des colonnes collees et des lignes cassees -- inutilisable
    dans un REPL ou dans un prompt, ce qui est precisement l usage.

    navigator.clipboard d abord ; repli sur select + execCommand quand
    le navigateur le refuse, ce qui arrive hors HTTPS. Et le bouton dit
    « copie » ou « echec » : muet, on ne saurait pas si ca a marche.

L EFFET DE BORD QU IL FALLAIT TRAITER

    Cette zone source contient le texte ENTIER. verifier() -- le
    controle qui prouve qu aucune ligne n est perdue en devenant un
    tableau -- l aurait trouvee et aurait valide n importe quel rendu,
    meme ampute. Le controle serait devenu decoratif au moment meme ou
    on ajoutait de quoi le tromper.

    verifier() retire donc les <textarea> avant de comparer. Verifie
    sur un rendu volontairement ampute : detecte.

LA PALETTE, AUSSI

    Les verts et rouges de ces panneaux etaient les tons pastel de
    Material (#81c995 / #f28b82) : justes, mais delaves a cote de RAILS
    TRADES et du panneau orderflow, qui utilisent la palette GitHub
    sombre du reste de la stack. Ils passent a #3fb950 et #f85149.

    Et les chiffres SIGNES passent en gras, comme dans RAILS TRADES :
    un resultat doit se voir avant les effectifs et les taux qui
    l entourent. Un panneau fade se lit moins vite.

    Aucun chiffre n est touche, seulement leur affichage.

CINQ ANCRES, verifiees uniques avant la moindre ecriture.
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

CIBLE = "panel_texte.py"
MARQUEUR = "class=\"cp\""

RE_CSS = re.compile(
    r"^([ \t]*)'</style>'\n[ \t]*% \{\"p\": pid, \"t\": TEXTE, \"g\": GRIS,"
    r" \"b\": BLEU, \"f2\": FOND2\}\)$", re.M)

RE_CORPS = re.compile(
    r"^([ \t]*)corps = \[_css\(pid\), '<div id=\"%s\">' % pid,\n"
    r"[ \t]*'<h2 style=\"color:%s\">%s</h2>' % \(coul, _e\(titre\)\),\n"
    r"[ \t]*'<div class=\"age\">%s &middot; %s</div>'\n"
    r"[ \t]*% \(_e\(entete\), _e\(str\(fichier\)\)\)\]$", re.M)

RE_VERIF = re.compile(
    r'^([ \t]*)nu = re\.sub\(r"</\(tr\|div\|pre\|h2\|h3\|style\)>",'
    r' "\\n", html\)$', re.M)

RE_PALETTE = re.compile(
    r'^VERT = "#81c995"\nROUGE = "#f28b82"$', re.M)

RE_SIGNE = re.compile(
    r'^([ \t]*)if v > 0:\n[ \t]*return VERT, False\n'
    r'[ \t]*if v < 0:\n[ \t]*return ROUGE, False$', re.M)

CSS = """@I@'#%(p)s .tete{display:flex;align-items:baseline;'
@I@'justify-content:space-between;gap:14px}'
@I@'#%(p)s .cp{background:%(f2)s;color:%(t)s;'
@I@'border:1px solid rgba(255,255,255,.16);border-radius:6px;'
@I@'padding:4px 13px;font-size:11.5px;cursor:pointer;'
@I@'font-family:inherit;white-space:nowrap;flex:none}'
@I@'#%(p)s .cp:hover{border-color:%(b)s;color:%(b)s}'
@I@# La source brute, hors ecran : c est ELLE qu on copie. Copier le
@I@# rendu HTML rendrait des colonnes collees et des lignes cassees,
@I@# donc du texte inutilisable dans un REPL ou un prompt.
@I@'#%(p)s .src{position:absolute;left:-9999px;top:0;'
@I@'width:1px;height:1px;opacity:0}'
@I@'</style>'
@I@% {"p": pid, "t": TEXTE, "g": GRIS, "b": BLEU, "f2": FOND2})


def _bouton(pid):
    \"\"\"Copie le TEXTE BRUT, pas le rendu. navigator.clipboard d abord ;
    si le navigateur le refuse -- il l interdit hors HTTPS sur certaines
    configurations -- on retombe sur la selection + execCommand, qui
    marche encore partout. Le bouton dit ce qui s est passe : muet, on
    ne saurait pas si la copie a eu lieu.\"\"\"
    return (
        '<button class="cp" onclick="(function(b){'
        "var t=document.getElementById('%(p)s_src');"
        "var ok=function(){b.textContent='copie';"
        "setTimeout(function(){b.textContent='Copy'},1400)};"
        "var vieux=function(){t.select();"
        "try{document.execCommand('copy');ok()}"
        "catch(e){b.textContent='echec'}};"
        "if(navigator.clipboard&&navigator.clipboard.writeText)"
        "{navigator.clipboard.writeText(t.value).then(ok,vieux)}"
        "else{vieux()}"
        '})(this)">Copy</button>' % {"p": pid})"""

CORPS = """@I@corps = [_css(pid), '<div id="%s">' % pid,
@I@         '<div class="tete">',
@I@         '<h2 style="color:%s">%s</h2>' % (coul, _e(titre)),
@I@         _bouton(pid),
@I@         '</div>',
@I@         '<div class="age">%s &middot; %s</div>'
@I@         % (_e(entete), _e(str(fichier))),
@I@         '<textarea id="%s_src" class="src" readonly>%s</textarea>'
@I@         % (pid, _e(txt))]"""

PALETTE = """# Les memes verts et rouges que RAILS TRADES et le panneau orderflow --
# la palette GitHub sombre que toute la stack utilise deja. Les
# precedents (#81c995 / #f28b82) etaient les tons pastel de Material :
# justes, mais delaves a cote des autres onglets, et un panneau fade se
# lit moins vite qu un panneau contraste.
VERT = "#3fb950"
ROUGE = "#f85149"
"""

SIGNE = """@I@# En gras, comme dans RAILS TRADES : un chiffre signe est le
@I@# resultat, il doit se voir avant les effectifs et les taux qui
@I@# l entourent.
@I@if v > 0:
@I@    return VERT, True
@I@if v < 0:
@I@    return ROUGE, True"""

VERIF = """@I@# La zone source cachee du bouton Copy contient le texte ENTIER. La
@I@# laisser ici ferait passer le controle a tous les coups, meme si le
@I@# rendu perdait une colonne : le verificateur trouverait chaque ligne
@I@# dans la copie, pas dans le tableau. On la retire d abord.
@I@html = re.sub(r"<textarea\\b[^>]*>.*?</textarea>", " ", html,
@I@              flags=re.S)
@I@nu = re.sub(r"</(tr|div|pre|h2|h3|style)>", "\\n", html)"""


def pose(gabarit, indent):
    """Le jeton @I@ porte l indentation capturee par l ancre. Sans lui il
    faudrait imbriquer deux niveaux de formatage %, et le gabarit CSS --
    qui contient du %(p)s destine au fichier cible -- se ferait manger."""
    return gabarit.replace("@I@", indent)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    for nom, rx in (("la fin de _css", RE_CSS),
                    ("le corps de rendre()", RE_CORPS),
                    ("le nettoyage de verifier()", RE_VERIF),
                    ("la palette", RE_PALETTE),
                    ("la couleur des chiffres signes", RE_SIGNE)):
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1

    neuf = RE_CSS.sub(lambda m: pose(CSS, m.group(1)), src, count=1)
    neuf = RE_CORPS.sub(lambda m: pose(CORPS, m.group(1)), neuf, count=1)
    neuf = RE_VERIF.sub(lambda m: pose(VERIF, m.group(1)), neuf, count=1)
    neuf = RE_PALETTE.sub(lambda m: PALETTE, neuf, count=1)
    neuf = RE_SIGNE.sub(lambda m: pose(SIGNE, m.group(1)), neuf, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Bouton Copy ajoute a cote du titre, sur les TROIS panneaux")
    print("rendus par ce module : RAILS RANGE, RAILS X3, X60 ONSET.")
    print("Il copie le texte brut du .txt, pas le tableau HTML.")
    print()
    print("verifier() ignore desormais la zone source : sans ca, le")
    print("controle des colonnes aurait valide n importe quel rendu.")
    print()
    print("Palette : #81c995 -> #3fb950, #f28b82 -> #f85149, celles de")
    print("RAILS TRADES. Les chiffres signes passent en gras. Aucun")
    print("chiffre n est touche, seulement son affichage.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Redemarre le 8095.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cartes_live_tableau.py -- une vraie table, pas du texte colorie.

CE QUE LE PATCH PRECEDENT A RATE
--------------------------------
Il coloriait le rendu texte. Les couleurs etaient justes, la page
restait illisible : une table alignee a l espace reste une table
alignee a l espace. Colonnes serrees, tirets partout, barres
verticales, tout en chasse fixe a douze pixels. On ne compare rien
la-dedans.

CE QU IL FAUT POUR COMPARER
    Le panneau existe pour une seule chose : mettre cote a cote les
    branches d un meme magic. Ca demande des lignes espacees, des
    nombres alignes a droite en chiffres tabulaires, des noms en
    caracteres proportionnels, et un groupe visuel par magic.

    Donc une vraie <table>, construite depuis les DONNEES et non
    depuis le texte. page_html recoit maintenant le paquet et
    papers_optimized, et refait mesure() / constate() -- les memes
    fonctions que le rendu texte, donc les memes chiffres.

    ATTENDU est volontairement terne, CONSTATE est vif. Ce n est pas
    une coquetterie : la colonne figee ne vaut pas la colonne reelle,
    et la mise en page doit le dire.

    La branche porte une pastille pleine -- 1 bleu, 2 ambre, 5 violet.

LE TEXTE N EST PAS PERDU
    Il vit dans un bloc repliable en bas, avec les explications et le
    detail par strategie. Memes chiffres, meme ordre. Et le bouton
    Copier copie CE texte : c est lui qui se colle dans un message ou
    un tableur, pas le HTML.

CE QUI N EST PAS TOUCHE
    `rendu()` et `cartes\panel_papers_live.txt` sont inchanges. Le
    fichier texte reste la source de verite, et la table en est une
    seconde lecture -- pas une seconde verite.

    Le patch modifie page_html et TROIS lignes de main(), pour lui
    passer les donnees. Rien d autre.

USAGE
-----
    python patch_cartes_live_tableau.py                <- simulation
    python patch_cartes_live_tableau.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\cartes_live.py"
SUFFIXE_BAK = ".bak_tableau"
MARQUEUR = "TABLEAU_V1"
DEBUT = "def page_html(txt"
SUITE = "\ndef defaut("

# --- les trois retouches de main(), pour que page_html voie les donnees
A1 = "    paquet, souci = lis_instantane(args.instantane)"
B1 = ("    donnees = None            # le paquet SI il est frais\n"
      "    paquet, souci = lis_instantane(args.instantane)")

A2 = "            txt = rendu(paquet, po, familles(), args.instantane)"
B2 = ("            donnees = paquet\n"
      "            txt = rendu(paquet, po, familles(), args.instantane)")

A3 = '    io.open(h, "w", encoding="utf-8", newline="").write(page_html(txt))'
B3 = ('    io.open(h, "w", encoding="utf-8", newline="").write(\n'
      '        page_html(txt, donnees, po, familles(), args.instantane))')

NEUVE = r'''def page_html(txt, paquet=None, po=None, noms=None, chemin=""):
    """TABLEAU_V1 -- un FRAGMENT : la route /carte prepose elle-meme le
    style et la barre du tableau de bord. Tout est porte par #cl.

    La table est construite depuis les DONNEES, pas depuis le texte :
    mesure() et constate() sont celles du rendu texte, donc les
    chiffres sont les memes par construction et non par recopie."""
    corps = []
    if paquet and po:
        corps.append(_entete(paquet, chemin))
        corps.append(_tableau(paquet, po, noms or {}))
    else:
        corps.append('<div class="avis">Pas de donnees fraiches. Le'
                     ' rapport ci-dessous dit pourquoi.</div>')
    corps.append('<details><summary>Le rapport complet en texte'
                 ' &mdash; memes chiffres, meme ordre, plus le detail'
                 ' de chaque strategie</summary><div class="txt">'
                 + "\n".join(_habille(txt)) + '</div></details>')
    return (_CSS + '<div id="cl">' + _TETE + _copieur(txt)
            + "".join(corps) + '</div>')


_CSS = """<style>
#cl{padding:16px 20px 40px;background:#0d1117;color:#c9d1d9;
    font:13px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
#cl h1{font:600 19px system-ui;color:#58a6ff;margin:0 0 3px}
#cl .sous{color:#8b949e;margin:0 0 14px;max-width:70ch}
#cl .cles{margin:0 0 18px}
#cl .cle{display:inline-block;padding:2px 10px;border-radius:11px;
    font-size:11.5px;font-weight:600;color:#0d1117;margin-right:7px}
#cl .g1{background:#58a6ff}
#cl .g2{background:#d29922}
#cl .g5{background:#a371f7}
#cl .tuiles{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 20px}
#cl .tuile{background:#161b22;border:1px solid #30363d;border-radius:7px;
    padding:9px 14px;min-width:118px}
#cl .lib{color:#8b949e;font-size:11px;text-transform:uppercase;
    letter-spacing:.06em}
#cl .val{font:600 16px ui-monospace,Consolas,monospace;color:#e6edf3;
    font-variant-numeric:tabular-nums}
#cl table{border-collapse:collapse;width:100%;margin:0 0 20px}
#cl th{padding:7px 10px;text-align:right;color:#8b949e;font-size:11px;
    font-weight:600;text-transform:uppercase;letter-spacing:.05em;
    border-bottom:1px solid #30363d;white-space:nowrap}
#cl td{padding:7px 10px;text-align:right;border-bottom:1px solid #161b22;
    font-variant-numeric:tabular-nums;white-space:nowrap}
#cl tr:hover td{background:#161b22}
#cl tr.sep td{border-top:1px solid #30363d}
#cl th.ga{color:#8b949e;text-align:center;background:#12171f}
#cl th.gc{color:#58a6ff;text-align:center;background:#0f1c2c}
#cl td.mag{text-align:left;color:#d29922;font-weight:600;
    font-family:ui-monospace,Consolas,monospace}
#cl td.nom{text-align:left;color:#e6edf3;white-space:normal}
#cl td.att{color:#6e7681}
#cl td.vide{color:#484f58}
#cl .vert{color:#3fb950;font-weight:600}
#cl .rouge{color:#f85149;font-weight:600}
#cl .pas{display:inline-block;min-width:22px;padding:1px 8px;
    border-radius:10px;font-size:11px;font-weight:700;color:#0d1117}
#cl button{background:#21262d;color:#c9d1d9;border:1px solid #30363d;
    border-radius:6px;padding:6px 14px;font:600 12px system-ui;
    cursor:pointer;margin:0 0 18px}
#cl button:hover{background:#30363d;color:#e6edf3}
#cl textarea{position:fixed;top:-2000px;left:-2000px;width:10px;
    height:10px;opacity:0}
#cl .avis{background:#2b2210;border:1px solid #d29922;border-radius:7px;
    padding:11px 14px;margin:0 0 18px;color:#e6edf3}
#cl details{border-top:1px solid #30363d;padding-top:12px}
#cl summary{cursor:pointer;color:#8b949e;font-weight:600;
    padding:5px 0;list-style:none}
#cl summary:hover{color:#58a6ff}
#cl .txt{font:12px/1.5 ui-monospace,Consolas,monospace;color:#c9d1d9;
    overflow-x:auto;margin-top:10px}
#cl .txt .l{white-space:pre}
#cl .txt .v{height:9px}
#cl .txt h2{font:600 11px system-ui;letter-spacing:.09em;
    text-transform:uppercase;color:#0d1117;background:#58a6ff;
    padding:5px 11px;border-radius:5px;margin:20px 0 9px;
    display:inline-block}
#cl .txt hr{border:0;border-top:1px solid #30363d;margin:8px 0}
#cl .txt .tete{color:#8b949e;font-weight:600}
#cl .txt .cst{color:#58a6ff}
#cl .txt .att{color:#8b949e}
#cl .txt .det,#cl .txt .fort{color:#e6edf3;font-weight:600}
#cl .txt .mag{color:#d29922;font-weight:600}
</style>"""

_TETE = ("""<h1>Cartes live &mdash; les papers sur le compte dedie</h1>
<div class="sous">Meme entree, meme lot, meme instant pour les trois
branches. Seule la sortie, ou l entree pour la 5, les separe.</div>
<div class="cles"><span class="cle g1">1 &middot; exempt des sorties</span>
<span class="cle g2">2 &middot; soumis aux sorties</span>
<span class="cle g5">5 &middot; entree filtree CVD</span></div>""")

_SIGNE = re.compile(r"(?<![\w.])([+-]\d+\.\d{2})(?!\d)")
_MAGIC = re.compile(r"^(\s*)(\d{6,7})")
BRANCHES = (1, 2, 5)


def _echappe(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _copieur(txt):
    """Le bouton copie le TEXTE, pas le HTML : c est lui qui se colle
    dans un message ou un tableur. La zone de saisie est hors ecran
    plutot que masquee -- select() ne marche pas sur du display:none.
    execCommand est garde en secours : navigator.clipboard exige un
    contexte sur, ce que le panneau vu par son adresse IP n est pas."""
    return ('<textarea id="cltxt" readonly>' + _echappe(txt) + '</textarea>'
            '<button id="clbtn" onclick="clCopie()">Copier le rapport'
            '</button>'
            '<script>function clCopie(){'
            'var t=document.getElementById("cltxt"),'
            'b=document.getElementById("clbtn"),v=b.textContent;'
            'try{t.select();document.execCommand("copy")}catch(e){}'
            'if(navigator.clipboard){try{navigator.clipboard.writeText('
            't.value)}catch(e){}}'
            'b.textContent="copie";'
            'setTimeout(function(){b.textContent=v},1400);}</script>')


def _entete(paquet, chemin):
    c = paquet.get("compte", {})
    age = time.time() - float(paquet.get("ts", 0))
    ecart = c.get("equite", 0.0) - c.get("solde", 0.0)
    t = [("compte", masque(c.get("login", 0)), ""),
         ("serveur", c.get("serveur", "--"), ""),
         ("solde", "%.2f" % c.get("solde", 0.0), ""),
         ("equite", "%.2f" % c.get("equite", 0.0), ""),
         ("flottant", "%+.2f" % ecart,
          "vert" if ecart > 0 else ("rouge" if ecart < 0 else "")),
         ("niveau", "%.0f %%" % c.get("niveau", 0.0), ""),
         ("instantane", "%.0f s" % age, "")]
    return ('<div class="tuiles">' + "".join(
        '<div class="tuile"><div class="lib">%s</div>'
        '<div class="val %s">%s</div></div>' % (lib, cls, _echappe(str(val)))
        for lib, val, cls in t) + '</div>')


def _pct(v):
    return "--" if v is None else "%.0f&#37;" % (100 * v)


def _f(v, f="%.2f"):
    return "--" if v is None else f % v


def _sous(v):
    """Une cellule de montant : vert au-dessus de zero, rouge en
    dessous, neutre a zero -- un zero n est ni un gain ni une perte."""
    if v is None:
        return '<td class="vide">--</td>'
    k = "vert" if v > 0 else ("rouge" if v < 0 else "")
    return '<td class="%s">%+.2f</td>' % (k, v)


def _rang(mag, nom, br, att, c, neuf):
    o = ['<tr class="sep">' if neuf else '<tr>',
         '<td class="mag">%d</td>' % mag,
         '<td class="nom">%s</td>' % _echappe(nom),
         '<td><span class="pas g%d">%d</span></td>' % (br, br)]
    if att is None:
        o += ['<td class="vide">--</td>'] * 4
    else:
        n_max, taux, borne, pnl_tr = att
        o += ['<td class="att">%d</td>' % n_max,
              '<td class="att">%s</td>' % _pct(taux),
              '<td class="att">%s</td>' % _pct(borne),
              '<td class="att">%s</td>' % _f(pnl_tr)]
    if c is None:
        o += ['<td class="vide">0</td>'] + ['<td class="vide">--</td>'] * 6
    else:
        o += ['<td>%d</td>' % c["n"],
              '<td>%s</td>' % _pct(c["taux"]),
              '<td>%s</td>' % _pct(c["borne"]),
              '<td>%s</td>' % _f(c["pnl_tr"]),
              _sous(c["pnl"]),
              '<td>%d</td>' % c["ouvertes"],
              _sous(c["latent"]) if c["ouvertes"] else
              '<td class="vide">--</td>']
    o.append('</tr>')
    return "".join(o)


def _tableau(paquet, po, noms):
    """Memes fonctions que le rendu texte -- mesure() et constate() --
    donc memes chiffres par construction, et non par recopie."""
    par = mesure(paquet)
    vus, lignes = set(), []
    for s in po.STRATEGIES:
        n_max, n_tot, taux, pnl_tr = po.agrege(s["croise"])
        att = (n_max, taux, po.wilson_bas(taux, n_tot), pnl_tr)
        for br in BRANCHES:
            c = constate(par.get((s["magic"], br)), po)
            if br != 1 and c is None:
                continue
            vus.add((s["magic"], br))
            lignes.append((s["magic"], s["nom"], br, att, c))
    for mag, br in sorted(k for k in par if k not in vus):
        nom, fam = noms.get(mag, ("(non repertorie)", "?"))
        lignes.append((mag, "%s [%s]" % (nom, fam), br, None,
                       constate(par.get((mag, br)), po)))

    corps, precedent = [], None
    for mag, nom, br, att, c in lignes:
        corps.append(_rang(mag, nom, br, att, c, mag != precedent))
        precedent = mag
    return ('<table><thead><tr>'
            '<th colspan="3"></th>'
            '<th colspan="4" class="ga">ATTENDU &middot; panneau papier,'
            ' fige</th>'
            '<th colspan="7" class="gc">CONSTATE &middot; reel</th>'
            '</tr><tr>'
            '<th style="text-align:left">Magic</th>'
            '<th style="text-align:left">Nom</th><th>Br</th>'
            '<th>n max</th><th>taux</th><th>borne</th><th>PnL/tr</th>'
            '<th>n</th><th>taux</th><th>borne</th><th>PnL/tr</th>'
            '<th>PnL</th><th>ouv.</th><th>latent</th>'
            '</tr></thead><tbody>' + "".join(corps) + '</tbody></table>')


def _nombres(e):
    def f(m):
        v = m.group(1)
        if float(v) == 0.0:
            return v
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
    elif _MAGIC.match(l):
        cls += "det"
        e = _MAGIC.sub(r'\1<b class="mag">\2</b>', e, count=1)
    elif s.startswith("MAGIC") or "A T T E N D U" in l:
        cls += "tete"
    elif len(s) > 12 and s == s.upper():
        cls += "fort"
    return '<div class="%s">%s</div>' % (cls.strip(), e)


def _habille(txt):
    L = txt.split("\n")
    out, i, n = [], 0, len(txt.split("\n"))
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
    if s.count(DEBUT) != 1:
        return None, "def page_html attendue 1 fois, trouvee %d" % s.count(DEBUT)
    for motif, quoi in ((A1, "l appel a lis_instantane"),
                        (A2, "l appel a rendu()"),
                        (A3, "l ecriture du HTML")):
        if s.count(motif) != 1:
            return None, "%s attendu 1 fois, trouve %d" % (quoi,
                                                           s.count(motif))
    i = s.index(DEBUT)
    j = s.find(SUITE, i)
    if j < 0:
        return None, "def defaut( introuvable apres page_html"
    for m in ("import re", "import time", "def mesure(", "def constate(",
              "def masque("):
        if m not in s:
            return None, "%s absent du fichier" % m
    s = s[:i] + NEUVE + s[j + 1:]
    for a, b in ((A1, B1), (A2, B2), (A3, B3)):
        s = s.replace(a, b, 1)
    return s, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 68)
    print("patch_cartes_live_tableau -- %s"
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
        print("Deja pose : page_html rend deja une vraie table.")
        return 0

    neuf, err = applique(s)
    if neuf is None:
        print("")
        print("REFUS : %s." % err)
        return 1
    print("        page_html unique, les 3 ancres de main() uniques.")
    print("")
    print("a faire :")
    print("   ~ page_html construit une <table> depuis les DONNEES")
    print("   ~ main() lui passe le paquet, po, les noms et le chemin")
    print("   + tuiles compte / solde / equite / flottant / instantane")
    print("   + pastille de branche : 1 bleu, 2 ambre, 5 violet")
    print("   + ATTENDU terne, CONSTATE vif, montants vert et rouge")
    print("   + bouton Copier -- il copie le TEXTE, pas le HTML")
    print("   + le rapport texte complet en bloc repliable")
    print("   = rendu() et panel_papers_live.txt INCHANGES")

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
    manques = [x for x in (MARQUEUR, "_tableau", "donnees = paquet",
                           "def defaut(", "Copier le rapport")
               if x not in relu]
    if manques:
        print("relu  : INCOMPLET, manque %s -- RESTAURER %s"
              % (", ".join(manques), bak))
        return 1
    try:
        compile(relu, a.cible, "exec")
        print("relu  : les cinq marques y sont, et le fichier compile.")
    except SyntaxError as e:
        print("relu  : ERREUR DE SYNTAXE ligne %s -- RESTAURER %s"
              % (e.lineno, bak))
        return 1

    print("")
    print("-" * 68)
    print("Relancer `python cartes_live.py`, puis rafraichir l onglet.")
    print("Rien a redemarrer : la route relit le dossier a chaque")
    print("requete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

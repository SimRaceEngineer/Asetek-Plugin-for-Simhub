#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cartes_live_synthese.py -- l actif d abord, l ecart calcule.

LA QUESTION QUE LA TABLE CROISEE NE POSAIT PAS
----------------------------------------------
Elle compare les branches A L INTERIEUR d un magic. C est la bonne
maille pour juger une strategie. Ce n est pas la bonne pour juger un
INSTRUMENT.

    "Sur US30, la gestion de sortie aide-t-elle ou nuit-elle ?"

Cette question-la traverse toutes les strategies. Avec trente magics a
l ecran, y repondre demandait d additionner de tete. On l additionne
donc pour de bon : une table de synthese, une ligne par actif, toutes
strategies confondues, posee AVANT le detail.

LES DEUX ECARTS NE PORTENT PAS SUR LA MEME GRANDEUR
    C est deliberé, et c est le coeur de ce patch.

    2 moins 1, en PnL. Les deux branches ont la MEME entree, au meme
    instant, pour le meme lot -- leurs effectifs sont egaux par
    construction. Comparer les montants a donc un sens, et la
    difference ne peut venir que de la sortie.

    5 moins 1, en PnL PAR TRADE. La branche 5 REFUSE des entrees :
    son effectif est plus petit par construction. Comparer les
    montants mesurerait surtout combien de trades elle a pris, pas
    s ils etaient meilleurs. Le PnL par trade est la seule grandeur
    qui compare la qualite au lieu de la quantite.

    Afficher le meme ecart des deux cotes aurait ete plus joli et
    faux. Un tableau qui invite a une mauvaise comparaison est pire
    qu un tableau qui n en propose aucune.

LA LIGNE "toutes"
    Elle somme les actifs. Sur les strategies definies PAR l actif --
    220004 est "US30 vendeur / US500 acheteur" -- elle melange des
    choses differentes, et c est pour ca qu elle vient en dernier et
    non en premier.

USAGE
-----
    python patch_cartes_live_synthese.py                <- simulation
    python patch_cartes_live_synthese.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\cartes_live.py"
SUFFIXE_BAK = ".bak_synthese"
MARQUEUR = "SYNTHESE_V1"

A_APPEL = ("        corps.append(_entete(paquet, chemin))\n"
           "        corps.append(_tableau(paquet, po, noms or {}))")
B_APPEL = ("        corps.append(_entete(paquet, chemin))\n"
           "        corps.append(_synthese(paquet, po))\n"
           "        corps.append(_tableau(paquet, po, noms or {}))")

A_CSS = "#cl td.b5{background:rgba(163,113,247,.06)}"
B_CSS = """#cl td.b5{background:rgba(163,113,247,.06)}
#cl h3{font:600 12px system-ui;letter-spacing:.07em;text-transform:uppercase;
    color:#8b949e;margin:4px 0 9px;border-bottom:1px solid #30363d;
    padding-bottom:7px}
#cl .note{color:#8b949e;font-size:11.5px;margin:-4px 0 16px;
    max-width:92ch;line-height:1.5}
#cl th.he{background:#1b1420;color:#e6edf3;text-align:center}
#cl td.ec{background:rgba(230,237,243,.04);font-weight:600}
#cl tr.syn td{border-bottom:1px solid #21262d}
#cl tr.syntot td{border-top:1px solid #30363d;font-weight:700}
#cl tr.syntot td.act{color:#8b949e;font-style:italic}"""

A_INS = "\ndef _nombres("

NEUVE = r'''def _somme(cptrs):
    """SYNTHESE_V1 -- additionne des compteurs bruts, pas des taux. Un
    taux moyen de taux serait faux des que les effectifs different."""
    t = {"n": 0, "gagnants": 0, "pnl": 0.0, "ouvertes": 0, "latent": 0.0,
         "symboles": set()}
    for c in cptrs:
        if not c:
            continue
        t["n"] += c["n"]
        t["gagnants"] += c["gagnants"]
        t["pnl"] += c["pnl"]
        t["ouvertes"] += c["ouvertes"]
        t["latent"] += c["latent"]
    return t


def _cell_ec(v, fmt="%+.2f"):
    if v is None:
        return '<td class="vide ec">--</td>'
    k = "vert" if v > 0 else ("rouge" if v < 0 else "")
    return '<td class="ec %s">%s</td>' % (k, fmt % v)


def _synthese(paquet, po):
    """L actif d abord, toutes strategies confondues.

    Les deux ecarts ne portent PAS sur la meme grandeur, et c est
    voulu. 2 moins 1 en PnL : memes entrees, memes effectifs, la
    difference ne peut venir que de la sortie. 5 moins 1 en PnL par
    trade : la branche 5 refuse des entrees, son effectif est plus
    petit par construction, et comparer les montants mesurerait le
    nombre de trades au lieu de leur qualite."""
    fin = _cpt_actif(paquet)
    actifs = sorted(set(s for _, _, s in fin))
    if not actifs:
        return ""

    corps = []
    for sym in actifs + [None]:
        par = {}
        for br in BRANCHES:
            src = [c for (m, b, s), c in fin.items()
                   if b == br and (sym is None or s == sym)]
            par[br] = constate(_somme(src), po)
        un, deux, cinq = par[1], par[2], par[5]
        ec_pnl = (None if (un is None or deux is None)
                  else deux["pnl"] - un["pnl"])
        ec_tr = (None if (un is None or cinq is None)
                 else cinq["pnl_tr"] - un["pnl_tr"])
        corps.append(
            '<tr class="%s"><td class="act">%s</td>%s%s%s</tr>'
            % ("syntot" if sym is None else "syn",
               "toutes" if sym is None else _echappe(sym),
               "".join(_bloc(par[br], br) for br in BRANCHES),
               _cell_ec(ec_pnl), _cell_ec(ec_tr)))

    tete = "".join('<th colspan="4" class="h%d">MIROIR %d</th>' % (br, br)
                   for br in BRANCHES)
    return ('<h3>Synthese par actif &mdash; toutes strategies confondues'
            '</h3>'
            '<div class="note">L ecart <b>2 &minus; 1</b> est en PnL : les'
            ' deux branches ont la meme entree au meme instant, donc le'
            ' meme effectif, et la difference ne peut venir que de la'
            ' sortie. L ecart <b>5 &minus; 1</b> est en PnL par trade :'
            ' la branche 5 refuse des entrees, son effectif est plus petit'
            ' par construction, et comparer les montants mesurerait le'
            ' nombre de trades au lieu de leur qualite.</div>'
            '<table><thead><tr><th></th>' + tete
            + '<th colspan="2" class="he">ECART</th></tr><tr>'
            '<th style="text-align:left">actif</th>'
            + ('<th>n</th><th>taux</th><th>PnL/tr</th><th>PnL</th>' * 3)
            + '<th>2 &minus; 1<br>PnL</th><th>5 &minus; 1<br>PnL/tr</th>'
            '</tr></thead><tbody>' + "".join(corps) + '</tbody></table>')

'''


def lire(chemin):
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        return f.read()


def applique(s):
    if "CROISE_V1" not in s:
        return None, "CROISE_V1 absent : poser patch_cartes_live_croise"
    for motif, quoi in ((A_APPEL, "l appel a _tableau dans page_html"),
                        (A_CSS, "la regle de style td.b5"),
                        (A_INS, "def _nombres(")):
        if s.count(motif) != 1:
            return None, "%s attendu 1 fois, trouve %d" % (quoi,
                                                           s.count(motif))
    s = s.replace(A_INS, "\n" + NEUVE + A_INS, 1)
    s = s.replace(A_APPEL, B_APPEL, 1)
    return s.replace(A_CSS, B_CSS, 1), ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 68)
    print("patch_cartes_live_synthese -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 68)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))
    print("        CROISE_V1 : %s" % ("oui" if "CROISE_V1" in s else "NON"))
    if MARQUEUR in s:
        print("")
        print("Deja pose : la synthese par actif est la.")
        return 0

    neuf, err = applique(s)
    if neuf is None:
        print("")
        print("REFUS : %s." % err)
        return 1
    print("        les trois ancres uniques.")
    print("")
    print("a faire :")
    print("   + table de synthese par actif, AVANT le detail")
    print("     une ligne par instrument, toutes strategies confondues")
    print("   + ecart 2 - 1 en PnL      (memes entrees, memes effectifs)")
    print("   + ecart 5 - 1 en PnL/trade (effectifs differents par")
    print("     construction : le montant mesurerait la quantite)")
    print("   = la table croisee et le texte INCHANGES")

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
    manques = [x for x in (MARQUEUR, "def _synthese(", "corps.append(_synthese",
                           "Synthese par actif", "def _nombres(")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())

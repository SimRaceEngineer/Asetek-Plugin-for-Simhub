#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cartes_live_actifs.py -- l actif attendu, et l actif touche.

CE QUI MANQUAIT
---------------
La table donnait le taux, la borne et le PnL, mais pas sur QUOI. Or
la moitie des strategies du papier sont definies par leur actif --
220004 est litteralement "US30 vendeur / US500 acheteur". Comparer un
attendu et un realise sans savoir s ils portent sur le meme instrument,
c est comparer deux choses qui n ont peut-etre rien a voir.

CE QU ON AJOUTE, ET D OU CA VIENT
    Deux colonnes, une par groupe.

    Cote ATTENDU : le champ `actif` de papers_optimized, tel quel.
    C est la definition de la strategie, pas une deduction.

    Cote CONSTATE : les symboles REELLEMENT touches, tires des
    compteurs de mesure() -- qui les collectait deja dans un ensemble
    sans que personne ne les lise. Aucune liste ecrite a la main :
    si le miroir a pris un actif qu on n attendait pas, il apparait.

    C est tout l interet de la colonne. Un ecart entre les deux se
    voit sur la meme ligne, a l oeil, sans rien recouper.

CE QUI N EST PAS TOUCHE
    Ni rendu(), ni le fichier texte, ni le reste de la table. Le patch
    remplace _rang et _tableau -- deux fonctions contigues -- et
    ajoute trois regles de style. Rien d autre.

USAGE
-----
    python patch_cartes_live_actifs.py                <- simulation
    python patch_cartes_live_actifs.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\cartes_live.py"
SUFFIXE_BAK = ".bak_actifs"
MARQUEUR = "ACTIFS_V1"
DEBUT = "def _rang(mag, nom, br, att, c, neuf):"
SUITE = "\ndef _nombres("

A_CSS = "#cl td.vide{color:#484f58}"
B_CSS = ("#cl td.vide{color:#484f58}\n"
         "#cl td.act{text-align:left;white-space:normal;font-size:11.5px;\n"
         "    color:#8b949e;max-width:190px;line-height:1.35}\n"
         "#cl td.act.reel{color:#c9d1d9}\n"
         "#cl td.act.hors{color:#d29922;font-weight:600}")

NEUVE = r'''def _actifs(brut):
    """ACTIFS_V1 -- les symboles REELLEMENT touches, tires des
    compteurs de mesure(). Ils y etaient deja collectes ; personne ne
    les lisait. Rien n est ecrit a la main : un actif inattendu se
    montre de lui-meme."""
    if not brut:
        return None
    s = sorted(brut.get("symboles") or ())
    return ", ".join(s) if s else None


def _hors_sujet(attendu, reels):
    """Vrai si un symbole touche n est nomme nulle part dans l actif
    attendu. Comparaison volontairement grossiere -- le champ attendu
    est une phrase ("US30 vendeur / US500 acheteur"), pas une liste --
    donc on cherche seulement si le symbole y figure. Dans le doute
    elle se tait : mieux vaut ne rien signaler qu alerter a tort."""
    if not attendu or not reels:
        return False
    a = attendu.upper()
    return any(s.strip().upper() not in a for s in reels.split(","))


def _rang(mag, nom, br, att, act_att, c, brut, neuf):
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
    o.append('<td class="act">%s</td>'
             % (_echappe(act_att) if act_att else "--"))
    reels = _actifs(brut)
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
    if reels:
        hors = " hors" if _hors_sujet(act_att, reels) else ""
        o.append('<td class="act reel%s" title="%s">%s</td>'
                 % (hors,
                    "un symbole hors de l actif attendu" if hors else "",
                    _echappe(reels)))
    else:
        o.append('<td class="vide">--</td>')
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
            brut = par.get((s["magic"], br))
            c = constate(brut, po)
            if br != 1 and c is None:
                continue
            vus.add((s["magic"], br))
            lignes.append((s["magic"], s["nom"], br, att,
                           s.get("actif"), c, brut))
    for mag, br in sorted(k for k in par if k not in vus):
        nom, fam = noms.get(mag, ("(non repertorie)", "?"))
        brut = par.get((mag, br))
        lignes.append((mag, "%s [%s]" % (nom, fam), br, None, None,
                       constate(brut, po), brut))

    corps, precedent = [], None
    for mag, nom, br, att, act, c, brut in lignes:
        corps.append(_rang(mag, nom, br, att, act, c, brut,
                           mag != precedent))
        precedent = mag
    return ('<table><thead><tr>'
            '<th colspan="3"></th>'
            '<th colspan="5" class="ga">ATTENDU &middot; panneau papier,'
            ' fige</th>'
            '<th colspan="8" class="gc">CONSTATE &middot; reel</th>'
            '</tr><tr>'
            '<th style="text-align:left">Magic</th>'
            '<th style="text-align:left">Nom</th><th>Br</th>'
            '<th>n max</th><th>taux</th><th>borne</th><th>PnL/tr</th>'
            '<th style="text-align:left">actifs</th>'
            '<th>n</th><th>taux</th><th>borne</th><th>PnL/tr</th>'
            '<th>PnL</th><th>ouv.</th><th>latent</th>'
            '<th style="text-align:left">actifs touches</th>'
            '</tr></thead><tbody>' + "".join(corps) + '</tbody></table>')


'''


def lire(chemin):
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        return f.read()


def applique(s):
    if s.count(DEBUT) != 1:
        return None, ("l ancienne _rang attendue 1 fois, trouvee %d"
                      " -- le patch TABLEAU_V1 est-il pose ?"
                      % s.count(DEBUT))
    if s.count(A_CSS) != 1:
        return None, "la regle de style td.vide attendue 1 fois, trouvee %d" \
                     % s.count(A_CSS)
    i = s.index(DEBUT)
    j = s.find(SUITE, i)
    if j < 0:
        return None, "def _nombres( introuvable apres _rang"
    if "TABLEAU_V1" not in s:
        return None, "TABLEAU_V1 absent : poser patch_cartes_live_tableau"
    s = s[:i] + NEUVE + s[j + 1:]
    return s.replace(A_CSS, B_CSS, 1), ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 68)
    print("patch_cartes_live_actifs -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 68)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))
    print("        table posee : %s"
          % ("oui" if "TABLEAU_V1" in s else "NON"))
    if MARQUEUR in s:
        print("")
        print("Deja pose : les colonnes actifs sont la.")
        return 0

    neuf, err = applique(s)
    if neuf is None:
        print("")
        print("REFUS : %s." % err)
        return 1
    print("        _rang et _tableau uniques, style td.vide unique.")
    print("")
    print("a faire :")
    print("   + colonne ACTIFS cote ATTENDU -- le champ de la strategie")
    print("   + colonne ACTIFS TOUCHES cote CONSTATE -- les symboles")
    print("     reels, tires des compteurs, jamais ecrits a la main")
    print("   + un symbole hors de l actif attendu passe en ambre")
    print("   = rendu(), le texte et le reste de la table INCHANGES")

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
    manques = [x for x in (MARQUEUR, "_hors_sujet", "actifs touches",
                           'colspan="8"', "def _nombres(")
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

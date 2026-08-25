#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cartes_live_croise.py -- magic x actif x branche, croises.

POURQUOI TROIS LIGNES NE SE COMPARENT PAS
-----------------------------------------
La table precedente empilait les branches : une ligne par branche, la
meme colonne PnL a trois hauteurs differentes. Pour comparer, l oeil
devait descendre, retenir un chiffre, redescendre. Sur trente lignes
c est fatigant, et sur cinquante on renonce.

Une comparaison se lit de GAUCHE A DROITE, sur la meme ligne. Donc les
branches deviennent des COLONNES.

LES TROIS ENTREES
    magic     bande de titre, avec l attendu du papier a droite
    actif     une ligne par symbole reellement touche, puis "toutes"
    branche   trois blocs de colonnes -- miroir 1, 2 et 5

    Lire une ligne, c est voir ce que les trois branches ont fait DU
    MEME magic SUR LE MEME actif. L ecart 1 contre 2 ne mesure alors
    que la sortie, l ecart 1 contre 5 que le filtre d entree, et ni
    l un ni l autre n est pollue par un melange d instruments.

D OU VIENNENT LES CHIFFRES PAR ACTIF
    mesure() ne gardait des symboles qu un ENSEMBLE : on savait
    lesquels avaient ete touches, pas ce qu ils avaient rapporte.
    _cpt_actif refait le meme comptage avec le symbole dans la cle.

    Meme regle qu ailleurs : une AFFAIRE, pas un deal. Et la ligne
    "toutes" vient de mesure(), pas d une somme des lignes actif --
    si les deux divergeaient un jour, la divergence serait visible au
    lieu d etre masquee par une addition.

CE QUI REMPLACE QUOI
    Ce patch REMPLACE patch_cartes_live_actifs : il fait ce qu il
    faisait, en mieux. Ne pas poser les deux. Il exige en revanche
    TABLEAU_V1, qui apporte page_html et le reste de la page.

USAGE
-----
    python patch_cartes_live_croise.py                <- simulation
    python patch_cartes_live_croise.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\cartes_live.py"
SUFFIXE_BAK = ".bak_croise"
MARQUEUR = "CROISE_V1"
DEBUT = "def _rang("
SUITE = "\ndef _nombres("

A_CSS = "#cl td.vide{color:#484f58}"
B_CSS = """#cl td.vide{color:#484f58}
#cl tr.grp td{background:#161b22;border-top:1px solid #30363d;
    border-bottom:1px solid #30363d;padding:9px 11px;text-align:left}
#cl tr.grp .att2{float:right;color:#8b949e;font-size:11.5px;
    font-weight:400}
#cl tr.grp .hors{color:#d29922;font-weight:600}
#cl td.act{text-align:left;color:#c9d1d9;padding-left:22px}
#cl tr.tot td{font-weight:600}
#cl tr.tot td.act{color:#8b949e;font-style:italic}
#cl th.h1{background:#0f2438;color:#58a6ff;text-align:center}
#cl th.h2{background:#2b2210;color:#d29922;text-align:center}
#cl th.h5{background:#221a33;color:#a371f7;text-align:center}
#cl td.b2{background:rgba(210,153,34,.05)}
#cl td.b5{background:rgba(163,113,247,.06)}"""

NEUVE = r'''def _cpt_actif(paquet):
    """CROISE_V1 -- les compteurs de mesure(), mais avec le SYMBOLE
    dans la cle. mesure() n en gardait qu un ensemble : on savait
    quels actifs avaient ete touches, pas ce qu ils avaient rapporte.

    Meme regle qu ailleurs : une AFFAIRE, pas un deal."""
    par = {}

    def case(mag, sym):
        b, br = base_et_branche(mag)
        return par.setdefault((b, br, sym),
                              {"n": 0, "gagnants": 0, "pnl": 0.0,
                               "ouvertes": 0, "latent": 0.0,
                               "symboles": set()})

    for a in paquet.get("closes", []):
        mag = int(a.get("magic", 0) or 0)
        if not mag:
            continue
        c = case(mag, a.get("sym") or "?")
        c["n"] += 1
        r = float(a.get("resultat", 0.0))
        c["pnl"] += r
        if r > 0:
            c["gagnants"] += 1
    for p in paquet.get("ouvertes", []):
        mag = int(p.get("magic", 0) or 0)
        if not mag:
            continue
        c = case(mag, p.get("sym") or "?")
        c["ouvertes"] += 1
        c["latent"] += float(p.get("latent", 0.0))
    return par


def _bloc(c, br):
    """Les quatre cellules d une branche. Un fond tres leger distingue
    la 2 et la 5 de la 1 sans crier."""
    f = "" if br == 1 else " b%d" % br
    if c is None:
        return ('<td class="vide%s">--</td>' % f) * 4
    return ('<td class="%s">%d</td><td class="%s">%s</td>'
            '<td class="%s">%s</td>%s'
            % (f.strip(), c["n"], f.strip(), _pct(c["taux"]),
               f.strip(), _f(c["pnl_tr"]),
               _sous(c["pnl"], f.strip())))


def _bande(mag, nom, att, act_att, reels):
    """La bande de titre d un magic. L attendu y vit a droite : il n a
    ni branche ni actif, il n a donc pas sa place dans une colonne."""
    if att is None:
        d = "attendu : absent, et non fabrique"
    else:
        n_max, taux, borne, pnl_tr = att
        d = ("attendu : %s &middot; n max %d &middot; %s (borne %s)"
             " &middot; %s/tr"
             % (_echappe(act_att) if act_att else "actif non precise",
                n_max, _pct(taux), _pct(borne), _f(pnl_tr)))
    if act_att and reels:
        a = act_att.upper()
        hors = [s for s in reels if s.upper() not in a]
        if hors:
            d += ('  <span class="hors">hors actif : %s</span>'
                  % _echappe(", ".join(hors)))
    return ('<tr class="grp"><td colspan="13">'
            '<b class="mag">%d</b>&nbsp; %s<span class="att2">%s</span>'
            '</td></tr>' % (mag, _echappe(nom), d))


def _tableau(paquet, po, noms):
    """Trois entrees : le magic en bande, l actif en ligne, la branche
    en colonne. La ligne "toutes" vient de mesure() et non d une somme
    des lignes actif : si les deux divergeaient, ca se verrait."""
    tot = mesure(paquet)
    fin = _cpt_actif(paquet)

    att = {}
    for s in po.STRATEGIES:
        n_max, n_tot, taux, pnl_tr = po.agrege(s["croise"])
        att[s["magic"]] = (s["nom"], s.get("actif"),
                           (n_max, taux, po.wilson_bas(taux, n_tot), pnl_tr))

    magics = sorted(set(m for m, _ in tot) | set(att))
    corps = []
    for mag in magics:
        if mag in att:
            nom, act_att, a = att[mag]
        else:
            n, fam = noms.get(mag, ("(non repertorie)", "?"))
            nom, act_att, a = "%s [%s]" % (n, fam), None, None
        actifs = sorted(set(s for m, _, s in fin if m == mag))
        corps.append(_bande(mag, nom, a, act_att, actifs))
        if not actifs:
            corps.append('<tr><td class="act">aucune affaire</td>'
                         '<td class="vide" colspan="12">--</td></tr>')
            continue
        for sym in actifs:
            corps.append('<tr><td class="act">%s</td>%s</tr>'
                         % (_echappe(sym),
                            "".join(_bloc(constate(fin.get((mag, br, sym)),
                                                   po), br)
                                    for br in BRANCHES)))
        if len(actifs) > 1:
            corps.append('<tr class="tot"><td class="act">toutes</td>%s</tr>'
                         % "".join(_bloc(constate(tot.get((mag, br)), po), br)
                                   for br in BRANCHES))

    tete = "".join('<th colspan="4" class="h%d">MIROIR %d &middot; %s</th>'
                   % (br, br, lib) for br, lib in
                   ((1, "exempt des sorties"),
                    (2, "soumis aux sorties"),
                    (5, "entree filtree CVD")))
    return ('<table><thead><tr><th></th>' + tete + '</tr><tr>'
            '<th style="text-align:left">actif</th>'
            + ('<th>n</th><th>taux</th><th>PnL/tr</th><th>PnL</th>' * 3)
            + '</tr></thead><tbody>' + "".join(corps) + '</tbody></table>')


'''

# _sous prend desormais une classe de fond : une cellule de montant de
# la branche 2 ou 5 doit garder sa teinte comme les autres.
A_SOUS = '''def _sous(v):
    """Une cellule de montant : vert au-dessus de zero, rouge en
    dessous, neutre a zero -- un zero n est ni un gain ni une perte."""
    if v is None:
        return '<td class="vide">--</td>'
    k = "vert" if v > 0 else ("rouge" if v < 0 else "")
    return '<td class="%s">%+.2f</td>' % (k, v)'''

B_SOUS = '''def _sous(v, fond=""):
    """Une cellule de montant : vert au-dessus de zero, rouge en
    dessous, neutre a zero -- un zero n est ni un gain ni une perte.
    `fond` porte la teinte de branche, qui ne doit pas sauter sur les
    cellules colorees."""
    if v is None:
        return '<td class="vide %s">--</td>' % fond
    k = "vert" if v > 0 else ("rouge" if v < 0 else "")
    return '<td class="%s %s">%+.2f</td>' % (k, fond, v)'''


def lire(chemin):
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        return f.read()


def applique(s):
    if "TABLEAU_V1" not in s:
        return None, "TABLEAU_V1 absent : poser patch_cartes_live_tableau"
    if s.count(DEBUT) != 1:
        return None, "def _rang( attendue 1 fois, trouvee %d" % s.count(DEBUT)
    if s.count(A_SOUS) != 1:
        return None, "_sous attendue 1 fois dans sa forme connue"
    if s.count(A_CSS) != 1:
        return None, "la regle de style td.vide attendue 1 fois"
    if "def base_et_branche(" not in s:
        return None, "base_et_branche absente du fichier"
    i = s.index(DEBUT)
    j = s.find(SUITE, i)
    if j < 0:
        return None, "def _nombres( introuvable apres _rang"
    s = s[:i] + NEUVE + s[j + 1:]
    s = s.replace(A_SOUS, B_SOUS, 1)
    return s.replace(A_CSS, B_CSS, 1), ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 68)
    print("patch_cartes_live_croise -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 68)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))
    print("        TABLEAU_V1 : %s" % ("oui" if "TABLEAU_V1" in s else "NON"))
    print("        ACTIFS_V1  : %s  (ce patch le remplace)"
          % ("pose" if "ACTIFS_V1" in s else "absent"))
    if MARQUEUR in s:
        print("")
        print("Deja pose : la table est deja croisee.")
        return 0

    neuf, err = applique(s)
    if neuf is None:
        print("")
        print("REFUS : %s." % err)
        return 1
    print("        _rang, _sous et le style td.vide uniques.")
    print("")
    print("a faire :")
    print("   ~ la table devient un croisement a trois entrees")
    print("     magic en bande, actif en ligne, branche en colonne")
    print("   + _cpt_actif : les memes compteurs, ventiles par symbole")
    print("   + ligne 'toutes' issue de mesure(), pas d une somme")
    print("   + l attendu passe dans la bande de titre du magic")
    print("   + un symbole hors de l actif attendu est signale en ambre")
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
    manques = [x for x in (MARQUEUR, "_cpt_actif", "MIROIR 5",
                           "def _nombres(", "def _sous(v, fond=")
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

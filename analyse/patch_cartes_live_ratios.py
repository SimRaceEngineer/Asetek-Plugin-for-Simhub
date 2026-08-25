#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cartes_live_ratios.py -- Wilson, RR, PF, Sharpe dans la synthese.

OU LES METTRE, ET SURTOUT OU NE PAS
-----------------------------------
La table croisee descend jusqu a la case magic x actif x branche. A
cette maille, un groupe porte souvent trois ou quatre affaires. Un
facteur de profit calcule sur trois trades vaut zero, un Sharpe sur
trois trades vaut moins que zero -- ils donnent au bruit l apparence
d une mesure.

Et vingt-deux colonnes ne se lisent pas.

Les ratios vont donc dans la SYNTHESE PAR ACTIF, ou chaque ligne
agrege toutes les strategies : c est la seule maille du panneau ou
l effectif justifie qu on les calcule. La table croisee garde ses
quatre colonnes -- n, taux, PnL/trade, PnL -- qui restent honnetes a
tout effectif.

CE QUE LA SYNTHESE DEVIENT
    Une ligne par branche au lieu d un bloc de colonnes : a onze
    mesures, empiler se lit mieux qu etaler. Chaque groupe d actif
    donne donc une ligne 1, une ligne 2, une ligne 5, puis les ecarts.

        n, taux, Wilson 95 %, RR d equilibre, PF, PnL, esperance,
        Sharpe, sigma

    RR eq   (1-p)/p, le ratio gain/perte necessaire pour rentrer dans
            ses frais.
    PF      somme des gains / somme des pertes. "inf" sans perte --
            affiche tel quel plutot que borne, car c est un signal
            d effectif trop faible, pas une performance.
    Sharpe  esperance / sigma, PAR TRADE et NON ANNUALISE. Annualiser
            demanderait de supposer un nombre de trades par an ; on ne
            le suppose pas.

    L ecart 2-1 reste en PnL (memes entrees, memes effectifs) et
    l ecart 5-1 en PnL par trade (la branche 5 refuse des entrees,
    comparer les montants mesurerait la quantite).

CE QU IL A FALLU CHANGER DESSOUS
    PF et sigma demandent les resultats UN PAR UN, que les compteurs
    ne gardaient pas -- ils ne cumulaient qu une somme. mesure(),
    _cpt_actif() et _somme() conservent desormais la liste des
    resultats, et constate() en tire pf, sigma et Sharpe.

USAGE
-----
    python patch_cartes_live_ratios.py                <- simulation
    python patch_cartes_live_ratios.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\cartes_live.py"
SUFFIXE_BAK = ".bak_ratios"
MARQUEUR = "RATIOS_V1"

# --- 1. les compteurs gardent les resultats un par un -----------------
A1 = '''        return par.setdefault((b, br), {"n": 0, "gagnants": 0, "pnl": 0.0,
                                        "ouvertes": 0, "latent": 0.0,
                                        "volume": 0.0, "symboles": set()})'''
B1 = '''        return par.setdefault((b, br), {"n": 0, "gagnants": 0, "pnl": 0.0,
                                        "ouvertes": 0, "latent": 0.0,
                                        "volume": 0.0, "symboles": set(),
                                        "res": []})'''

A2 = '''        return par.setdefault((b, br, sym),
                              {"n": 0, "gagnants": 0, "pnl": 0.0,
                               "ouvertes": 0, "latent": 0.0,
                               "symboles": set()})'''
B2 = '''        return par.setdefault((b, br, sym),
                              {"n": 0, "gagnants": 0, "pnl": 0.0,
                               "ouvertes": 0, "latent": 0.0,
                               "symboles": set(), "res": []})'''

# les deux boucles d accumulation, dans mesure() et dans _cpt_actif()
A3 = '''        c["n"] += 1
        r = float(a.get("resultat", 0.0))
        c["pnl"] += r
        if r > 0:
            c["gagnants"] += 1
        c["volume"] += float(a.get("volume", 0.0))'''
B3 = '''        c["n"] += 1
        r = float(a.get("resultat", 0.0))
        c["pnl"] += r
        c["res"].append(r)
        if r > 0:
            c["gagnants"] += 1
        c["volume"] += float(a.get("volume", 0.0))'''

A4 = '''        c = case(mag, a.get("sym") or "?")
        c["n"] += 1
        r = float(a.get("resultat", 0.0))
        c["pnl"] += r
        if r > 0:
            c["gagnants"] += 1'''
B4 = '''        c = case(mag, a.get("sym") or "?")
        c["n"] += 1
        r = float(a.get("resultat", 0.0))
        c["pnl"] += r
        c["res"].append(r)
        if r > 0:
            c["gagnants"] += 1'''

A5 = '''    t = {"n": 0, "gagnants": 0, "pnl": 0.0, "ouvertes": 0, "latent": 0.0,
         "symboles": set()}
    for c in cptrs:
        if not c:
            continue
        t["n"] += c["n"]
        t["gagnants"] += c["gagnants"]
        t["pnl"] += c["pnl"]
        t["ouvertes"] += c["ouvertes"]
        t["latent"] += c["latent"]
    return t'''
B5 = '''    t = {"n": 0, "gagnants": 0, "pnl": 0.0, "ouvertes": 0, "latent": 0.0,
         "symboles": set(), "res": []}
    for c in cptrs:
        if not c:
            continue
        t["n"] += c["n"]
        t["gagnants"] += c["gagnants"]
        t["pnl"] += c["pnl"]
        t["ouvertes"] += c["ouvertes"]
        t["latent"] += c["latent"]
        t["res"].extend(c.get("res") or [])
    return t'''

# --- 2. constate() en tire PF, sigma et Sharpe ------------------------
A6 = '''    return {"n": c["n"], "taux": p, "borne": po.wilson_bas(p, c["n"]),
            "rr": po.rr_equilibre(p) if p > 0 else float("inf"),
            "pnl": c["pnl"], "pnl_tr": c["pnl"] / float(c["n"]),
            "ouvertes": c["ouvertes"], "latent": c["latent"]}'''
B6 = '''    # RATIOS_V1 -- PF et sigma demandent les resultats UN PAR UN, que
    # les compteurs gardent desormais. Sur une source ancienne sans
    # "res", on rend None plutot qu un zero : un ratio absent se voit,
    # un ratio faux ne se voit pas.
    v = c.get("res") or []
    n = float(c["n"])
    moy = c["pnl"] / n
    sd = ((sum((x - moy) ** 2 for x in v) / (len(v) - 1.0)) ** 0.5
          if len(v) > 1 else None)
    gg = sum(x for x in v if x > 0)
    pp = abs(sum(x for x in v if x < 0))
    return {"n": c["n"], "taux": p, "borne": po.wilson_bas(p, c["n"]),
            "rr": po.rr_equilibre(p) if p > 0 else float("inf"),
            "pnl": c["pnl"], "pnl_tr": moy,
            "ouvertes": c["ouvertes"], "latent": c["latent"],
            "sd": sd,
            "pf": (gg / pp) if pp > 0 else (float("inf") if gg > 0 else None),
            "sharpe": (moy / sd) if (sd and sd > 0) else None}'''

# --- 3. la synthese passe en lignes, avec les onze mesures -----------
A7 = "def _synthese(paquet, po):"
SUITE7 = "\ndef _nombres("

NEUVE = r'''def _inf(v, f="%.2f"):
    """inf s affiche tel quel : c est un signal d effectif trop faible,
    pas une performance qu il faudrait borner. None -> tiret."""
    if v is None:
        return '<td class="vide">--</td>'
    if v == float("inf"):
        return '<td class="vide">inf</td>'
    return '<td>%s</td>' % (f % v)


def _synthese(paquet, po):
    """RATIOS_V1 -- l actif d abord, toutes strategies confondues, et
    une LIGNE par branche : a onze mesures, empiler se lit mieux
    qu etaler.

    Les ratios vivent ici et non dans la table croisee. Celle-ci
    descend a la case magic x actif x branche, ou un groupe porte
    souvent trois affaires -- un PF sur trois trades donne au bruit
    l apparence d une mesure.

    Les deux ecarts ne portent pas sur la meme grandeur, et c est
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
        faites = [br for br in BRANCHES if par[br]]
        if not faites:
            continue
        nom = "toutes" if sym is None else sym
        prem = True
        for br in faites:
            c = par[br]
            corps.append(
                '<tr class="sy%s"><td class="act">%s</td>'
                '<td class="brq"><span class="pas g%d">%d</span></td>'
                '<td>%d</td><td>%s</td><td>%s</td>%s%s%s<td>%s</td>'
                '%s<td class="vide">%s</td></tr>'
                % ("tot" if sym is None else "",
                   _echappe(nom) if prem else "", br, br, c["n"],
                   _pct(c["taux"]), _pct(c["borne"]), _inf(c["rr"]),
                   _inf(c["pf"]), _sous(c["pnl"]), _f(c["pnl_tr"]),
                   _inf(c["sharpe"]),
                   "--" if c["sd"] is None else "%.0f" % c["sd"]))
            prem = False
        un = par[1]
        for br, lib, quoi in ((2, "2 &minus; 1", "pnl"),
                              (5, "5 &minus; 1", "tr")):
            o = par[br]
            if un is None or o is None:
                continue
            if quoi == "pnl":
                v, f, note = o["pnl"] - un["pnl"], "%+.2f", "en PnL"
            else:
                v, f, note = (o["pnl_tr"] - un["pnl_tr"], "%+.2f",
                              "en PnL/trade")
            k = "vert" if v > 0 else ("rouge" if v < 0 else "")
            # La valeur doit tomber SOUS SA PROPRE colonne : le 2-1 est
            # un PnL, le 5-1 un PnL par trade. Un nombre range sous le
            # mauvais en-tete est un nombre qui ment.
            av, ap = (5, 3) if quoi == "pnl" else (6, 2)
            corps.append('<tr class="syec"><td></td><td class="brq">%s</td>'
                         '<td colspan="%d" class="note2">%s</td>'
                         '<td class="ec %s">%s</td>'
                         '<td colspan="%d" class="note2">%s</td></tr>'
                         % (lib, av, note, k, f % v, ap,
                            "memes effectifs" if quoi == "pnl"
                            else "effectifs differents par construction"))
    return ('<h3>Synthese par actif &mdash; toutes strategies confondues'
            '</h3>'
            '<div class="note">Les ratios vivent ici et non dans la table'
            ' croisee : celle-ci descend a la case magic &times; actif'
            ' &times; branche, ou un groupe porte souvent trois affaires,'
            ' et un facteur de profit sur trois trades donne au bruit'
            ' l apparence d une mesure.<br>'
            '<b>Wilson</b> = borne basse du taux a 95 %.'
            ' <b>RR eq</b> = (1-p)/p, le ratio necessaire pour rentrer'
            ' dans ses frais. <b>PF</b> = gains / pertes, "inf" sans'
            ' perte. <b>Sharpe</b> = esperance / sigma, <b>par trade et'
            ' non annualise</b> : annualiser demanderait de supposer un'
            ' nombre de trades par an, on ne le suppose pas.</div>'
            '<table><thead><tr>'
            '<th style="text-align:left">actif</th>'
            '<th style="text-align:left">br</th><th>n</th><th>taux</th>'
            '<th>Wilson</th><th>RR eq</th><th>PF</th><th>PnL</th>'
            '<th>esp</th><th>Sharpe</th><th>sigma</th>'
            '</tr></thead><tbody>' + "".join(corps) + '</tbody></table>')


'''

A_CSS = "#cl tr.syntot td.act{color:#8b949e;font-style:italic}"
B_CSS = """#cl tr.syntot td.act{color:#8b949e;font-style:italic}
#cl td.brq{text-align:left}
#cl tr.sytot td{background:rgba(230,237,243,.03);font-weight:600}
#cl tr.syec td{background:rgba(230,237,243,.05);
    border-bottom:1px solid #30363d}
#cl td.note2{text-align:left;color:#6e7681;font-size:11px;
    font-style:italic}"""

REMPL = ((A1, B1, "le compteur de mesure()"),
         (A2, B2, "le compteur de _cpt_actif()"),
         (A3, B3, "l accumulation de mesure()"),
         (A4, B4, "l accumulation de _cpt_actif()"),
         (A5, B5, "_somme()"),
         (A6, B6, "le retour de constate()"),
         (A_CSS, B_CSS, "le style syntot"))


def lire(chemin):
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        return f.read()


def applique(s):
    if "SYNTHESE_V1" not in s:
        return None, "SYNTHESE_V1 absent : poser patch_cartes_live_synthese"
    for a, _, quoi in REMPL:
        if s.count(a) != 1:
            return None, "%s attendu 1 fois, trouve %d" % (quoi, s.count(a))
    if s.count(A7) != 1:
        return None, "def _synthese attendue 1 fois, trouvee %d" % s.count(A7)
    i = s.index(A7)
    j = s.find(SUITE7, i)
    if j < 0:
        return None, "def _nombres( introuvable apres _synthese"
    s = s[:i] + NEUVE + s[j + 1:]
    for a, b, _ in REMPL:
        s = s.replace(a, b, 1)
    return s, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 68)
    print("patch_cartes_live_ratios -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 68)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))
    print("        SYNTHESE_V1 : %s"
          % ("oui" if "SYNTHESE_V1" in s else "NON"))
    if MARQUEUR in s:
        print("")
        print("Deja pose : les ratios sont dans la synthese.")
        return 0

    neuf, err = applique(s)
    if neuf is None:
        print("")
        print("REFUS : %s." % err)
        return 1
    print("        les huit ancres uniques.")
    print("")
    print("a faire :")
    print("   ~ les compteurs gardent les resultats un par un")
    print("     (PF et sigma les exigent ; une somme ne suffit pas)")
    print("   + constate() rend PF, sigma et Sharpe")
    print("   ~ la synthese passe en LIGNES par branche, onze mesures :")
    print("     n, taux, Wilson, RR eq, PF, PnL, esp, Sharpe, sigma")
    print("   = la table croisee reste a quatre colonnes -- a sa maille")
    print("     un PF sur trois trades ne mesurerait que du bruit")

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
    manques = [x for x in (MARQUEUR, "def _inf(", '"res": []',
                           "Sharpe", "def _nombres(") if x not in relu]
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

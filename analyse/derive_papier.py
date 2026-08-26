#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""derive_papier.py -- le papier sait-il vendre, ou le marche est-il descendu ?

  python derive_papier.py
  python derive_papier.py --jours 5
  python derive_papier.py --html-seul

LA QUESTION, ET POURQUOI ELLE EST LA SEULE QUI COMPTE
-----------------------------------------------------
Le 26/08, l autopsie a montre une asymetrie massive sur douze jours :
les achats du papier perdent 4993, ses ventes gagnent 1877. L ecart
traverse les trois motifs de sortie et les trois actifs.

Deux explications, et elles n ont rien a voir :

    COMPETENCE  le papier choisit BIEN ses ventes. Il vend quand il
                faut vendre. C est une propriete du signal, elle
                survivra au changement de regime.

    DERIVE      le marche a baissé pendant ces douze jours. N IMPORTE
                QUELLE vente aurait gagne. Ce n est pas une propriete
                du signal, c est une propriete d aout 2026, et elle
                s inversera sans prevenir.

Aucun des tableaux de l autopsie ne peut les separer : ils ne
contiennent pas la derive. Le fichier, si -- chaque trade porte son
prix d entree et son prix de sortie.

LA DECOMPOSITION, ET POURQUOI UN TEMOIN NE SUFFIT PAS
    La premiere version comparait chaque trade a une VENTE
    SYSTEMATIQUE sur la meme fenetre. L idee etait juste, la mise en
    oeuvre non : sur un trade vendeur, ce temoin EST le trade
    lui-meme. L apport y valait zero par construction, et le tableau
    aurait ete vide la ou il compte.

    La bonne separation est algebrique. Avec d le mouvement du prix
    et s le sens choisi (+1 achat, -1 vente), le resultat vaut s x d,
    et sa moyenne se coupe en deux :

        moyenne(s x d)  =  moyenne(s) x moyenne(d)   <- BIAIS
                        +  covariance(s, d)          <- SELECTION

    BIAIS      ce qu un penchant directionnel constant aurait rapporte
               sans aucun timing. Etre net vendeur pendant que le
               marche descend suffit a le rendre positif.
    SELECTION  ce que le timing ajoute. Le papier vend-il PRECISEMENT
               quand le mouvement est plus negatif que d habitude ?
               C est la seule compétence, et la seule chose qui
               survivra au retournement du regime.

LE TEST DE LA SELECTION
    On compare le mouvement moyen des fenetres ou le papier a ACHETE
    a celui des fenetres ou il a VENDU.

        discrimination = moyenne(d | achat) - moyenne(d | vente)

    Un papier competent achete quand ca monte davantage et vend quand
    ca descend davantage : sa discrimination est POSITIVE. Un papier
    qui choisit au hasard laisse les deux moyennes egales, quelle que
    soit la derive d ensemble.

    Le t est celui de Welch sur ces deux echantillons -- ils n ont ni
    la meme taille ni la meme variance, et Student simple les
    supposerait egales.

    C est un test que la derive ne peut pas truquer : elle deplace
    les DEUX moyennes ensemble et disparait de leur difference.

ON NE LIT QUE LE BRAS 206
    Il ne fractionne quasiment jamais ses sorties, donc un trade =
    un enregistrement, et son prix de sortie est celui du trade
    entier. Le 207 melangerait des segments.

OU IL ECRIT
    cartes\panel_derive.txt
    cartes\derive_papier.html    visible sur /carte?f=derive_papier.html
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime, timedelta

RACINE = os.path.dirname(os.path.abspath(__file__))
TRADES = os.path.join(RACINE, "docs", "papier_tf", "trades.jsonl")
SORTIE = os.path.join(RACINE, "cartes")
BRAS = "206"
LARGE = 116


def lis(chemin, depuis=None):
    T, lus = [], 0
    if not os.path.isfile(chemin):
        return None, 0
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for l in f:
            l = l.strip()
            if not l or '"TRADE"' not in l:
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            if o.get("quoi") != "TRADE" or str(o.get("bras")) != BRAS:
                continue
            if depuis and str(o.get("ts", "")) < depuis:
                continue
            e, s = o.get("entree"), o.get("sortie")
            if e is None or s is None:
                continue
            lus += 1
            o["_move"] = float(s) - float(e)
            T.append(o)
    return T, lus


def sens_mot(s):
    try:
        s = int(s)
    except (TypeError, ValueError):
        return "?"
    return "achat" if s > 0 else ("vente" if s < 0 else "?")


def welch(x, y):
    """t de Welch. Les deux echantillons n ont ni la meme taille ni la
    meme variance ; Student simple les supposerait egales."""
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2:
        return None
    mx, my = sum(x) / nx, sum(y) / ny
    vx = sum((a - mx) ** 2 for a in x) / (nx - 1.0)
    vy = sum((a - my) ** 2 for a in y) / (ny - 1.0)
    d = vx / nx + vy / ny
    if d <= 0:
        return None
    return (mx - my) / (d ** 0.5)


def mesure(recs):
    """La coupure biais / selection, et le test de la selection."""
    if not recs:
        return None
    n = len(recs)
    d = [o["_move"] for o in recs]
    sgn = [1.0 if int(o.get("sens", 0)) > 0 else -1.0 for o in recs]
    reel = [a * b for a, b in zip(sgn, d)]
    md = sum(d) / n
    ms = sum(sgn) / n
    biais = ms * md
    da = [x for x, g in zip(d, sgn) if g > 0]
    dv = [x for x, g in zip(d, sgn) if g < 0]
    discr = ((sum(da) / len(da) - sum(dv) / len(dv))
             if (da and dv) else None)
    return {"n": n, "derive": md, "biais_dir": ms, "baisses":
            sum(1 for x in d if x < 0) / float(n),
            "part_biais": biais,
            "part_select": sum(reel) / n - biais,
            "reel": sum(reel) / n,
            "discr": discr, "t": welch(da, dv) if (da and dv) else None}


def groupe(T, cle):
    out = {}
    for o in T:
        out.setdefault(cle(o), []).append(o)
    return out


def rangs(d, ordre=None):
    return [(k, d[k]) for k in (sorted(d, key=ordre) if ordre
                                else sorted(d, key=str))]


# ----------------------------------------------------------------------
def f(v, fm="%+.1f"):
    return "--" if v is None else fm % v


def bloc(titre, lignes, lib):
    L = ["", "=" * LARGE, titre, "=" * LARGE, "-" * LARGE,
         ("%-24s %5s %8s %7s %8s %9s %9s %9s %8s"
          % (lib[:24], "n", "derive", "penchant", "discrim", "t",
             "p.biais", "p.select", "reel")),
         "-" * LARGE]
    for nom, recs in lignes:
        m = mesure(recs)
        if m is None:
            continue
        L.append("%-24s %5d %+8.1f %+8.2f %8s %9s %+9.1f %+9.1f %+8.1f"
                 % (str(nom)[:24], m["n"], m["derive"], m["biais_dir"],
                    f(m["discr"]), f(m["t"], "%+.2f"), m["part_biais"],
                    m["part_select"], m["reel"]))
    return L


def rendu(T, lus, depuis):
    L = ["=" * LARGE,
         "DERIVE -- le papier sait-il vendre, ou le marche est-il descendu ?",
         "=" * LARGE,
         "  source  : docs\\papier_tf\\trades.jsonl, bras %s seulement"
         % BRAS,
         "  trades  : %d avec un prix d entree et de sortie" % lus,
         "  fenetre : %s" % (depuis or "tout le fichier"),
         "",
         "  Avec d le mouvement du prix et s le sens choisi (+1 achat,",
         "  -1 vente), le resultat vaut s x d et sa moyenne se coupe",
         "  en deux :",
         "",
         "      moyenne(s x d) = moyenne(s) x moyenne(d)   <- BIAIS",
         "                     + covariance(s, d)          <- SELECTION",
         "",
         "  BIAIS      ce qu un penchant directionnel constant aurait",
         "             rapporte SANS AUCUN TIMING. Etre net vendeur",
         "             pendant que le marche descend suffit.",
         "  SELECTION  ce que le timing ajoute. La seule chose qui",
         "             survivra au retournement du regime.",
         "",
         "  DISCRIM    moyenne(d | achat) - moyenne(d | vente). Un",
         "             papier competent achete quand ca monte davantage",
         "             et vend quand ca descend davantage : elle est",
         "             positive. Un papier qui choisit au hasard laisse",
         "             les deux moyennes egales, QUELLE QUE SOIT la",
         "             derive -- c est un test que la periode ne peut",
         "             pas truquer, elle deplace les deux moyennes",
         "             ensemble et disparait de leur difference.",
         "  t          Welch, qui ne suppose ni memes tailles ni memes",
         "             variances entre les deux groupes.",
         "",
         "  Tout est en POINTS, jamais en euros : les lots varient, et",
         "  un ecart de lot ferait passer pour une competence ce qui",
         "  n est qu une taille de position.",
         ""]
    if not T:
        return "\n".join(L + ["  AUCUN TRADE exploitable.", ""])

    m = mesure(T)
    L += ["  VUE D ENSEMBLE",
          "     derive du marche      %+.1f pts, %.0f %% des fenetres en"
          % (m["derive"], 100 * m["baisses"]),
          "                           baisse",
          "     penchant du papier    %+.2f   (-1 = toujours vendeur)"
          % m["biais_dir"],
          "",
          "     part BIAIS            %+.1f pts/trade" % m["part_biais"],
          "     part SELECTION        %+.1f pts/trade" % m["part_select"],
          "                           ------",
          "     resultat              %+.1f pts/trade" % m["reel"],
          "",
          "     discrimination        %s pts   t de Welch = %s"
          % (f(m["discr"]), f(m["t"], "%+.2f")),
          ""]
    if m["t"] is None:
        L.append("     Un seul sens dans l echantillon : rien a comparer.")
    elif abs(m["t"]) < 2.0:
        L += ["     |t| < 2 : AUCUNE COMPETENCE DIRECTIONNELLE DEMONTREE.",
              "     Les fenetres ou le papier achete bougent comme celles",
              "     ou il vend. Tout son resultat vient du penchant, donc",
              "     de la derive -- et s inversera avec elle.",
              "",
              "     Ce n est pas un echec du papier : c est la difference",
              "     entre gagner parce qu on a raison et gagner parce",
              "     qu on etait du bon cote."]
    elif m["discr"] is not None and m["discr"] > 0:
        L += ["     |t| >= 2 et discrimination POSITIVE : le papier achete",
              "     bien les fenetres qui montent et vend bien celles qui",
              "     descendent. C est une competence, et la derive ne peut",
              "     pas la truquer -- elle deplace les deux moyennes",
              "     ensemble et disparait de leur difference."]
    else:
        L += ["     |t| >= 2 et discrimination NEGATIVE : le papier se",
              "     trompe systematiquement de sens. Un renversement pur",
              "     et simple ferait mieux."]
    L.append("")

    L += bloc("PAR MOTIF DE SORTIE",
              rangs(groupe(T, lambda o: o.get("motif") or "?")), "motif")
    L += bloc("PAR ACTIF", rangs(groupe(T, lambda o: o.get("actif") or "?")),
              "actif")
    L += bloc("PAR CRENEAU",
              rangs(groupe(T, lambda o: o.get("creneau") or "?")), "creneau")
    L += bloc("ACTIF x CRENEAU",
              rangs(groupe(T, lambda o: "%s %s" % (o.get("actif"),
                                                   o.get("creneau")))),
              "actif x creneau")
    L += bloc("PAR HORIZON",
              rangs(groupe(T, lambda o: "%s min" % o.get("mn"))), "horizon")
    L += bloc("PAR JOUR -- la derive tient-elle tous les jours ?",
              rangs(groupe(T, lambda o: str(o.get("ouvert", ""))[:10])),
              "jour")
    L += ["",
          "  LA LECTURE PAR JOUR EST LA PLUS UTILE. Une derive qui",
          "  change de signe d un jour a l autre en laissant une",
          "  selection stable, c est une competence. Une derive",
          "  constamment negative avec une selection nulle, c est la",
          "  periode.",
          "",
          "  Genere le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    return "\n".join(L)


# ----------------------------------------------------------------------
CSS = """<style>
#dv{padding:16px 20px 40px;background:#0d1117;color:#c9d1d9;
    font:13px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
#dv h1{font:600 19px system-ui;color:#58a6ff;margin:0 0 3px}
#dv .sous{color:#8b949e;margin:0 0 16px;max-width:86ch}
#dv h3{font:600 12px system-ui;letter-spacing:.07em;text-transform:uppercase;
    color:#8b949e;margin:26px 0 9px;border-bottom:1px solid #30363d;
    padding-bottom:7px}
#dv .tuiles{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 18px}
#dv .tuile{background:#161b22;border:1px solid #30363d;border-radius:7px;
    padding:9px 14px;min-width:118px}
#dv .lib{color:#8b949e;font-size:11px;text-transform:uppercase;
    letter-spacing:.06em}
#dv .val{font:600 16px ui-monospace,Consolas,monospace;color:#e6edf3;
    font-variant-numeric:tabular-nums}
#dv .avis{background:#161b22;border-left:3px solid #58a6ff;border-radius:5px;
    padding:11px 15px;margin:0 0 18px;color:#c9d1d9;max-width:100ch;
    font-size:12.5px;line-height:1.55}
#dv .alerte{border-left-color:#d29922}
#dv table{border-collapse:collapse;width:100%;margin:0 0 8px}
#dv th{padding:7px 9px;text-align:right;color:#8b949e;font-size:11px;
    font-weight:600;text-transform:uppercase;letter-spacing:.05em;
    border-bottom:1px solid #30363d;white-space:nowrap}
#dv td{padding:6px 9px;text-align:right;border-bottom:1px solid #161b22;
    font-variant-numeric:tabular-nums;white-space:nowrap}
#dv tr:hover td{background:#161b22}
#dv td.k{text-align:left;color:#e6edf3;font-weight:600}
#dv td.ap{background:rgba(230,237,243,.05);font-weight:600}
#dv .vert{color:#3fb950;font-weight:600}
#dv .rouge{color:#f85149;font-weight:600}
#dv .gris{color:#6e7681}
#dv .fort{background:#1f2d20;border-radius:4px;padding:1px 6px}
</style>"""


def ech(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def sig(v, f="%+.1f"):
    k = "vert" if v > 0 else ("rouge" if v < 0 else "gris")
    return '<span class="%s">%s</span>' % (k, f % v)


def table(lignes, lib):
    o = ['<table><thead><tr><th style="text-align:left">%s</th><th>n</th>'
         '<th>derive</th><th>penchant</th><th>discrim.</th><th>t Welch</th>'
         '<th>part biais</th><th>part selection</th><th>resultat</th>'
         '</tr></thead><tbody>' % ech(lib)]
    for nom, recs in lignes:
        m = mesure(recs)
        if m is None:
            continue
        cl = "fort" if (m["t"] is not None and abs(m["t"]) >= 2.0) else ""
        o.append('<tr><td class="k">%s</td><td>%d</td><td>%s</td>'
                 '<td class="gris">%+.2f</td><td>%s</td>'
                 '<td><span class="%s">%s</span></td>'
                 '<td class="gris">%s</td><td class="ap">%s</td>'
                 '<td>%s</td></tr>'
                 % (ech(nom), m["n"], sig(m["derive"]), m["biais_dir"],
                    "--" if m["discr"] is None else sig(m["discr"]),
                    cl, "--" if m["t"] is None else "%+.2f" % m["t"],
                    sig(m["part_biais"]), sig(m["part_select"]),
                    sig(m["reel"])))
    return "".join(o) + '</tbody></table>'


def page(T, lus, depuis, txt):
    if not T:
        return (CSS + '<div id="dv"><h1>Derive</h1><div class="avis">'
                'Aucun trade exploitable.</div></div>')
    m = mesure(T)
    if m["t"] is None:
        verdict, cls = "Un seul sens dans l echantillon.", " alerte"
    elif abs(m["t"]) < 2.0:
        verdict = ("<b>|t| = %.2f, en deca de 2 : aucune competence"
                   " directionnelle demontree.</b> Les fenetres ou le"
                   " papier achete bougent comme celles ou il vend. Tout"
                   " son resultat vient du <b>penchant</b>, donc de la"
                   " derive &mdash; et s inversera avec elle.<br><br>"
                   "Ce n est pas un echec du papier : c est la difference"
                   " entre gagner parce qu on a raison et gagner parce"
                   " qu on etait du bon cote." % abs(m["t"]))
        cls = " alerte"
    elif m["discr"] is not None and m["discr"] > 0:
        verdict = ("<b>|t| = %.2f et discrimination positive.</b> Le papier"
                   " achete les fenetres qui montent et vend celles qui"
                   " descendent. C est une competence, et la derive ne peut"
                   " pas la truquer : elle deplace les deux moyennes"
                   " ensemble et disparait de leur difference."
                   % abs(m["t"]))
        cls = ""
    else:
        verdict = ("<b>|t| = %.2f et discrimination negative.</b> Le papier"
                   " se trompe systematiquement de sens : un renversement"
                   " pur et simple ferait mieux." % abs(m["t"]))
        cls = " alerte"
    tuiles = [("trades", "%d" % m["n"]),
              ("derive marche", "%+.1f" % m["derive"]),
              ("fenetres en baisse", "%.0f %%" % (100 * m["baisses"])),
              ("penchant", "%+.2f" % m["biais_dir"]),
              ("part biais", "%+.1f" % m["part_biais"]),
              ("part selection", "%+.1f" % m["part_select"]),
              ("t de Welch",
               "--" if m["t"] is None else "%+.2f" % m["t"])]
    o = [CSS, '<div id="dv">',
         '<h1>Derive &mdash; le papier sait-il vendre, ou le marche'
         ' est-il descendu ?</h1>',
         '<div class="sous">Bras %s seulement, %d trades, tout en'
         ' <b>points</b> et jamais en euros : les lots varient, et un'
         ' ecart de lot ferait passer pour une competence ce qui n est'
         ' qu une taille de position.</div>' % (BRAS, lus),
         '<div class="tuiles">' + "".join(
             '<div class="tuile"><div class="lib">%s</div>'
             '<div class="val">%s</div></div>' % (ech(a), ech(b))
             for a, b in tuiles) + '</div>',
         '<div class="avis%s">%s</div>' % (cls, verdict),
         '<div class="avis">Avec <b>d</b> le mouvement du prix et'
         ' <b>s</b> le sens choisi (+1 achat, &minus;1 vente), le'
         ' resultat vaut s&times;d et sa moyenne se coupe en deux :'
         '<br><br>'
         '&nbsp;&nbsp;moyenne(s&times;d) = <b>moyenne(s) &times;'
         ' moyenne(d)</b> &nbsp;<i>le biais</i><br>'
         '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
         '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
         '&nbsp;&nbsp;+ <b>covariance(s, d)</b> &nbsp;<i>la selection'
         '</i><br><br>'
         'Le <b>biais</b> est ce qu un penchant directionnel constant'
         ' aurait rapporte sans aucun timing : etre net vendeur pendant'
         ' que le marche descend suffit a le rendre positif. La'
         ' <b>selection</b> est ce que le timing ajoute.<br><br>'
         'La <b>discrimination</b> compare le mouvement moyen des'
         ' fenetres achetees a celui des fenetres vendues. Un papier'
         ' competent achete quand ca monte davantage : elle est'
         ' positive. Un papier qui choisit au hasard laisse les deux'
         ' moyennes egales, <b>quelle que soit la derive</b> &mdash;'
         ' c est un test que la periode ne peut pas truquer.<br><br>'
         'Le <b>t de Welch</b> ne suppose ni memes tailles ni memes'
         ' variances entre les deux groupes.</div>']
    for titre, lignes, lib in (
            ("Par actif", rangs(groupe(T, lambda x: x.get("actif") or "?")),
             "actif"),
            ("Par creneau",
             rangs(groupe(T, lambda x: x.get("creneau") or "?")), "creneau"),
            ("Par motif de sortie",
             rangs(groupe(T, lambda x: x.get("motif") or "?")), "motif"),
            ("Actif &times; creneau",
             rangs(groupe(T, lambda x: "%s %s" % (x.get("actif"),
                                                  x.get("creneau")))),
             "actif x creneau"),
            ("Par horizon",
             rangs(groupe(T, lambda x: "%s min" % x.get("mn"))), "horizon"),
            ("Par jour &mdash; la derive tient-elle tous les jours ?",
             rangs(groupe(T, lambda x: str(x.get("ouvert", ""))[:10])),
             "jour")):
        o.append('<h3>%s</h3>' % titre)
        o.append(table(lignes, lib))
    o.append('<div class="avis">La lecture <b>par jour</b> est la plus'
             ' utile. Une derive qui change de signe d un jour a l autre'
             ' en laissant une selection stable, c est une competence.'
             ' Une derive constamment negative avec une selection nulle,'
             ' c est la periode.</div>')
    o.append('<details><summary style="cursor:pointer;color:#8b949e;'
             'font-weight:600;padding:14px 0 0">Le rapport en texte'
             '</summary><pre style="font:12px/1.45 ui-monospace,Consolas,'
             'monospace;color:#c9d1d9;overflow-x:auto">' + ech(txt)
             + '</pre></details>')
    return "".join(o) + '</div>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", default=TRADES)
    ap.add_argument("--sortie", default=SORTIE)
    ap.add_argument("--jours", type=int, default=0)
    ap.add_argument("--html-seul", action="store_true")
    a = ap.parse_args()

    depuis = None
    if a.jours > 0:
        depuis = (datetime.now() - timedelta(days=a.jours)).strftime(
            "%Y-%m-%dT%H:%M:%S")

    T, lus = lis(a.trades, depuis)
    if T is None:
        print("introuvable : %s" % a.trades)
        return 2
    txt = rendu(T, lus, depuis)
    if not a.html_seul:
        print(txt)

    if not os.path.isdir(a.sortie):
        os.makedirs(a.sortie)
    t = os.path.join(a.sortie, "panel_derive.txt")
    h = os.path.join(a.sortie, "derive_papier.html")
    io.open(t, "w", encoding="utf-8", newline="").write(txt + "\n")
    io.open(h, "w", encoding="utf-8", newline="").write(page(T, lus, depuis,
                                                             txt))
    print("")
    print("  ecrit : %s" % t)
    print("  ecrit : %s" % h)
    print("  visible sur  /carte?f=derive_papier.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())

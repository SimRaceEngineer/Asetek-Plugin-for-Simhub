#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""reverse_autopsie.py -- pourquoi REVERSE perd sur 352 trades.

  python reverse_autopsie.py
  python reverse_autopsie.py --motif SESSION_FLAT
  python reverse_autopsie.py --jours 5 --html-seul

LA QUESTION
-----------
Le 25/08, l A/B des sorties a montre que 72 % des trades du papier
sortent sur REVERSE, et que REVERSE perd SUR LES DEUX BRAS : -3221 cote
206, -1703 cote 207. Un A/B de sortie ne peut pas reparer ca -- le
defaut est en amont.

Reste a savoir lequel. Deux histoires expliquent une perte, elles
appellent des corrections opposees, et seul le chemin du prix les
separe :

    MORT-NE    le trade part contre soi et n y revient jamais.
               L ENTREE est mauvaise. Aucun reglage de sortie n y
               changera quoi que ce soit.

    RETOURNE   le trade monte, puis rend tout et finit dans le rouge.
               L entree etait bonne, c est la SORTIE qui laisse filer.
               La un trail, un seuil, un partiel changent tout.

LE PARTAGE, ET SON SEUIL ASSUME
    Sur les trades PERDANTS seulement, et en points :

        mort-ne    MFE <  0.5 x |points perdus|
        retourne   MFE >= 1.0 x |points perdus|
        entre-deux le reste

    Le seuil de 0.5 est un choix, pas une verite. Il est ecrit ici
    plutot que cache dans le code : un trade qui n a jamais ete en
    profit de plus de la moitie de ce qu il a fini par perdre n a
    jamais vraiment ete gagnant.

    RENDU = MFE - points. Ce que le trade avait offert et qu il n a
    pas garde. C est la mesure directe de ce qu une meilleure sortie
    pourrait recuperer -- et de ce qu une meilleure entree ne
    recuperera pas.

POURQUOI LES DEUX BRAS SONT AFFICHES COTE A COTE
    C est le test qui tranche. Meme entree, sorties differentes :

        si les MORT-NES sont en meme proportion des deux cotes,
        le mal est dans l ENTREE -- aucun des deux ne s en sort.

        s ils different, c est que la sortie choisit ce qu elle
        laisse mourir, et la il y a quelque chose a regler.

OU IL ECRIT
    cartes\panel_reverse.txt
    cartes\reverse_autopsie.html   visible sur /carte?f=reverse_autopsie.html
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
BRAS = ("206", "207")
SEUIL_MORT = 0.5          # MFE sous cette part de la perte = mort-ne
LARGE = 128


def lis(chemin, motif, depuis=None):
    T, lus, casse = [], 0, 0
    if not os.path.isfile(chemin):
        return None, 0, 0
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for l in f:
            l = l.strip()
            if not l or '"TRADE"' not in l:
                continue
            lus += 1
            try:
                o = json.loads(l)
            except ValueError:
                casse += 1
                continue
            if o.get("quoi") != "TRADE" or o.get("motif") != motif:
                continue
            if depuis and str(o.get("ts", "")) < depuis:
                continue
            if str(o.get("bras", "")) not in BRAS:
                continue
            T.append(o)
    return T, lus, casse


def sens_mot(s):
    try:
        s = int(s)
    except (TypeError, ValueError):
        return "?"
    return "achat" if s > 0 else ("vente" if s < 0 else "?")


def mediane(v):
    if not v:
        return 0.0
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def mesure(recs):
    """Les compteurs d un groupe. Le partage mort-ne / retourne ne
    porte QUE sur les trades perdants : un gagnant n a rien a
    expliquer."""
    if not recs:
        return None
    n = len(recs)
    pts = [float(o.get("points", 0.0)) for o in recs]
    eur = [float(o.get("eur", 0.0)) for o in recs]
    mfe = [float(o.get("mfe", 0.0)) for o in recs]
    mae = [float(o.get("mae", 0.0)) for o in recs]
    mn = [float(o.get("minutes", 0.0)) for o in recs]
    gagnants = sum(1 for x in eur if x > 0)
    perdants = [o for o in recs if float(o.get("eur", 0.0)) <= 0]
    morts = ret = entre = 0
    for o in perdants:
        p = abs(float(o.get("points", 0.0)))
        f = float(o.get("mfe", 0.0))
        if p <= 0:
            continue
        if f < SEUIL_MORT * p:
            morts += 1
        elif f >= p:
            ret += 1
        else:
            entre += 1
    np_ = max(1, len(perdants))
    return {"n": n, "gagnants": gagnants, "taux": gagnants / float(n),
            "pnl": sum(eur), "esp": sum(eur) / n,
            "mfe": sum(mfe) / n, "mae": sum(mae) / n,
            "rendu": sum(m - p for m, p in zip(mfe, pts)) / n,
            "perdants": len(perdants),
            "morts": morts, "ret": ret, "entre": entre,
            "p_morts": morts / float(np_), "p_ret": ret / float(np_),
            "duree": mediane(mn)}


def groupe(T, cle):
    out = {}
    for o in T:
        out.setdefault(cle(o), {}).setdefault(str(o.get("bras")), []).append(o)
    return out


def rangs(d):
    return [(k, d[k]) for k in sorted(d, key=str)]


# ----------------------------------------------------------------------
# TEXTE
# ----------------------------------------------------------------------
TET = ("%-22s %-5s %5s %5s %9s %8s %7s %7s %7s %7s %7s %6s"
       % ("", "bras", "n", "taux", "PnL", "esp", "MFE", "MAE", "rendu",
          "mort-ne", "retour", "duree"))


def bloc(titre, lignes, lib):
    L = ["", "=" * LARGE, titre, "=" * LARGE, "-" * LARGE,
         ("%-22s %-5s %5s %5s %9s %8s %7s %7s %7s %7s %7s %6s"
          % (lib[:22], "bras", "n", "taux", "PnL", "esp", "MFE", "MAE",
             "rendu", "mort-ne", "retour", "duree")),
         "-" * LARGE]
    for nom, par in lignes:
        premier = True
        for b in BRAS:
            m = mesure(par.get(b))
            if m is None:
                continue
            L.append("%-22s %-5s %5d %4.0f%% %+9.2f %+8.2f %7.1f %7.1f"
                     " %7.1f %6.0f%% %6.0f%% %6.0f"
                     % (str(nom)[:22] if premier else "", b, m["n"],
                        100 * m["taux"], m["pnl"], m["esp"], m["mfe"],
                        m["mae"], m["rendu"], 100 * m["p_morts"],
                        100 * m["p_ret"], m["duree"]))
            premier = False
        L.append("")
    return L


def rendu_txt(T, motif, lus, casse, depuis):
    L = ["=" * LARGE,
         "AUTOPSIE DE %s -- pourquoi ces trades perdent" % motif,
         "=" * LARGE,
         "  source  : docs\\papier_tf\\trades.jsonl",
         "  lus     : %d TRADE, %d retenus sur motif %s%s"
         % (lus, len(T), motif, ", %d illisibles" % casse if casse else ""),
         "  fenetre : %s" % (depuis or "tout le fichier"),
         ""]
    if not T:
        return "\n".join(L + ["  AUCUN TRADE sur ce motif. Rien a decouper.",
                              ""])
    L += ["  MORT-NE   MFE < %.0f %% de la perte. Le trade n a jamais"
          % (100 * SEUIL_MORT),
          "            vraiment ete en profit : l ENTREE est en cause,",
          "            et aucun reglage de sortie n y changera rien.",
          "  RETOURNE  MFE >= la perte. Le trade avait offert au moins",
          "            ce qu il a fini par couter : la SORTIE laisse",
          "            filer, et la il y a quelque chose a regler.",
          "  RENDU     MFE - points, en points. Ce qui etait sur la",
          "            table et n a pas ete garde.",
          "  Les deux bras cote a cote : des proportions EGALES de",
          "  mort-nes accusent l entree, des proportions DIFFERENTES",
          "  accusent la sortie.",
          ""]
    tout = {"tout": {}}
    for o in T:
        tout["tout"].setdefault(str(o.get("bras")), []).append(o)
    L += bloc("VUE D ENSEMBLE", rangs(tout), "ensemble")
    L += bloc("PAR ACTIF", rangs(groupe(T, lambda o: o.get("actif") or "?")),
              "actif")
    L += bloc("PAR SENS", rangs(groupe(T, lambda o: sens_mot(o.get("sens")))),
              "sens")
    L += bloc("PAR CRENEAU",
              rangs(groupe(T, lambda o: o.get("creneau") or "?")), "creneau")
    L += bloc("ACTIF x SENS",
              rangs(groupe(T, lambda o: "%s %s" % (o.get("actif"),
                                                   sens_mot(o.get("sens"))))),
              "actif x sens")
    L += bloc("ACTIF x CRENEAU",
              rangs(groupe(T, lambda o: "%s %s" % (o.get("actif"),
                                                   o.get("creneau")))),
              "actif x creneau")
    L += bloc("SENS x CRENEAU",
              rangs(groupe(T, lambda o: "%s %s" % (sens_mot(o.get("sens")),
                                                   o.get("creneau")))),
              "sens x creneau")
    L += bloc("PAR HORIZON",
              rangs(groupe(T, lambda o: "%s min" % o.get("mn"))), "horizon")
    L += ["  Genere le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    return "\n".join(L)


# ----------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------
CSS = """<style>
#rv{padding:16px 20px 40px;background:#0d1117;color:#c9d1d9;
    font:13px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
#rv h1{font:600 19px system-ui;color:#58a6ff;margin:0 0 3px}
#rv .sous{color:#8b949e;margin:0 0 16px;max-width:84ch}
#rv h3{font:600 12px system-ui;letter-spacing:.07em;text-transform:uppercase;
    color:#8b949e;margin:26px 0 9px;border-bottom:1px solid #30363d;
    padding-bottom:7px}
#rv .avis{background:#161b22;border-left:3px solid #58a6ff;border-radius:5px;
    padding:11px 15px;margin:0 0 18px;color:#c9d1d9;max-width:104ch;
    font-size:12.5px;line-height:1.55}
#rv table{border-collapse:collapse;width:100%;margin:0 0 8px}
#rv th{padding:7px 9px;text-align:right;color:#8b949e;font-size:11px;
    font-weight:600;text-transform:uppercase;letter-spacing:.05em;
    border-bottom:1px solid #30363d;white-space:nowrap}
#rv td{padding:6px 9px;text-align:right;border-bottom:1px solid #161b22;
    font-variant-numeric:tabular-nums;white-space:nowrap}
#rv tr.b206 td{background:rgba(139,148,158,.05)}
#rv tr.b207 td{background:rgba(88,166,255,.06)}
#rv tr.fin td{border-bottom:1px solid #30363d}
#rv td.k{text-align:left;color:#e6edf3;font-weight:600}
#rv td.br{text-align:left;color:#8b949e;font-size:11.5px}
#rv .vert{color:#3fb950;font-weight:600}
#rv .rouge{color:#f85149;font-weight:600}
#rv .gris{color:#6e7681}
#rv .chaud{background:#3d1d1d;border-radius:4px;padding:1px 6px;
    color:#ff9492;font-weight:600}
#rv .tiede{color:#d29922;font-weight:600}
</style>"""


def ech(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def sig(v, f="%+.2f"):
    k = "vert" if v > 0 else ("rouge" if v < 0 else "gris")
    return '<span class="%s">%s</span>' % (k, f % v)


def part(p):
    """Au-dela de 60 % de mort-nes, la case est marquee : ce n est plus
    un accident de quelques trades, c est le regime du groupe."""
    if p >= 0.60:
        return '<span class="chaud">%.0f&#37;</span>' % (100 * p)
    if p >= 0.40:
        return '<span class="tiede">%.0f&#37;</span>' % (100 * p)
    return "%.0f&#37;" % (100 * p)


def table(lignes, lib):
    o = ['<table><thead><tr><th style="text-align:left">%s</th>'
         '<th style="text-align:left">bras</th><th>n</th><th>taux</th>'
         '<th>PnL</th><th>esp</th><th>MFE</th><th>MAE</th><th>rendu</th>'
         '<th>mort-nes</th><th>retournes</th><th>duree med.</th>'
         '</tr></thead><tbody>' % ech(lib)]
    for nom, par in lignes:
        premier = True
        faits = [b for b in BRAS if par.get(b)]
        for b in faits:
            m = mesure(par[b])
            o.append('<tr class="b%s%s"><td class="k">%s</td>'
                     '<td class="br">%s</td><td>%d</td><td>%.0f&#37;</td>'
                     '<td>%s</td><td>%s</td><td>%.1f</td><td>%.1f</td>'
                     '<td>%.1f</td><td>%s</td><td>%s</td>'
                     '<td class="gris">%.0f</td></tr>'
                     % (b, " fin" if b == faits[-1] else "",
                        ech(nom) if premier else "", b, m["n"],
                        100 * m["taux"], sig(m["pnl"]), sig(m["esp"]),
                        m["mfe"], m["mae"], m["rendu"], part(m["p_morts"]),
                        "%.0f&#37;" % (100 * m["p_ret"]), m["duree"]))
            premier = False
    return "".join(o) + '</tbody></table>'


def page(T, motif, lus, casse, depuis, txt):
    if not T:
        return (CSS + '<div id="rv"><h1>Autopsie de %s</h1>'
                '<div class="avis">Aucun trade sur ce motif.</div></div>'
                % ech(motif))
    o = [CSS, '<div id="rv">',
         '<h1>Autopsie de %s &mdash; pourquoi ces trades perdent</h1>'
         % ech(motif),
         '<div class="sous">%d trades retenus sur %d lus. Les deux bras'
         ' sont affiches cote a cote : c est ce qui permet de designer'
         ' le coupable.</div>' % (len(T), lus),
         '<div class="avis"><b>Deux histoires expliquent une perte, et'
         ' elles appellent des corrections opposees.</b><br><br>'
         '<b>MORT-NE</b> &mdash; MFE &lt; %.0f &#37; de la perte. Le trade'
         ' part contre soi et n y revient jamais. L <b>entree</b> est en'
         ' cause : aucun reglage de sortie n y changera quoi que ce'
         ' soit.<br>'
         '<b>RETOURNE</b> &mdash; MFE &ge; la perte. Le trade avait offert'
         ' au moins ce qu il a fini par couter. La <b>sortie</b> laisse'
         ' filer, et un trail ou un partiel changent tout.<br>'
         '<b>RENDU</b> = MFE &minus; points. Ce qui etait sur la table et'
         ' n a pas ete garde.<br><br>'
         'Le seuil de %.0f &#37; est un choix, pas une verite : il est'
         ' ecrit ici plutot que cache dans le code.<br><br>'
         '<b>Le test qui tranche :</b> des proportions de mort-nes'
         ' <b>egales</b> entre les deux bras accusent l entree &mdash;'
         ' aucune des deux sorties ne s en sort. Des proportions'
         ' <b>differentes</b> accusent la sortie.</div>'
         % (100 * SEUIL_MORT, 100 * SEUIL_MORT)]
    tout = {"tout": {}}
    for x in T:
        tout["tout"].setdefault(str(x.get("bras")), []).append(x)
    for titre, lignes, lib in (
            ("Vue d ensemble", rangs(tout), "ensemble"),
            ("Par actif", rangs(groupe(T, lambda x: x.get("actif") or "?")),
             "actif"),
            ("Par sens", rangs(groupe(T, lambda x: sens_mot(x.get("sens")))),
             "sens"),
            ("Par creneau",
             rangs(groupe(T, lambda x: x.get("creneau") or "?")), "creneau"),
            ("Actif &times; sens",
             rangs(groupe(T, lambda x: "%s %s" % (x.get("actif"),
                                                  sens_mot(x.get("sens"))))),
             "actif x sens"),
            ("Actif &times; creneau",
             rangs(groupe(T, lambda x: "%s %s" % (x.get("actif"),
                                                  x.get("creneau")))),
             "actif x creneau"),
            ("Sens &times; creneau",
             rangs(groupe(T, lambda x: "%s %s" % (sens_mot(x.get("sens")),
                                                  x.get("creneau")))),
             "sens x creneau"),
            ("Par horizon",
             rangs(groupe(T, lambda x: "%s min" % x.get("mn"))), "horizon")):
        o.append('<h3>%s</h3>' % titre)
        o.append(table(lignes, lib))
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
    ap.add_argument("--motif", default="REVERSE")
    ap.add_argument("--jours", type=int, default=0)
    ap.add_argument("--html-seul", action="store_true")
    a = ap.parse_args()

    depuis = None
    if a.jours > 0:
        depuis = (datetime.now() - timedelta(days=a.jours)).strftime(
            "%Y-%m-%dT%H:%M:%S")

    T, lus, casse = lis(a.trades, a.motif, depuis)
    if T is None:
        print("introuvable : %s" % a.trades)
        return 2
    txt = rendu_txt(T, a.motif, lus, casse, depuis)
    if not a.html_seul:
        print(txt)

    if not os.path.isdir(a.sortie):
        os.makedirs(a.sortie)
    t = os.path.join(a.sortie, "panel_reverse.txt")
    h = os.path.join(a.sortie, "reverse_autopsie.html")
    io.open(t, "w", encoding="utf-8", newline="").write(txt + "\n")
    io.open(h, "w", encoding="utf-8", newline="").write(
        page(T, a.motif, lus, casse, depuis, txt))
    print("")
    print("  ecrit : %s" % t)
    print("  ecrit : %s" % h)
    print("  visible sur  /carte?f=reverse_autopsie.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())

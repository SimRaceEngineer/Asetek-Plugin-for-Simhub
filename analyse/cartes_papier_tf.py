#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""cartes_papier_tf.py -- l A/B de sortie du papier, 206 contre 207.

  python cartes_papier_tf.py
  python cartes_papier_tf.py --jours 5
  python cartes_papier_tf.py --html-seul

CE QUE C EST, ET CE QUE CE N EST PAS
------------------------------------
docs\papier_tf\trades.jsonl porte deux bras et deux seulement : 206 et
207. Pas de 220xxx, pas de 230xxx, pas de 240xxx. Ce fichier n est donc
PAS le papier des strategies du panneau, et les poser cote a cote
comparerait deux choses differentes en donnant l illusion du contraire.

Ce qu il est, papier_tf.py le dit lui-meme : "MEMES ENTREES que le 206
-- c est un A/B de la SORTIE". Soit exactement la question que pose le
miroir 1 contre le miroir 2, mais sur douze jours et plus de mille
trades au lieu d une seance.

L APPARIEMENT, ET POURQUOI IL N EST PAS OPTIONNEL
-------------------------------------------------
Au 25/08 le fichier portait 740 trades du bras 207 et 504 du 206.
"Memes entrees" ne veut donc pas dire "memes effectifs" : une entree
peut sortir d un cote et pas encore de l autre, ou avoir ete coupee
par une fin de seance.

Comparer les totaux de deux populations inegales attribuerait a la
SORTIE un ecart qui vient du NOMBRE. On apparie donc sur
(actif, horizon, instant d ouverture) et on ne compare que les paires.
Les orphelins ne sont pas jetes en silence : ils sont comptes et
affiches. Une exclusion tue est une exclusion qui ment.

TROIS LECTURES, DE LA PLUS SURE A LA PLUS FINE
    par actif      US30, US500, US100 -- la maille la plus fournie
    actif x horizon 10, 20, 30, 60, 120, 240 minutes
    par motif      SESSION_FLAT, REVERSE, ... -- QUELLE sortie fait
                   la difference, ce que les deux premieres ne disent
                   pas

OU IL ECRIT
    cartes\panel_papier_tf.txt
    cartes\papier_tf_ab.html      visible sur /carte?f=papier_tf_ab.html

Le dossier cartes\ est relu a chaque requete par la route /cartes :
deposer le fichier suffit a le rendre visible, sans toucher au panneau.
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
LARGE = 104


# ----------------------------------------------------------------------
# LECTURE
# ----------------------------------------------------------------------
def lis(chemin, depuis=None):
    """(trades, lus, ignores). Une ligne illisible est comptee, pas
    fatale : le fichier est ecrit en continu et la derniere ligne peut
    etre a moitie posee."""
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
            if o.get("quoi") != "TRADE":
                continue
            if depuis and str(o.get("ts", "")) < depuis:
                continue
            T.append(o)
    return T, lus, casse


def apparie(T):
    """(paires, orphelins_par_bras). La cle est (actif, horizon,
    instant d ouverture) : c est ce que "memes entrees" veut dire."""
    par = {}
    for o in T:
        b = str(o.get("bras", ""))
        if b not in BRAS:
            continue
        cle = (o.get("actif"), o.get("mn"), o.get("ouvert"))
        par.setdefault(cle, {})[b] = o
    paires = [(k, v[BRAS[0]], v[BRAS[1]])
              for k, v in par.items() if len(v) == 2]
    orph = {b: sum(1 for v in par.values() if len(v) == 1 and b in v)
            for b in BRAS}
    return paires, orph


# ----------------------------------------------------------------------
# MESURE
# ----------------------------------------------------------------------
def cumule(paires, cle=None):
    """cle(paire) -> compteurs. cle=None cumule tout ensemble."""
    out = {}
    for k, a, b in paires:
        nom = "toutes" if cle is None else cle(k, a, b)
        c = out.setdefault(nom, {"n": 0, "a": 0.0, "b": 0.0,
                                 "ga": 0, "gb": 0})
        c["n"] += 1
        ea, eb = float(a.get("eur", 0.0)), float(b.get("eur", 0.0))
        c["a"] += ea
        c["b"] += eb
        if ea > 0:
            c["ga"] += 1
        if eb > 0:
            c["gb"] += 1
    return out


def rangs(d, ordre=None):
    cles = list(d)
    if ordre:
        cles.sort(key=ordre)
    else:
        cles.sort()
    return [(k, d[k]) for k in cles]


# ----------------------------------------------------------------------
# RENDU TEXTE -- la source de verite
# ----------------------------------------------------------------------
def bloc_texte(titre, lignes, lib):
    L = ["-" * LARGE,
         "%-22s %6s | %9s %6s | %9s %6s | %9s %8s"
         % (lib, "n", "PnL 206", "taux", "PnL 207", "taux",
            "207-206", "par tr"),
         "-" * LARGE]
    for nom, c in lignes:
        d = c["b"] - c["a"]
        L.append("%-22s %6d | %+9.2f %5.0f%% | %+9.2f %5.0f%% | %+9.2f %+8.2f"
                 % (str(nom)[:22], c["n"], c["a"], 100.0 * c["ga"] / c["n"],
                    c["b"], 100.0 * c["gb"] / c["n"], d, d / c["n"]))
    return [""] + ["=" * LARGE, titre, "=" * LARGE] + L


def rendu(paires, orph, lus, casse, depuis):
    L = ["=" * LARGE,
         "PAPIER TF -- A/B DE SORTIE, LE BRAS 206 CONTRE LE 207",
         "=" * LARGE,
         "  source   : docs\\papier_tf\\trades.jsonl",
         "  lus      : %d enregistrements TRADE%s"
         % (lus, ", %d lignes illisibles" % casse if casse else ""),
         "  fenetre  : %s" % (depuis or "tout le fichier"),
         "",
         "  MEMES ENTREES, SORTIES DIFFERENTES. C est la meme question",
         "  que le miroir 1 contre le miroir 2, mais sur douze jours et",
         "  plus de mille trades au lieu d une seance.",
         ""]
    if not paires:
        L += ["  AUCUNE PAIRE. Les deux bras n ont aucune entree commune",
              "  sur la fenetre demandee -- il n y a rien a comparer.", ""]
        return "\n".join(L)

    tot = cumule(paires)["toutes"]
    d = tot["b"] - tot["a"]
    L += ["  paires   : %d entrees sorties DES DEUX cotes" % tot["n"],
          "  orphelins: 206 %d, 207 %d -- exclus de la comparaison, et"
          % (orph.get("206", 0), orph.get("207", 0)),
          "             comptes ici plutot que jetes en silence.",
          "",
          "  L APPARIEMENT N EST PAS UN DETAIL. Les deux bras n ont pas",
          "  le meme effectif brut : une entree peut sortir d un cote et",
          "  pas encore de l autre. Comparer les totaux attribuerait a la",
          "  SORTIE un ecart qui vient du NOMBRE.",
          "",
          "  VERDICT SUR LES PAIRES",
          "     206  %+.2f    207  %+.2f    ecart  %+.2f  (%+.2f par trade)"
          % (tot["a"], tot["b"], d, d / tot["n"]),
          "     %s" % ("le 207 fait mieux" if d > 0 else
                       ("le 206 fait mieux" if d < 0 else "egalite")),
          ""]

    L += bloc_texte("PAR ACTIF", rangs(cumule(paires, lambda k, a, b: k[0])),
                    "actif")
    L += bloc_texte("PAR HORIZON",
                    rangs(cumule(paires, lambda k, a, b: k[1]),
                          ordre=lambda x: (x is None, x)),
                    "horizon (min)")
    L += bloc_texte("ACTIF x HORIZON",
                    rangs(cumule(paires,
                                 lambda k, a, b: "%s  %s min" % (k[0], k[1]))),
                    "actif x horizon")
    L += bloc_texte("PAR MOTIF DE SORTIE DU 207",
                    rangs(cumule(paires,
                                 lambda k, a, b: b.get("motif") or "?")),
                    "motif")
    L += ["",
          "  LE MOTIF EST CELUI DU 207, pas du 206. Il repond a : quand",
          "  le 207 sort POUR CETTE RAISON, gagne-t-il ou perd-il contre",
          "  le 206 sur la meme entree ? C est la seule des quatre",
          "  lectures qui designe un MECANISME et non un perimetre.",
          "",
          "  Genere le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    return "\n".join(L)


# ----------------------------------------------------------------------
# RENDU HTML
# ----------------------------------------------------------------------
CSS = """<style>
#pt{padding:16px 20px 40px;background:#0d1117;color:#c9d1d9;
    font:13px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
#pt h1{font:600 19px system-ui;color:#58a6ff;margin:0 0 3px}
#pt .sous{color:#8b949e;margin:0 0 16px;max-width:78ch}
#pt h3{font:600 12px system-ui;letter-spacing:.07em;text-transform:uppercase;
    color:#8b949e;margin:26px 0 9px;border-bottom:1px solid #30363d;
    padding-bottom:7px}
#pt .tuiles{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 18px}
#pt .tuile{background:#161b22;border:1px solid #30363d;border-radius:7px;
    padding:9px 14px;min-width:112px}
#pt .lib{color:#8b949e;font-size:11px;text-transform:uppercase;
    letter-spacing:.06em}
#pt .val{font:600 16px ui-monospace,Consolas,monospace;color:#e6edf3;
    font-variant-numeric:tabular-nums}
#pt .avis{background:#161b22;border-left:3px solid #58a6ff;border-radius:5px;
    padding:11px 15px;margin:0 0 20px;color:#c9d1d9;max-width:96ch;
    font-size:12.5px;line-height:1.55}
#pt table{border-collapse:collapse;width:100%;margin:0 0 6px}
#pt th{padding:7px 10px;text-align:right;color:#8b949e;font-size:11px;
    font-weight:600;text-transform:uppercase;letter-spacing:.05em;
    border-bottom:1px solid #30363d;white-space:nowrap}
#pt td{padding:7px 10px;text-align:right;border-bottom:1px solid #161b22;
    font-variant-numeric:tabular-nums;white-space:nowrap}
#pt tr:hover td{background:#161b22}
#pt th.a{background:#12171f;color:#8b949e;text-align:center}
#pt th.b{background:#0f2438;color:#58a6ff;text-align:center}
#pt th.e{background:#1b1420;color:#e6edf3;text-align:center}
#pt td.k{text-align:left;color:#e6edf3}
#pt td.ec{background:rgba(230,237,243,.04);font-weight:600}
#pt tr.tot td{border-top:1px solid #30363d;font-weight:700}
#pt .vert{color:#3fb950;font-weight:600}
#pt .rouge{color:#f85149;font-weight:600}
#pt .gris{color:#484f58}
</style>"""


def ech(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def sig(v, f="%+.2f"):
    k = "vert" if v > 0 else ("rouge" if v < 0 else "gris")
    return '<span class="%s">%s</span>' % (k, f % v)


def table_html(lignes, lib):
    o = ['<table><thead><tr><th></th><th></th>'
         '<th colspan="2" class="a">BRAS 206</th>'
         '<th colspan="2" class="b">BRAS 207</th>'
         '<th colspan="2" class="e">207 &minus; 206</th></tr><tr>'
         '<th style="text-align:left">%s</th><th>paires</th>'
         '<th>PnL</th><th>taux</th><th>PnL</th><th>taux</th>'
         '<th>total</th><th>par trade</th></tr></thead><tbody>' % ech(lib)]
    for nom, c in lignes:
        d = c["b"] - c["a"]
        o.append('<tr><td class="k">%s</td><td>%d</td>'
                 '<td>%s</td><td>%.0f&#37;</td>'
                 '<td>%s</td><td>%.0f&#37;</td>'
                 '<td class="ec">%s</td><td class="ec">%s</td></tr>'
                 % (ech(nom), c["n"], sig(c["a"]),
                    100.0 * c["ga"] / c["n"], sig(c["b"]),
                    100.0 * c["gb"] / c["n"], sig(d), sig(d / c["n"])))
    return "".join(o) + '</tbody></table>'


def page_html(paires, orph, lus, casse, depuis, txt):
    if not paires:
        return (CSS + '<div id="pt"><h1>Papier TF &mdash; A/B de sortie</h1>'
                '<div class="avis">Aucune paire sur la fenetre demandee :'
                ' les deux bras n ont aucune entree commune. Il n y a rien'
                ' a comparer.</div></div>')
    tot = cumule(paires)["toutes"]
    d = tot["b"] - tot["a"]
    tuiles = [("periode", depuis or "tout"),
              ("paires", "%d" % tot["n"]),
              ("orphelins 206", "%d" % orph.get("206", 0)),
              ("orphelins 207", "%d" % orph.get("207", 0)),
              ("PnL 206", "%+.2f" % tot["a"]),
              ("PnL 207", "%+.2f" % tot["b"]),
              ("ecart", "%+.2f" % d)]
    o = [CSS, '<div id="pt">',
         '<h1>Papier TF &mdash; A/B de sortie, le bras 206 contre le 207'
         '</h1>',
         '<div class="sous">Memes entrees, sorties differentes. C est la'
         ' meme question que le miroir 1 contre le miroir 2, mais sur'
         ' douze jours et plus de mille trades au lieu d une seance.</div>',
         '<div class="tuiles">' + "".join(
             '<div class="tuile"><div class="lib">%s</div>'
             '<div class="val">%s</div></div>' % (ech(a), ech(b))
             for a, b in tuiles) + '</div>',
         '<div class="avis"><b>L appariement n est pas un detail.</b> Les'
         ' deux bras n ont pas le meme effectif brut &mdash; une entree'
         ' peut sortir d un cote et pas encore de l autre. Comparer les'
         ' totaux attribuerait a la <b>sortie</b> un ecart qui vient du'
         ' <b>nombre</b>. Seules les %d entrees sorties DES DEUX cotes'
         ' sont comparees ici, appariees sur (actif, horizon, instant'
         ' d ouverture). Les %d orphelins sont exclus &mdash; et comptes'
         ' ci-dessus plutot que jetes en silence.</div>'
         % (tot["n"], orph.get("206", 0) + orph.get("207", 0))]
    o.append('<h3>Par actif</h3>')
    o.append(table_html(rangs(cumule(paires, lambda k, a, b: k[0])), "actif"))
    o.append('<h3>Par horizon</h3>')
    o.append(table_html(rangs(cumule(paires, lambda k, a, b: k[1]),
                              ordre=lambda x: (x is None, x)),
                        "horizon (min)"))
    o.append('<h3>Actif &times; horizon</h3>')
    o.append(table_html(rangs(cumule(
        paires, lambda k, a, b: "%s  %s min" % (k[0], k[1]))),
        "actif x horizon"))
    o.append('<h3>Par motif de sortie du 207</h3>')
    o.append('<div class="avis">Le motif est celui du <b>207</b>. La'
             ' question posee est : quand le 207 sort POUR CETTE RAISON,'
             ' gagne-t-il ou perd-il contre le 206 sur la meme entree ?'
             ' C est la seule des quatre lectures qui designe un'
             ' <b>mecanisme</b> et non un perimetre.</div>')
    o.append(table_html(rangs(cumule(paires,
                                     lambda k, a, b: b.get("motif") or "?")),
                        "motif"))
    o.append('<details><summary style="cursor:pointer;color:#8b949e;'
             'font-weight:600;padding:14px 0 0">Le rapport en texte'
             '</summary><pre style="font:12px/1.45 ui-monospace,Consolas,'
             'monospace;color:#c9d1d9;overflow-x:auto">' + ech(txt)
             + '</pre></details>')
    return "".join(o) + '</div>'


# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", default=TRADES)
    ap.add_argument("--sortie", default=SORTIE)
    ap.add_argument("--jours", type=int, default=0,
                    help="ne garder que les N derniers jours")
    ap.add_argument("--html-seul", action="store_true")
    a = ap.parse_args()

    depuis = None
    if a.jours > 0:
        depuis = (datetime.now() - timedelta(days=a.jours)).strftime(
            "%Y-%m-%dT%H:%M:%S")

    T, lus, casse = lis(a.trades, depuis)
    if T is None:
        print("introuvable : %s" % a.trades)
        print("Ce panneau ne lit que ce fichier. Sans lui il n a rien a")
        print("dire, et il ne va pas inventer des trades pour remplir la")
        print("page.")
        return 2

    paires, orph = apparie(T)
    txt = rendu(paires, orph, lus, casse, depuis)
    if not a.html_seul:
        print(txt)

    if not os.path.isdir(a.sortie):
        os.makedirs(a.sortie)
    t = os.path.join(a.sortie, "panel_papier_tf.txt")
    h = os.path.join(a.sortie, "papier_tf_ab.html")
    io.open(t, "w", encoding="utf-8", newline="").write(txt + "\n")
    io.open(h, "w", encoding="utf-8", newline="").write(
        page_html(paires, orph, lus, casse, depuis, txt))
    print("")
    print("  ecrit : %s" % t)
    print("  ecrit : %s" % h)
    print("  visible sur  /carte?f=papier_tf_ab.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())

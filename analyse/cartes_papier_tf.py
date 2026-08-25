#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""cartes_papier_tf.py -- l A/B de sortie du papier, 206 contre 207.

  python cartes_papier_tf.py
  python cartes_papier_tf.py --jours 5
  python cartes_papier_tf.py --html-seul

CE QUE C EST, ET CE QUE CE N EST PAS
------------------------------------
docs\papier_tf\trades.jsonl porte deux bras et deux seulement : 206 et
207. Ni 220xxx, ni 230xxx, ni 240xxx. Ce fichier n est donc PAS le
papier des strategies du panneau, et les poser cote a cote comparerait
deux choses differentes en donnant l illusion du contraire.

Ce qu il est, papier_tf.py le dit : "MEMES ENTREES que le 206 -- c est
un A/B de la SORTIE". Soit exactement la question que pose le miroir 1
contre le miroir 2, mais sur douze jours et plus de mille trades au
lieu d une seance.

LES SORTIES FRACTIONNEES -- LE PIEGE DU PREMIER PASSAGE
-------------------------------------------------------
papier_tf.py, ligne 432 : "une sortie, totale ou partielle. Le 207 en
produit deux". Le 207 solde en DEUX FOIS. C est ce qui explique 740
enregistrements cote 207 pour 504 cote 206 : pas deux fois plus de
trades, des trades coupes en deux.

La premiere version de ce fichier ne gardait qu un enregistrement par
(actif, horizon, ouverture) et par bras. Elle amputait donc le 207 de
la moitie de chaque trade fractionne, et annoncait "-5.98 par trade en
faveur du 206" -- un chiffre qui mesurait le DECOUPAGE, pas la SORTIE.

fusionne() somme desormais les morceaux d une meme entree. Le nombre
d entrees fractionnees est compte et AFFICHE par bras : c est une
transformation des donnees, elle doit se voir.

L APPARIEMENT
-------------
"Memes entrees" ne veut pas dire "memes effectifs" : une entree peut
sortir d un cote et pas encore de l autre. Comparer les totaux de deux
populations inegales attribuerait a la SORTIE un ecart qui vient du
NOMBRE. On apparie sur (actif, horizon, instant d ouverture) et on ne
compare que les paires. Les orphelins sont comptes, pas jetes en
silence : une exclusion tue est une exclusion qui ment.

LES MESURES, ET CE QU ELLES VALENT
----------------------------------
    taux      part de trades gagnants
    borne     borne basse de Wilson a 95 %. Sur dix trades elle tombe
              tres bas, et c est exact : dix trades ne disent rien.
              C est la seule colonne qui l avoue.
    RR eq     ratio gain/perte necessaire pour rentrer dans ses frais,
              soit (1-p)/p. Au-dessus, la strategie gagne.
    PF        facteur de profit : somme des gains / somme des pertes.
              1.0 = equilibre. "inf" quand il n y a aucune perte --
              affiche tel quel plutot que borne, car c est un signal
              d effectif trop faible, pas une performance.
    esp       esperance par trade, en euros.
    sigma     ecart-type par trade. La dispersion est ce qui rend un
              ecart de moyenne difficile a prouver.
    Sharpe    esp / sigma, PAR TRADE et NON ANNUALISE. Annualiser
              demanderait de supposer un nombre de trades par an ; on
              ne le suppose pas.

    t         LE chiffre de l A/B. Test de Student sur les differences
              APPARIEES : moyenne(207-206) / (ecart-type / racine(n)).
              Les paires partagent la meme entree, donc le meme alea
              de marche -- l apparier annule cet alea et ne laisse que
              l effet de la sortie. |t| au-dela de 2 : l ecart tient
              difficilement du hasard. En deca, il y tient tres bien.

              Un ecart en euros sans son t ne dit rien. C est pour ca
              qu ils sont cote a cote.

OU IL ECRIT
    cartes\panel_papier_tf.txt
    cartes\papier_tf_ab.html      visible sur /carte?f=papier_tf_ab.html
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
INF = float("inf")


# ----------------------------------------------------------------------
# LECTURE ET APPARIEMENT
# ----------------------------------------------------------------------
def lis(chemin, depuis=None):
    """(trades, lus, illisibles). Une ligne cassee est comptee, pas
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


def fusionne(recs):
    """Un bras peut solder une entree en DEUX FOIS -- papier_tf.py,
    ligne 432. Les morceaux appartiennent a la MEME entree : on somme
    leurs resultats et on garde le motif du DERNIER, celui qui solde.

    N en garder qu un amputerait ce bras de la moitie de chaque trade
    coupe, et l A/B mesurerait le decoupage au lieu de la sortie."""
    recs = sorted(recs, key=lambda o: str(o.get("ts", "")))
    d = dict(recs[-1])
    d["eur"] = sum(float(o.get("eur", 0.0)) for o in recs)
    d["points"] = sum(float(o.get("points", 0.0)) for o in recs)
    d["parts"] = len(recs)
    return d


def apparie(T):
    """(paires, orphelins, fractionnees)."""
    par = {}
    for o in T:
        b = str(o.get("bras", ""))
        if b not in BRAS:
            continue
        cle = (o.get("actif"), o.get("mn"), o.get("ouvert"))
        par.setdefault(cle, {}).setdefault(b, []).append(o)
    par = {k: {b: fusionne(r) for b, r in v.items()} for k, v in par.items()}
    paires = [(k, v[BRAS[0]], v[BRAS[1]])
              for k, v in par.items() if len(v) == 2]
    orph = {b: sum(1 for v in par.values() if len(v) == 1 and b in v)
            for b in BRAS}
    frac = {b: sum(1 for v in par.values()
                   if b in v and v[b].get("parts", 1) > 1) for b in BRAS}
    return paires, orph, frac


# ----------------------------------------------------------------------
# LES MESURES
# ----------------------------------------------------------------------
def wilson(p, n, z=1.96):
    """Borne basse a 95 %. Sur petit effectif elle s effondre, et c est
    le but : elle refuse de confondre un taux mesure et un taux vrai."""
    if n <= 0:
        return 0.0
    d = 1.0 + z * z / n
    c = p + z * z / (2.0 * n)
    r = z * ((p * (1.0 - p) / n + z * z / (4.0 * n * n)) ** 0.5)
    return max(0.0, (c - r) / d)


def stats(v):
    if not v:
        return None
    n = len(v)
    g = [x for x in v if x > 0]
    pe = [x for x in v if x < 0]
    som = sum(v)
    moy = som / n
    sd = ((sum((x - moy) ** 2 for x in v) / (n - 1.0)) ** 0.5) if n > 1 else 0.0
    taux = len(g) / float(n)
    return {"n": n, "pnl": som, "esp": moy, "sd": sd, "taux": taux,
            "borne": wilson(taux, n),
            "pf": (sum(g) / abs(sum(pe))) if pe else INF,
            "rr": ((1.0 - taux) / taux) if taux > 0 else INF,
            "sharpe": (moy / sd) if sd > 0 else 0.0}


def student(d):
    """Test apparie. Les deux bras partagent la MEME entree, donc le
    meme alea de marche : l apparier l annule et ne laisse que l effet
    de la sortie. C est bien plus puissant qu une comparaison de deux
    moyennes independantes."""
    n = len(d)
    if n < 2:
        return None
    m = sum(d) / n
    sd = (sum((x - m) ** 2 for x in d) / (n - 1.0)) ** 0.5
    if sd <= 0:
        return None
    return m / (sd / (n ** 0.5))


def groupe(paires, cle=None):
    out = {}
    for k, a, b in paires:
        nom = "toutes" if cle is None else cle(k, a, b)
        c = out.setdefault(nom, {"a": [], "b": [], "d": []})
        ea, eb = float(a.get("eur", 0.0)), float(b.get("eur", 0.0))
        c["a"].append(ea)
        c["b"].append(eb)
        c["d"].append(eb - ea)
    return out


def rangs(d, ordre=None):
    cles = sorted(d, key=ordre) if ordre else sorted(d, key=str)
    return [(k, d[k]) for k in cles]


# ----------------------------------------------------------------------
# RENDU TEXTE -- la source de verite
# ----------------------------------------------------------------------
def f_pf(v):
    return "inf" if v == INF else "%.2f" % v


def f_rr(v):
    return "inf" if v == INF else "%.2f" % v


LARGE = 118


def bloc_texte(titre, lignes, lib):
    L = ["", "=" * LARGE, titre, "=" * LARGE, "-" * LARGE,
         "%-24s %-5s %5s %5s %6s %6s %6s %9s %8s %7s"
         % (lib[:24], "bras", "n", "taux", "borne", "RR eq", "PF", "PnL",
            "esp", "Sharpe"),
         "-" * LARGE]
    for nom, c in lignes:
        sa, sb = stats(c["a"]), stats(c["b"])
        t = student(c["d"])
        if sa is None or sb is None:
            continue
        for lbl, s in (("206", sa), ("207", sb)):
            L.append("%-24s %-5s %5d %4.0f%% %5.0f%% %6s %6s %+9.2f %+8.2f"
                     " %7.2f"
                     % (str(nom)[:24] if lbl == "206" else "", lbl, s["n"],
                        100 * s["taux"], 100 * s["borne"], f_rr(s["rr"]),
                        f_pf(s["pf"]), s["pnl"], s["esp"], s["sharpe"]))
        d = sb["pnl"] - sa["pnl"]
        L.append("%-24s %-5s %5s %4s  %5s  %6s %6s %+9.2f %+8.2f  t=%s"
                 % ("", "ecart", "", "", "", "", "", d, d / sa["n"],
                    ("%+.2f" % t) if t is not None else "--"))
        L.append("")
    return L


def rendu(paires, orph, frac, lus, casse, depuis):
    L = ["=" * LARGE,
         "PAPIER TF -- A/B DE SORTIE, LE BRAS 206 CONTRE LE 207",
         "=" * LARGE,
         "  source   : docs\\papier_tf\\trades.jsonl",
         "  lus      : %d enregistrements TRADE%s"
         % (lus, ", %d illisibles" % casse if casse else ""),
         "  fenetre  : %s" % (depuis or "tout le fichier"),
         ""]
    if not paires:
        L += ["  AUCUNE PAIRE sur la fenetre demandee. Rien a comparer.",
              ""]
        return "\n".join(L)

    g = groupe(paires)["toutes"]
    sa, sb = stats(g["a"]), stats(g["b"])
    t = student(g["d"])
    d = sb["pnl"] - sa["pnl"]
    L += ["  paires   : %d entrees soldees DES DEUX cotes" % sa["n"],
          "  orphelins: 206 %d, 207 %d -- exclus, et comptes ici plutot"
          % (orph.get("206", 0), orph.get("207", 0)),
          "             que jetes en silence.",
          "  fraction.: 206 %d, 207 %d entrees soldees en DEUX FOIS,"
          % (frac.get("206", 0), frac.get("207", 0)),
          "             morceaux sommes. N en garder qu un amputerait ce",
          "             bras de la moitie de chaque trade coupe.",
          "",
          "  VERDICT SUR LES PAIRES",
          "     206  %+.2f   esp %+.2f   PF %s   Sharpe %.2f"
          % (sa["pnl"], sa["esp"], f_pf(sa["pf"]), sa["sharpe"]),
          "     207  %+.2f   esp %+.2f   PF %s   Sharpe %.2f"
          % (sb["pnl"], sb["esp"], f_pf(sb["pf"]), sb["sharpe"]),
          "     ecart %+.2f  soit %+.2f par trade,  t apparie = %s"
          % (d, d / sa["n"], ("%+.2f" % t) if t is not None else "--"),
          ""]
    if t is None:
        L.append("     t incalculable : trop peu de paires.")
    elif abs(t) >= 2.0:
        L.append("     |t| >= 2 : l ecart tient difficilement du hasard.")
    else:
        L += ["     |t| < 2 : L ECART TIENT TRES BIEN DU HASARD. Le",
              "     montant en euros peut impressionner, il ne prouve",
              "     rien a ce stade -- la dispersion par trade (sigma",
              "     %.2f et %.2f) est d un autre ordre de grandeur que"
              % (sa["sd"], sb["sd"]),
              "     l ecart moyen (%+.2f)." % (d / sa["n"])]
    L.append("")

    L += bloc_texte("PAR ACTIF", rangs(groupe(paires, lambda k, a, b: k[0])),
                    "actif")
    L += bloc_texte("PAR HORIZON",
                    rangs(groupe(paires, lambda k, a, b: k[1]),
                          ordre=lambda x: (x is None, x)), "horizon (min)")
    L += bloc_texte("ACTIF x HORIZON",
                    rangs(groupe(paires,
                                 lambda k, a, b: "%s %s min" % (k[0], k[1]))),
                    "actif x horizon")
    L += bloc_texte("PAR MOTIF DE SORTIE DU 207",
                    rangs(groupe(paires,
                                 lambda k, a, b: b.get("motif") or "?")),
                    "motif du 207")
    L += ["  LE MOTIF EST CELUI DU 207. Il repond a : quand le 207 sort",
          "  POUR CETTE RAISON, gagne-t-il ou perd-il contre le 206 sur",
          "  la meme entree ? C est la seule des quatre lectures qui",
          "  designe un MECANISME et non un perimetre.",
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
#pt .sous{color:#8b949e;margin:0 0 16px;max-width:80ch}
#pt h3{font:600 12px system-ui;letter-spacing:.07em;text-transform:uppercase;
    color:#8b949e;margin:26px 0 9px;border-bottom:1px solid #30363d;
    padding-bottom:7px}
#pt .tuiles{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 18px}
#pt .tuile{background:#161b22;border:1px solid #30363d;border-radius:7px;
    padding:9px 14px;min-width:104px}
#pt .lib{color:#8b949e;font-size:11px;text-transform:uppercase;
    letter-spacing:.06em}
#pt .val{font:600 16px ui-monospace,Consolas,monospace;color:#e6edf3;
    font-variant-numeric:tabular-nums}
#pt .avis{background:#161b22;border-left:3px solid #58a6ff;border-radius:5px;
    padding:11px 15px;margin:0 0 18px;color:#c9d1d9;max-width:100ch;
    font-size:12.5px;line-height:1.55}
#pt .alerte{border-left-color:#d29922}
#pt table{border-collapse:collapse;width:100%;margin:0 0 8px}
#pt th{padding:7px 9px;text-align:right;color:#8b949e;font-size:11px;
    font-weight:600;text-transform:uppercase;letter-spacing:.05em;
    border-bottom:1px solid #30363d;white-space:nowrap}
#pt td{padding:6px 9px;text-align:right;border-bottom:1px solid #161b22;
    font-variant-numeric:tabular-nums;white-space:nowrap}
#pt tr.g206 td{background:rgba(139,148,158,.05)}
#pt tr.g207 td{background:rgba(88,166,255,.06)}
#pt tr.ec td{background:rgba(230,237,243,.05);font-weight:600;
    border-bottom:1px solid #30363d}
#pt td.k{text-align:left;color:#e6edf3;font-weight:600}
#pt td.br{text-align:left;color:#8b949e;font-size:11.5px}
#pt .vert{color:#3fb950;font-weight:600}
#pt .rouge{color:#f85149;font-weight:600}
#pt .gris{color:#6e7681}
#pt .fort{background:#1f2d20;border-radius:4px;padding:1px 6px}
#pt .faible{color:#6e7681}
</style>"""


def ech(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def sig(v, f="%+.2f"):
    k = "vert" if v > 0 else ("rouge" if v < 0 else "gris")
    return '<span class="%s">%s</span>' % (k, f % v)


def ligne_bras(nom, lbl, s, cls):
    return ('<tr class="%s"><td class="k">%s</td><td class="br">%s</td>'
            '<td>%d</td><td>%.0f&#37;</td><td>%.0f&#37;</td><td>%s</td>'
            '<td>%s</td><td>%s</td><td>%s</td><td>%.2f</td>'
            '<td class="faible">%.0f</td></tr>'
            % (cls, ech(nom), lbl, s["n"], 100 * s["taux"], 100 * s["borne"],
               f_rr(s["rr"]), f_pf(s["pf"]), sig(s["pnl"]), sig(s["esp"]),
               s["sharpe"], s["sd"]))


def table_html(lignes, lib):
    o = ['<table><thead><tr>'
         '<th style="text-align:left">%s</th><th style="text-align:left">'
         'bras</th><th>n</th><th>taux</th><th>Wilson</th><th>RR eq</th>'
         '<th>PF</th><th>PnL</th><th>esp</th><th>Sharpe</th>'
         '<th>sigma</th></tr></thead><tbody>' % ech(lib)]
    for nom, c in lignes:
        sa, sb = stats(c["a"]), stats(c["b"])
        if sa is None or sb is None:
            continue
        t = student(c["d"])
        o.append(ligne_bras(nom, "206", sa, "g206"))
        o.append(ligne_bras("", "207", sb, "g207"))
        d = sb["pnl"] - sa["pnl"]
        tt = ("--" if t is None else "%+.2f" % t)
        cl = "fort" if (t is not None and abs(t) >= 2.0) else ""
        o.append('<tr class="ec"><td></td><td class="br">207 &minus; 206</td>'
                 '<td></td><td>%s</td><td></td><td></td><td></td>'
                 '<td>%s</td><td>%s</td><td colspan="2">'
                 '<span class="%s">t = %s</span></td></tr>'
                 % (sig(100 * (sb["taux"] - sa["taux"]), "%+.0f&#37;"),
                    sig(d), sig(d / sa["n"]), cl, tt))
    return "".join(o) + '</tbody></table>'


def page_html(paires, orph, frac, lus, casse, depuis, txt):
    if not paires:
        return (CSS + '<div id="pt"><h1>Papier TF &mdash; A/B de sortie</h1>'
                '<div class="avis">Aucune paire sur la fenetre demandee.'
                ' Rien a comparer.</div></div>')
    g = groupe(paires)["toutes"]
    sa, sb = stats(g["a"]), stats(g["b"])
    t = student(g["d"])
    d = sb["pnl"] - sa["pnl"]
    tuiles = [("paires", "%d" % sa["n"]),
              ("orphelins", "%d" % (orph.get("206", 0) + orph.get("207", 0))),
              ("fractionnees 207", "%d" % frac.get("207", 0)),
              ("PnL 206", "%+.0f" % sa["pnl"]),
              ("PnL 207", "%+.0f" % sb["pnl"]),
              ("ecart / trade", "%+.2f" % (d / sa["n"])),
              ("t apparie", "--" if t is None else "%+.2f" % t)]
    if t is None:
        verdict = ("Trop peu de paires pour calculer un t.")
    elif abs(t) >= 2.0:
        verdict = ("<b>|t| = %.2f, au-dela de 2.</b> Un ecart de cette"
                   " taille tient difficilement du hasard sur %d paires."
                   % (abs(t), sa["n"]))
    else:
        verdict = ("<b>|t| = %.2f, en deca de 2.</b> L ecart de %+.2f euros"
                   " peut impressionner : il tient tres bien du hasard. La"
                   " dispersion par trade (sigma %.0f et %.0f) est d un"
                   " autre ordre de grandeur que l ecart moyen (%+.2f). Un"
                   " montant sans son t ne dit rien."
                   % (abs(t), d, sa["sd"], sb["sd"], d / sa["n"]))
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
         '<div class="avis%s">%s</div>'
         % ("" if (t is not None and abs(t) >= 2.0) else " alerte", verdict),
         '<div class="avis"><b>Le t est apparie</b>, et c est ce qui le'
         ' rend puissant : les deux bras partagent la MEME entree, donc'
         ' le meme alea de marche. L apparier annule cet alea et ne'
         ' laisse que l effet de la sortie.<br><br>'
         '<b>Appariement</b> sur (actif, horizon, instant d ouverture) :'
         ' %d paires, %d orphelins exclus. <b>Sorties fractionnees</b> :'
         ' %d entrees cote 206 et %d cote 207 sont soldees en deux fois'
         ' &mdash; leurs morceaux sont sommes, sans quoi l A/B mesurerait'
         ' le decoupage au lieu de la sortie.<br><br>'
         '<b>PF</b> = gains / pertes. <b>RR eq</b> = (1-p)/p, le ratio'
         ' necessaire pour rentrer dans ses frais. <b>Wilson</b> = borne'
         ' basse du taux a 95 %%. <b>Sharpe</b> = esperance / sigma,'
         ' <b>par trade et non annualise</b> : annualiser demanderait de'
         ' supposer un nombre de trades par an, on ne le suppose pas.'
         '</div>'
         % (sa["n"], orph.get("206", 0) + orph.get("207", 0),
            frac.get("206", 0), frac.get("207", 0))]
    o.append('<h3>Par actif</h3>')
    o.append(table_html(rangs(groupe(paires, lambda k, a, b: k[0])), "actif"))
    o.append('<h3>Par horizon</h3>')
    o.append(table_html(rangs(groupe(paires, lambda k, a, b: k[1]),
                              ordre=lambda x: (x is None, x)),
                        "horizon (min)"))
    o.append('<h3>Actif &times; horizon</h3>')
    o.append(table_html(rangs(groupe(
        paires, lambda k, a, b: "%s %s min" % (k[0], k[1]))),
        "actif x horizon"))
    o.append('<h3>Par motif de sortie du 207</h3>')
    o.append('<div class="avis">Le motif est celui du <b>207</b> : quand'
             ' il sort POUR CETTE RAISON, gagne-t-il ou perd-il contre le'
             ' 206 sur la meme entree ? C est la seule des quatre lectures'
             ' qui designe un <b>mecanisme</b> et non un perimetre.</div>')
    o.append(table_html(rangs(groupe(paires,
                                     lambda k, a, b: b.get("motif") or "?")),
                        "motif du 207"))
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
    ap.add_argument("--jours", type=int, default=0)
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
        print("dire, et il n inventera pas des trades pour remplir la page.")
        return 2

    paires, orph, frac = apparie(T)
    txt = rendu(paires, orph, frac, lus, casse, depuis)
    if not a.html_seul:
        print(txt)

    if not os.path.isdir(a.sortie):
        os.makedirs(a.sortie)
    t = os.path.join(a.sortie, "panel_papier_tf.txt")
    h = os.path.join(a.sortie, "papier_tf_ab.html")
    io.open(t, "w", encoding="utf-8", newline="").write(txt + "\n")
    io.open(h, "w", encoding="utf-8", newline="").write(
        page_html(paires, orph, frac, lus, casse, depuis, txt))
    print("")
    print("  ecrit : %s" % t)
    print("  ecrit : %s" % h)
    print("  visible sur  /carte?f=papier_tf_ab.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())

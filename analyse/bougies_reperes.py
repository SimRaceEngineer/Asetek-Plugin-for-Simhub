# -*- coding: utf-8 -*-
r"""
bougies_reperes.py -- REPERER les bougies au comportement different,
                      avant de tester quoi que ce soit

  python bougies_reperes.py
  python bougies_reperes.py --html 2026-08-14
  python bougies_reperes.py --centile 99.5 --montre 40

POURQUOI CET OUTIL EXISTE

    Reproche de l utilisateur, 18/08, et il est fonde :

      "tu as completement squize ces variables dans ton code, or c est
       le propre de l orderflow de nous permettre de visualiser les
       ordres. En chart TradingView, au lieu des candlestick, TV peut
       aussi proposer des candlesticks proportionnels au nombre d ordres
       et c est la meme idee de visualiser des bougies reperes."

    Les fichiers `of_*.csv` portent QUATORZE colonnes :

      ts open high low close trades volume bid_vol ask_vol delta cvd
      spread_moy contrat roulement

    Mes outils en lisaient CINQ -- ts, close, delta, volume, contrat.
    `trades`, `high`, `low`, `spread_moy` etaient la depuis le debut,
    sur 183 314 barres, et je mesurais des sommes de delta.

    Une bougie de meme volume et meme delta, remplie en cinq secondes
    ou etalee sur soixante, etait le MEME POINT dans toutes mes
    mesures. C est ce que cet outil repare.

IL REPERE, IL NE CONCLUT PAS

    Aucune p-value. Aucun temoin. Aucune issue. C est DELIBERE : on ne
    peut pas tester une hypothese sur les bougies reperes tant qu on ne
    sait pas les designer. Le repere vient d abord, la mesure ensuite.

    Consequence directe : cet outil NE CONSOMME PAS la coupe de
    confirmation du paragraphe 10 du protocole. Il decrit, donc il ne
    brule rien.

LES SIX DIMENSIONS, TOUTES NORMALISEES PAR LA JOURNEE ET L ACTIF

    Chaque minute est rapportee a la mediane de SA seance, sur SON
    actif -- sans quoi MES et YM ne seraient pas comparables et les
    journees calmes seraient toutes ignorees.

      VITESSE   trades              / mediane des trades
      TAILLE    volume / trades     / mediane du volume par trade
      AMPLEUR   high - low          / mediane du high - low
      PRESSION  |delta|             / mediane des |delta|
      SPREAD    spread_moy          / mediane du spread
      RENDU     AMPLEUR / PRESSION  -- ce que le prix rend pour ce que
                                      le flux pousse

    RENDU est la dimension qui dit l absorption : beaucoup de flux,
    peu d amplitude. Une minute ordinaire vaut 1 sur les six.

LE SEUIL EST MESURE, PAS INVENTE

    Une minute est REPERE si elle depasse le centile demande (99 par
    defaut) de la distribution de SA seance, sur au moins une
    dimension.

    ATTENTION AU COMPTE, corrige au banc : le centile est PAR
    DIMENSION. Six dimensions a 1 % chacune donnent une UNION d
    environ 6 %, pas 1 %. Sur 1250 barres reelles, attendez-vous a ~75
    reperes par seance et par actif, pas a une douzaine -- la premiere
    version de cette docstring l annoncait a tort.

    Pour un repere vraiment rare, deux chemins : monter le centile
    (--centile 99.8), ou ne retenir que les minutes franchissant
    PLUSIEURS dimensions -- ce que la colonne `franchies` du listing
    permet de faire a l oeil.

    Le centile est affiche en valeur absolue pour chaque dimension :
    un seuil qu on ne montre pas ne vaut pas mieux qu un seuil invente.

CE QUE LA TABLE DE CO-OCCURRENCE REPOND

    "Rapide", "gros", "large" et "absorbe" sont-ils quatre noms du meme
    phenomene, ou quatre phenomenes ? La table croise les dimensions
    deux a deux sur les minutes reperees. Si VITESSE et PRESSION se
    recouvrent a 90 %, on n a qu une variable sous deux noms.

    C est la question a trancher AVANT de pre-enregistrer quoi que ce
    soit : pre-enregistrer six variables qui n en sont qu une serait
    payer six tests pour une information.

L HTML : LA BOUGIE PROPORTIONNELLE AUX ORDRES

    `--html AAAA-MM-JJ` ecrit une page ou chaque bougie a la LARGEUR
    proportionnelle a son nombre de trades -- l idee TradingView, sur
    nos donnees. Les reperes sont cercles. C est du SVG pur, aucune
    dependance, ouvrable au double-clic.

LECTEUR SEUL. N ecrit que dans `cartes\`.
"""
import argparse
import csv
import io
import os
import sys
from datetime import datetime

DOSSIER = os.path.join("cartes", "scid")
SORTIE = "cartes"
FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M")

DIMS = ("VITESSE", "TAILLE", "AMPLEUR", "PRESSION", "SPREAD", "RENDU")


def horo(s):
    if not s:
        return None
    s = s.strip()
    for f in FORMATS:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def med(v):
    if not v:
        return None
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def centile(v, c):
    if not v:
        return None
    s = sorted(v)
    i = int(round((c / 100.0) * (len(s) - 1)))
    return s[max(0, min(len(s) - 1, i))]


def charge(dossier):
    """Les of_*.csv, QUATORZE colonnes, dedoublonnes par `contrat`."""
    out = {}
    if not os.path.isdir(dossier):
        return out, []
    for nom in sorted(os.listdir(dossier)):
        if not nom.startswith("of_") or not nom.endswith(".csv"):
            continue
        serie = []
        with io.open(os.path.join(dossier, nom), encoding="utf-8",
                     errors="replace") as f:
            for r in csv.DictReader(f, delimiter=";"):
                t = horo(r.get("ts"))
                c = flt(r.get("close"))
                if t is None or c is None:
                    continue
                serie.append({
                    "t": t, "o": flt(r.get("open")) or c,
                    "h": flt(r.get("high")) or c, "b": flt(r.get("low")) or c,
                    "c": c, "n": flt(r.get("trades")) or 0.0,
                    "v": flt(r.get("volume")) or 0.0,
                    "d": flt(r.get("delta")) or 0.0,
                    "sp": flt(r.get("spread_moy")) or 0.0,
                    "k": (r.get("contrat") or "").strip()})
        if len(serie) > 100:
            serie.sort(key=lambda x: x["t"])
            out[nom[3:-4]] = serie
    absorbes = {}
    for sym, serie in out.items():
        for n in set(x["k"] for x in serie if x["k"]):
            if n != sym and n in out:
                absorbes[n] = sym
    msg = ["  of_%s.csv ecarte : deja dans of_%s.csv (colonne `contrat`)"
           % (n, s) for n, s in sorted(absorbes.items())]
    return dict((s, v) for s, v in out.items() if s not in absorbes), msg


def sans_carnet(barres):
    """Meme exclusion que partout ailleurs -- un indice n a pas de
    carnet. La regle est reprise, pas reinventee."""
    out = []
    for sym in sorted(barres):
        cl = [b["c"] for b in barres[sym]]
        if cl and min(cl) <= 0:
            out.append((sym, "la serie traverse zero -- oscillateur"))
    for sym, _ in out:
        del barres[sym]
    return out


def dimensions(jour):
    """Les six dimensions d une seance, normalisees par ses medianes."""
    mn = med([b["n"] for b in jour if b["n"] > 0]) or 0.0
    mt = med([b["v"] / b["n"] for b in jour if b["n"] > 0]) or 0.0
    ma = med([b["h"] - b["b"] for b in jour]) or 0.0
    mp = med([abs(b["d"]) for b in jour if b["d"]]) or 0.0
    ms = med([b["sp"] for b in jour if b["sp"] > 0]) or 0.0
    for b in jour:
        b["VITESSE"] = b["n"] / mn if mn else 0.0
        b["TAILLE"] = ((b["v"] / b["n"]) / mt) if (b["n"] and mt) else 0.0
        b["AMPLEUR"] = ((b["h"] - b["b"]) / ma) if ma else 0.0
        b["PRESSION"] = (abs(b["d"]) / mp) if mp else 0.0
        b["SPREAD"] = (b["sp"] / ms) if ms else 0.0
        b["RENDU"] = (b["AMPLEUR"] / b["PRESSION"]) if b["PRESSION"] else 0.0
    return {"trades": mn, "taille": mt, "ampleur": ma,
            "pression": mp, "spread": ms}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dossier", default=DOSSIER)
    p.add_argument("--centile", type=float, default=99.0,
                   help="seuil de repere, en centile de la seance")
    p.add_argument("--montre", type=int, default=25)
    p.add_argument("--html", default=None, help="AAAA-MM-JJ")
    a = p.parse_args()

    print("=" * 78)
    print("BOUGIES REPERES -- reperer avant de mesurer")
    print("=" * 78)
    print("  Seuil : centile %.1f de la seance, sur au moins une des six"
          % a.centile)
    print("  dimensions. Chacune est rapportee a la mediane de SA")
    print("  seance et de SON actif : une journee calme a ses reperes")
    print("  comme une journee agitee.")
    print()
    print("  AUCUNE p-value, aucun temoin : cet outil DECRIT. Il ne")
    print("  consomme donc pas la coupe de confirmation du paragraphe 10.")
    print()

    barres, msg = charge(a.dossier)
    for m in msg:
        print(m)
    for sym, r in sans_carnet(barres):
        print("  %-16s ECARTE : %s" % (sym, r))
    if not barres:
        print("KO : aucun of_*.csv exploitable dans %s." % a.dossier)
        return 1
    print()

    tout = {}
    for sym in sorted(barres):
        jours = {}
        for b in barres[sym]:
            jours.setdefault(b["t"].date(), []).append(b)
        cpt = sorted(len(v) for v in jours.values())
        seuil_j = max(30, (cpt[len(cpt) // 2] if cpt else 0) // 2)
        reperes, nseances, seuils = [], 0, dict((d, []) for d in DIMS)
        for jour in sorted(jours):
            j = jours[jour]
            if len(j) < seuil_j:
                continue
            nseances += 1
            dimensions(j)
            lim = {}
            for d in DIMS:
                lim[d] = centile([b[d] for b in j], a.centile)
                if lim[d]:
                    seuils[d].append(lim[d])
            for b in j:
                q = [d for d in DIMS if lim[d] and b[d] >= lim[d]]
                if q:
                    b["quoi"] = q
                    b["sym"] = sym
                    reperes.append(b)
        tout[sym] = reperes
        print("  %-16s %d seances   %d bougies reperes   (%.2f par seance)"
              % (sym, nseances, len(reperes),
                 float(len(reperes)) / max(1, nseances)))
        print("  %-16s seuils medians : %s" % ("", "  ".join(
            "%s %.1f" % (d, med(seuils[d]) or 0.0) for d in DIMS)))
    print()

    # --- co-occurrence : combien de phenomenes, au juste ? ----------
    print("=" * 78)
    print("CO-OCCURRENCE -- six dimensions, ou six noms de la meme ?")
    print("=" * 78)
    print("  Part des reperes d une dimension (ligne) qui sont AUSSI")
    print("  reperes sur l autre (colonne). Un recouvrement eleve dit")
    print("  qu on a une variable sous deux noms -- et pre-enregistrer")
    print("  deux variables identiques, c est payer deux tests pour une")
    print("  information.")
    print()
    for sym in sorted(tout):
        r = tout[sym]
        if not r:
            continue
        print("  %s   %d reperes" % (sym, len(r)))
        print("      %-10s %s" % ("", " ".join("%8s" % d[:8] for d in DIMS)))
        for d1 in DIMS:
            a1 = [b for b in r if d1 in b["quoi"]]
            cells = []
            for d2 in DIMS:
                if not a1:
                    cells.append("%8s" % "-")
                elif d1 == d2:
                    cells.append("%7d%%" % 100)
                else:
                    n = len([b for b in a1 if d2 in b["quoi"]])
                    cells.append("%7d%%" % int(round(100.0 * n / len(a1))))
            print("      %-10s %s   (n=%d)" % (d1, " ".join(cells), len(a1)))
        print()

    # --- le listing -------------------------------------------------
    print("=" * 78)
    print("LES PLUS MARQUEES -- triees par nombre de dimensions franchies")
    print("=" * 78)
    for sym in sorted(tout):
        r = sorted(tout[sym], key=lambda b: (-len(b["quoi"]),
                                             -b["VITESSE"]))[:a.montre]
        if not r:
            continue
        print("  %s" % sym)
        print("    %-17s %6s %6s %6s %6s %6s %6s  %s"
              % ("instant", "VITES", "TAILL", "AMPLE", "PRESS", "SPRE",
                 "RENDU", "franchies"))
        for b in r:
            print("    %-17s %6.1f %6.1f %6.1f %6.1f %6.1f %6.1f  %s"
                  % (b["t"].strftime("%Y-%m-%d %H:%M"), b["VITESSE"],
                     b["TAILLE"], b["AMPLEUR"], b["PRESSION"], b["SPREAD"],
                     b["RENDU"], ",".join(x[:4] for x in b["quoi"])))
        print()

    if a.html:
        ecris_html(barres, tout, a.html, a.centile)

    print("=" * 78)
    print("CE QUE CA NE DIT PAS")
    print("=" * 78)
    print("  Rien sur la suite. Une bougie repere n est pour l instant")
    print("  qu une bougie inhabituelle : savoir si le prix y revient")
    print("  demande un temoin apparie et une mesure separee.")
    print("  Rien sur la cause. Une minute rapide peut suivre une")
    print("  nouvelle que le calendrier ne porte pas.")
    print("  Aucun euro.")
    return 0


def ecris_html(barres, tout, jour, cent):
    """Les bougies d une seance, LARGEUR proportionnelle aux trades.

    L idee vient de TradingView, qui sait tracer des chandeliers dont
    la largeur suit le nombre d ordres. Ici c est du SVG pur : aucune
    dependance, aucun CDN, ouvrable au double-clic."""
    try:
        d = datetime.strptime(jour, "%Y-%m-%d").date()
    except ValueError:
        print("  --html : date illisible, attendu AAAA-MM-JJ.")
        return
    blocs = []
    for sym in sorted(barres):
        j = [b for b in barres[sym] if b["t"].date() == d]
        if len(j) < 30:
            continue
        dimensions(j)
        rep = set(b["t"] for b in tout.get(sym, []) if b["t"].date() == d)
        hi = max(b["h"] for b in j)
        lo = min(b["b"] for b in j)
        ech = 420.0 / (hi - lo) if hi > lo else 1.0
        mn = med([b["n"] for b in j if b["n"] > 0]) or 1.0
        pas = max(2.0, min(9.0, 1500.0 / len(j)))
        sv = []
        for i, b in enumerate(j):
            x = 60 + i * pas
            w = max(0.6, min(pas * 2.6, pas * (b["n"] / mn) ** 0.5))
            y1 = 20 + (hi - b["h"]) * ech
            y2 = 20 + (hi - b["b"]) * ech
            yo = 20 + (hi - b["o"]) * ech
            yc = 20 + (hi - b["c"]) * ech
            col = "#3fb950" if b["c"] >= b["o"] else "#f85149"
            sv.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                      'stroke="%s" stroke-width="0.8"/>'
                      % (x, y1, x, y2, col))
            sv.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                      'fill="%s" opacity="0.85"><title>%s\ntrades %d  '
                      'vol %d  delta %+d\nvitesse x%.1f  ampleur x%.1f'
                      '</title></rect>'
                      % (x - w / 2, min(yo, yc), w, max(1.0, abs(yc - yo)),
                         col, b["t"].strftime("%H:%M"), b["n"], b["v"],
                         b["d"], b["VITESSE"], b["AMPLEUR"]))
            if b["t"] in rep:
                sv.append('<circle cx="%.1f" cy="%.1f" r="%.1f" '
                          'fill="none" stroke="#d29922" stroke-width="1.4"/>'
                          % (x, (y1 + y2) / 2, max(5.0, w)))
        blocs.append(
            '<h2>%s &mdash; %d minutes, %d rep&egrave;re(s)</h2>'
            '<svg width="%d" height="470" style="background:#0d1117">%s</svg>'
            % (sym, len(j), len(rep), int(120 + len(j) * pas), "".join(sv)))
    if not blocs:
        print("  --html : aucune seance le %s." % jour)
        return
    html = (u'<!doctype html><meta charset="utf-8"><title>Bougies '
            u'reperes %s</title><style>body{background:#0d1117;'
            u'color:#c9d1d9;font:14px system-ui;padding:18px}'
            u'h2{color:#58a6ff;font-size:15px;margin:22px 0 6px}'
            u'p{color:#8b949e;max-width:70em}</style>'
            u'<h1>Bougies rep&egrave;res &mdash; %s</h1>'
            u'<p>La <b>largeur</b> de chaque bougie est proportionnelle '
            u'&agrave; son nombre de <b>trades</b>, pas &agrave; une '
            u'dur&eacute;e : c\'est l\'id&eacute;e des chandeliers '
            u'proportionnels aux ordres. Les bougies cercl&eacute;es '
            u'd&eacute;passent le centile %.1f de leur s&eacute;ance sur '
            u'au moins une des six dimensions. Survolez une bougie pour '
            u'ses chiffres.</p><p>Ceci d&eacute;crit, ne mesure pas : '
            u'aucune p-value, aucun t&eacute;moin.</p>%s'
            % (jour, jour, cent, "".join(blocs)))
    if not os.path.isdir(SORTIE):
        os.makedirs(SORTIE)
    che = os.path.join(SORTIE, "bougies_reperes_%s.html" % jour)
    io.open(che, "w", encoding="utf-8").write(html)
    print("  ecrit : %s (%d octets)" % (che, len(html.encode("utf-8"))))
    print()


if __name__ == "__main__":
    sys.exit(main())

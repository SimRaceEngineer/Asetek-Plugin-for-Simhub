#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""tp_fixe.py -- ce qu un take-profit fixe aurait donne. Exactement.

POURQUOI CELLE-CI N EST PAS UNE BORNE
-------------------------------------
Un break-even et un trailing dependent de l ORDRE dans lequel le prix
a touche deux niveaux. Le journal ne garde que les deux extremes, pas
leur chronologie : ces deux mecanismes ne se simulent donc que barre
par barre.

Un take-profit, non. Il ne touche PAS le cote perte -- le stop reste
ou il est -- et il est rempli si et seulement si le prix a atteint le
niveau. Or le MFE d un trade est son plus haut, et un plus haut
survient forcement AVANT la fin du trade. Donc :

    TP a k.R rempli  <=>  MFE >= k.R

sans aucune ambiguite, y compris sur les perdants : un perdant dont le
MFE depasse k.R serait sorti en GAIN avant d aller mourir.

Ce panneau ne simule donc rien. Il recalcule.

CE QU IL COMPTE, ET DANS LES TROIS SENS
---------------------------------------
    RELEVE   gagnant dont le pic depassait k.R mais qui a fini
             en dessous : il remonte a k.R. C est le gisement.
    RABOTE   gagnant qui finissait AU-DESSUS de k.R : il redescend
             a k.R. C est le cout, et il est reel.
    RETOURNE perdant dont le pic depassait k.R : il change de signe.
             Le plus gros effet unitaire, le plus rare.

Un panneau qui ne compterait que les releves mentirait par omission.

R -- CE QUE C EST, ET CE QUE CE N EST PAS
-----------------------------------------
R est la PERTE MOYENNE REALISEE du magic, pas une distance de stop.
Sur ce jeu de donnees les stops etaient les placeholders larges (200
points sur US500, 1600 sur US100) : la perte moyenne reflete donc ou
les sorties ont REELLEMENT atterri, pas ou le stop etait pose. C est
la bonne reference pour un TP -- on veut un multiple du risque
effectivement pris -- mais ca veut dire que si les sorties changent,
R change, et la grille doit etre relue.

CE QU IL SOUS-ESTIME
--------------------
Le controle d unite de mfe_partage.py a montre que 12 % des gagnants
portent un MFE inferieur a leur propre gain -- vraisemblablement une
granularite de bougie. Un MFE sous-estime fait MANQUER des TP qui
auraient ete touches. Ce panneau est donc un MINORANT du gain, pas un
majorant.

CE QU IL NE MODELISE PAS
------------------------
Un trade ferme plus tot libere une place. Le moteur churn en aurait
peut-etre pris un autre. Ce panneau garde la population telle quelle.

OU IL ECRIT
-----------
    panels\panel_tp_fixe.txt
    cartes\tp_fixe.html              visible dans la liste /cartes

LECTURE SEULE. N importe pas MetaTrader5, n envoie aucun ordre.

USAGE
-----
    python tp_fixe.py
    python tp_fixe.py --seuils 1.0,1.2,1.4,2.0
    python tp_fixe.py --min-n 30
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

JOURNAL = os.path.join("docs", "papers_live", "trades.jsonl")
SORTIE_T = os.path.join("panels", "panel_tp_fixe.txt")
SORTIE_H = os.path.join("cartes", "tp_fixe.html")

LARGE = 118
GRILLE = (1.0, 1.2, 1.3, 1.4, 1.6, 2.0, 2.5)


def lire_jsonl(chemin):
    out, ko = [], 0
    if not os.path.isfile(chemin):
        return out, ko
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for l in f:
            l = l.strip()
            if not l:
                continue
            try:
                o = json.loads(l)
            except ValueError:
                ko += 1
                continue
            if isinstance(o, dict):
                out.append(o)
    return out, ko


def noms_des_papers():
    try:
        import papers_moteur as PM
        pe, pr, manque = PM._charge_modules()
        if manque:
            return {}, "modules absents : %s" % ", ".join(manque)
        return dict((j[0], j[1]) for j in PM.papers(pe, pr)), ""
    except Exception as e:
        return {}, str(e)[:120]


def famille(magic):
    m = int(magic or 0)
    if 220000 <= m < 230000:
        return "220xxx"
    if 230000 <= m < 240000:
        return "DS 23xxxx"
    if 240000 <= m < 250000:
        return "MR 24xxxx"
    return "autres"


# ----------------------------------------------------------------------
# le recalcul
# ----------------------------------------------------------------------
def reference(prises):
    """R, et l etat actuel. R vient des PERTES REELLES, pas d un stop."""
    g = [p for p in prises if (p.get("pnl") or 0.0) > 0]
    d = [p for p in prises if (p.get("pnl") or 0.0) < 0]
    n = len(g) + len(d)
    if not n or not d:
        return None
    R = sum(-p["pnl"] for p in d) / float(len(d))
    tot = sum(p["pnl"] for p in g + d)
    return {"n": n, "ng": len(g), "nd": len(d), "R": R, "tot": tot,
            "moy": tot / n, "wr": 100.0 * len(g) / n,
            "prises": g + d}


def au_seuil(ref, k):
    """Le resultat exact d un TP a k.R, et le detail des trois effets."""
    cible = k * ref["R"]
    tot, nk = 0.0, 0
    releve = rabote = retourne = 0
    g_releve = g_retourne = c_rabote = 0.0

    for p in ref["prises"]:
        pnl = p["pnl"]
        mfe = abs(p.get("mfe") or 0.0)
        if mfe >= cible:
            neuf = cible
            if pnl <= 0:
                retourne += 1
                g_retourne += neuf - pnl
            elif pnl < cible:
                releve += 1
                g_releve += neuf - pnl
            else:
                rabote += 1
                c_rabote += pnl - neuf
        else:
            neuf = pnl
        tot += neuf
        if neuf > 0:
            nk += 1

    return {"k": k, "cible": cible, "tot": tot,
            "delta": tot - ref["tot"],
            "moy": tot / ref["n"], "wr": 100.0 * nk / ref["n"],
            "releve": releve, "rabote": rabote, "retourne": retourne,
            "g_releve": g_releve, "g_retourne": g_retourne,
            "c_rabote": c_rabote}


# ----------------------------------------------------------------------
def barre(c="="):
    return c * LARGE


def rendu(journal, noms, souci, min_n, grille, chemin):
    L = []
    a = L.append

    par = {}
    for x in journal:
        par.setdefault(x.get("magic"), []).append(x)

    a(barre())
    a("TAKE-PROFIT FIXE -- RECALCUL EXACT, PAS UNE SIMULATION")
    a(barre())
    a("  source : %s   (%d prise(s))" % (chemin, len(journal)))
    if souci:
        a("  noms   : indisponibles (%s), magics seuls." % souci)
    a("")
    a("  Un TP a k.R est rempli si et seulement si le MFE atteint k.R :")
    a("  le plus haut d un trade survient forcement avant sa fin. Le")
    a("  cote perte n est PAS touche -- le stop reste ou il est.")
    a("")
    a("  R = la PERTE MOYENNE REALISEE du magic, pas une distance de")
    a("  stop. Elle dit ou les sorties ont atterri, pas ou le stop")
    a("  etait pose. Si les sorties changent, R change.")
    a("")

    # ---------------- table des ecarts
    a(barre("-"))
    e = "%-7s %-24s %6s %9s" % ("MAGIC", "PAPER", "n", "PnL reel")
    for k in grille:
        e += " %8s" % ("%.1fR" % k)
    a(e)
    a(barre("-"))

    lignes = []
    for magic, prises in par.items():
        ref = reference(prises)
        if ref and ref["n"] >= min_n:
            lignes.append((magic, ref,
                           [au_seuil(ref, k) for k in grille]))
    lignes.sort(key=lambda t: -t[1]["n"])

    for magic, ref, res in lignes:
        best = max(res, key=lambda r: r["delta"])
        ln = "%-7s %-24s %6d %+9.0f" % (magic, (noms.get(magic) or "")[:24],
                                        ref["n"], ref["tot"])
        for r in res:
            mk = "*" if r is best and r["delta"] > 0 else " "
            ln += " %+7.0f%s" % (r["delta"], mk)
        a(ln)

    a(barre("-"))
    fam = {}
    for x in journal:
        fam.setdefault(famille(x.get("magic")), []).append(x)
    for nom in ("220xxx", "DS 23xxxx", "MR 24xxxx", "autres"):
        ref = reference(fam.get(nom, []))
        if ref and ref["n"] >= min_n:
            res = [au_seuil(ref, k) for k in grille]
            best = max(res, key=lambda r: r["delta"])
            ln = "%-7s %-24s %6d %+9.0f" % ("", nom, ref["n"], ref["tot"])
            for r in res:
                mk = "*" if r is best and r["delta"] > 0 else " "
                ln += " %+7.0f%s" % (r["delta"], mk)
            a(ln)
    a(barre("-"))
    a("  Ecart de PnL total en EUR contre la sortie actuelle.")
    a("  L etoile marque le meilleur seuil de la ligne, s il est positif.")
    a("  R est propre a chaque ligne : les colonnes ne sont pas des")
    a("  niveaux de prix communs, ce sont des multiples du risque local.")
    a("")

    # ---------------- le detail des trois effets
    a(barre())
    a("LE DETAIL -- CE QUI EST RELEVE, CE QUI EST RABOTE, CE QUI RETOURNE")
    a(barre())
    a("  RELEVE   gagnant dont le pic depassait le TP mais qui a fini")
    a("           en dessous : il remonte au TP. Le gisement.")
    a("  RABOTE   gagnant qui finissait AU-DESSUS du TP : il redescend.")
    a("           Le cout, et il est reel.")
    a("  RETOURNE perdant dont le pic depassait le TP : il change de")
    a("           signe. Le plus gros effet unitaire, le plus rare.")
    a("")
    a(barre("-"))
    a("%-7s %-20s %5s %6s %7s %8s %6s %8s %6s %8s %8s"
      % ("MAGIC", "PAPER", "TP", "releve", "gain", "rabote", "cout",
         "retour", "gain", "NET", "WR"))
    a(barre("-"))
    for magic, ref, res in lignes:
        best = max(res, key=lambda r: r["delta"])
        a("%-7s %-20s %4.1fR %6d %+7.0f %8d %+6.0f %8d %+6.0f %+8.0f %5.0f%%"
          % (magic, (noms.get(magic) or "")[:20], best["k"],
             best["releve"], best["g_releve"],
             best["rabote"], -best["c_rabote"],
             best["retourne"], best["g_retourne"],
             best["delta"], best["wr"]))
    a(barre("-"))
    a("  Ligne calculee au MEILLEUR seuil de chaque magic. Choisir le")
    a("  meilleur seuil APRES avoir vu le tableau est du surajustement :")
    a("  cette ligne montre la mecanique, elle ne prescrit pas un reglage.")
    a("")

    # ---------------- ce que ca ne dit pas
    a(barre())
    a("CE QUE CE PANNEAU NE DIT PAS")
    a(barre())
    a("  Il MINORE le gain. 12 % des gagnants portent un MFE inferieur")
    a("  a leur propre gain -- une granularite de bougie. Un MFE")
    a("  sous-estime fait manquer des TP qui auraient ete touches.")
    a("")
    a("  Il ne modelise pas la place liberee : un trade ferme plus tot")
    a("  aurait peut-etre laisse le moteur en prendre un autre.")
    a("")
    a("  Il ne dit rien du break-even ni du trailing. Ces deux-la")
    a("  dependent de l ORDRE dans lequel le prix touche deux niveaux,")
    a("  que le journal ne garde pas. Seul le rejeu barre par barre.")
    a("")
    a("  Le meilleur seuil d une ligne a faible effectif n est pas un")
    a("  reglage, c est un tirage. Regarder n avant le NET.")
    return "\n".join(L)


def page_html(txt):
    h = (txt.replace("&", "&amp;").replace("<", "&lt;")
         .replace(">", "&gt;"))
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<title>TP fixe</title></head>'
            '<body style="margin:0;background:#0e1116">'
            '<pre style="font:12px Consolas,monospace;color:#c9d1d9;'
            'background:#0e1116;padding:16px 20px;margin:0;'
            'white-space:pre">' + h + '</pre></body></html>\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--journal", default=JOURNAL)
    ap.add_argument("--min-n", type=int, default=10, dest="min_n")
    ap.add_argument("--seuils", default="",
                    help="ex : 1.0,1.2,1.4,2.0 -- defaut %s"
                         % ",".join("%.1f" % k for k in GRILLE))
    a = ap.parse_args()

    grille = GRILLE
    if a.seuils.strip():
        try:
            grille = tuple(sorted(float(x) for x in a.seuils.split(",") if x))
        except ValueError:
            print("ABANDON : --seuils illisible.")
            return 2
        if not grille:
            print("ABANDON : --seuils vide.")
            return 2

    journal, ko = lire_jsonl(a.journal)
    if not journal:
        print("ABANDON : %s vide ou absent." % a.journal)
        return 2
    if ko:
        print("  %d ligne(s) illisible(s), ignoree(s)." % ko)

    noms, souci = noms_des_papers()
    txt = rendu(journal, noms, souci, a.min_n, grille, a.journal)
    print(txt)

    for d in ("panels", "cartes"):
        if not os.path.isdir(d):
            os.makedirs(d)
    io.open(SORTIE_T, "w", encoding="utf-8", newline="").write(txt + "\n")
    io.open(SORTIE_H, "w", encoding="utf-8", newline="").write(page_html(txt))
    print("")
    print("  ecrit : %s" % SORTIE_T)
    print("  ecrit : %s   (liste /cartes)" % SORTIE_H)
    return 0


if __name__ == "__main__":
    sys.exit(main())

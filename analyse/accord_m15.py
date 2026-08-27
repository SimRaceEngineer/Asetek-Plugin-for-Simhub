#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""accord_m15.py -- les deux jumeaux, jour par jour, et le R en points.

DEUX QUESTIONS, UN SEUL OUTIL
-----------------------------
1. LES JUMEAUX S INVERSENT-ILS ?
   240003 ACCORD M15 HAUSSIER a perdu 3 779 sur le mois, 240004 ACCORD
   M15 BAISSIER en a gagne 4 794. Deux lectures s affrontent :

     - le haussier est une mauvaise regle, il faut le couper ;
     - le mois etait oriente a la baisse, et les deux s inverseront.

   Elles se departagent en decoupant PAR JOURNEE. Si les deux gagnent
   et perdent en alternance, c est le regime de marche. S ils perdent
   les MEMES jours, c est la sortie, et l inversion est une illusion.

   Ce panneau ne tranche pas a la place des donnees : il donne le
   compte des jours en desaccord, la correlation des PnL quotidiens,
   et il rappelle qu un mois d un seul regime ne prouve rien dans un
   sens comme dans l autre.

2. COMBIEN VAUT R, EN POINTS ?
   Tout le R des trois etudes est en EUROS -- la perte moyenne
   realisee du magic. Pour poser un trailing en LIVE il faut un nombre
   de POINTS, par actif. Et il ne peut pas venir du stop d origine :
   c est le placeholder a 200 points sur US500, dont la moitie ferait
   un trailing qui ne se declencherait jamais.

   On le mesure donc : pour chaque prise, R_euros divise par les euros
   par point de cette prise. La mediane par actif est le chiffre a
   poser dans le miroir 6.

CE QU IL NE FAIT PAS
--------------------
Il n envoie aucun ordre. Il importe MetaTrader5 pour LIRE l historique,
et il vise explicitement le terminal du MOTEUR. La partie jour par
jour n a besoin de rien : si MT5 manque, elle sort quand meme.

Il reutilise les fonctions de rejoue_sorties.py au lieu de les
recopier -- une correction faite la vaut ici.

OU IL ECRIT
-----------
    panels\panel_accord_m15.txt
    cartes\accord_m15.html           visible dans la liste /cartes

USAGE
-----
    python accord_m15.py
    python accord_m15.py --magics 240003,240004
    python accord_m15.py --sans-mt5
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import time

JOURNAL = os.path.join("docs", "papers_live", "trades.jsonl")
SORTIE_T = os.path.join("panels", "panel_accord_m15.txt")
SORTIE_H = os.path.join("cartes", "accord_m15.html")
LARGE = 118


def barre(c="="):
    return c * LARGE


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


def correlation(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def mediane(v):
    if not v:
        return None
    w = sorted(v)
    n = len(w)
    return w[n // 2] if n % 2 else 0.5 * (w[n // 2 - 1] + w[n // 2])


def quartile(v, q):
    if not v:
        return None
    w = sorted(v)
    i = int(q * (len(w) - 1))
    return w[i]


# ----------------------------------------------------------------------
# 1. jour par jour
# ----------------------------------------------------------------------
def jour_par_jour(dire, journal, a_, b_, noms):
    par = {}
    for x in journal:
        m = x.get("magic")
        if m not in (a_, b_):
            continue
        j = str(x.get("ts") or "")[:10]
        if not j:
            continue
        d = par.setdefault(j, {a_: [0, 0.0], b_: [0, 0.0]})
        d[m][0] += 1
        d[m][1] += x.get("pnl") or 0.0

    dire(barre())
    dire("LES DEUX JUMEAUX, JOUR PAR JOUR")
    dire(barre())
    dire("  %-7s %s" % (a_, noms.get(a_, "")))
    dire("  %-7s %s" % (b_, noms.get(b_, "")))
    dire("")
    dire("  S ils gagnent et perdent EN ALTERNANCE, c est le regime de")
    dire("  marche qui commande, et les couper serait vendre celui des")
    dire("  deux qui gagnera au retournement.")
    dire("  S ils perdent les MEMES jours, c est la sortie, et l")
    dire("  inversion est une illusion.")
    dire("")
    dire(barre("-"))
    dire("%-12s %6s %10s   %6s %10s   %8s" %
         ("JOUR", "n", "haussier", "n", "baissier", "accord"))
    dire(barre("-"))

    xs, ys = [], []
    memes = contraires = 0
    for j in sorted(par):
        d = par[j]
        na, pa = d[a_]
        nb, pb = d[b_]
        if na == 0 and nb == 0:
            continue
        marque = ""
        if na and nb:
            xs.append(pa)
            ys.append(pb)
            if (pa > 0) == (pb > 0):
                memes += 1
                marque = "meme"
            else:
                contraires += 1
                marque = "OPPOSE"
        dire("%-12s %6d %+10.0f   %6d %+10.0f   %8s"
             % (j, na, pa, nb, pb, marque))
    dire(barre("-"))
    tot_a = sum(par[j][a_][1] for j in par)
    tot_b = sum(par[j][b_][1] for j in par)
    dire("%-12s %6d %+10.0f   %6d %+10.0f"
         % ("TOTAL", sum(par[j][a_][0] for j in par), tot_a,
            sum(par[j][b_][0] for j in par), tot_b))
    dire(barre("-"))
    dire("")

    n = memes + contraires
    dire("  jours ou les deux ont trade : %d" % n)
    if n:
        dire("    meme signe    : %d  (%.0f %%)" % (memes, 100.0 * memes / n))
        dire("    signes opposes: %d  (%.0f %%)"
             % (contraires, 100.0 * contraires / n))
    r = correlation(xs, ys)
    if r is None:
        dire("  correlation des PnL quotidiens : incalculable (trop peu de jours)")
    else:
        dire("  correlation des PnL quotidiens : %+.2f" % r)
        dire("")
        if r < -0.3:
            dire("  NEGATIVE et marquee : les deux s opposent jour apres")
            dire("  jour. C est la signature d un effet de REGIME, et")
            dire("  couper le haussier reviendrait a vendre l assurance")
            dire("  contre le retournement.")
        elif r > 0.3:
            dire("  POSITIVE : ils gagnent et perdent ENSEMBLE. Ce n est")
            dire("  donc pas le sens du marche qui les separe -- l ecart")
            dire("  de resultat vient d ailleurs, et tres probablement de")
            dire("  la sortie.")
        else:
            dire("  PROCHE DE ZERO : ils sont independants. Ni regime")
            dire("  commun, ni opposition. L hypothese de l inversion n")
            dire("  est ni confirmee ni refutee par ce mois-ci.")
    dire("")
    dire("  RESERVE : un mois d un seul regime ne peut pas prouver une")
    dire("  inversion. Une correlation negative rend l hypothese")
    dire("  PLAUSIBLE ; seule une periode haussiere la trancherait.")


# ----------------------------------------------------------------------
# 2. R en points
# ----------------------------------------------------------------------
def r_en_points(dire, journal, magics, terminal, noms):
    try:
        import rejoue_sorties as RS
    except Exception as e:
        dire("  R en points : rejoue_sorties.py introuvable (%s)." % str(e)[:60])
        return
    for f in ("deals_fenetre", "resume_position"):
        if not hasattr(RS, f):
            dire("  R en points : rejoue_sorties.py n a pas %s()." % f)
            return
    if not os.path.exists(terminal):
        dire("  R en points : terminal introuvable, mesure impossible.")
        dire("    %s" % terminal)
        return
    try:
        import MetaTrader5 as mt5
    except ImportError:
        dire("  R en points : MetaTrader5 non installe.")
        return
    if not mt5.initialize(path=terminal):
        dire("  R en points : initialize a echoue -- %s" % (mt5.last_error(),))
        return

    t1 = time.time()
    t0 = t1 - 86400.0 * 40
    par_pos = RS.deals_fenetre(mt5, t0, t1, dire)

    R_eur = {}
    for m in magics:
        pertes = [-x["pnl"] for x in journal
                  if x.get("magic") == m and (x.get("pnl") or 0.0) < 0]
        R_eur[m] = (sum(pertes) / len(pertes)) if pertes else None

    pts = {}        # (magic, symbole) -> [r_pts]
    manque = 0
    for x in journal:
        m = x.get("magic")
        if m not in magics or not R_eur.get(m):
            continue
        tk = x.get("ticket")
        d = par_pos.get(int(tk)) if tk is not None else None
        if not d:
            manque += 1
            continue
        r = RS.resume_position(mt5, d)
        if not r:
            manque += 1
            continue
        sens, entree, sortie, profit, t_ouv, t_fer, sym = r
        amp = (sortie - entree) * sens
        if abs(amp) < 1e-9 or abs(profit) < 1e-9:
            manque += 1
            continue
        ep = (x["pnl"] / profit) * (profit / amp)       # euros par point
        if abs(ep) < 1e-12:
            manque += 1
            continue
        pts.setdefault((m, sym), []).append(R_eur[m] / abs(ep))
    mt5.shutdown()

    dire("")
    dire(barre())
    dire("R EN POINTS -- le chiffre qui manque au miroir 6")
    dire(barre())
    dire("  R est la perte moyenne REALISEE du magic, en euros. Ici on")
    dire("  la convertit en points, prise par prise, et on prend la")
    dire("  mediane. C est la distance a poser dans un trailing live.")
    dire("")
    dire("  Elle ne vient PAS du stop d origine : celui-ci est le")
    dire("  placeholder a 200 points sur US500, dont la moitie ferait un")
    dire("  trailing qui ne se declencherait jamais.")
    dire("")
    dire(barre("-"))
    dire("%-7s %-22s %-8s %7s %9s %9s %9s %11s"
         % ("MAGIC", "PAPER", "ACTIF", "n", "R q25", "R median", "R q75",
            "0.5R points"))
    dire(barre("-"))
    for (m, sym) in sorted(pts):
        v = pts[(m, sym)]
        md = mediane(v)
        dire("%-7s %-22s %-8s %7d %9.1f %9.1f %9.1f %11.1f"
             % (m, (noms.get(m) or "")[:22], sym, len(v),
                quartile(v, 0.25), md, quartile(v, 0.75), md / 2.0))
    dire(barre("-"))
    if manque:
        dire("  %d prise(s) sans position retrouvee, ignoree(s)." % manque)
    dire("  q25 et q75 encadrent la dispersion : si elles sont loin l une")
    dire("  de l autre, une distance unique par actif est deja une")
    dire("  approximation, et il faut le savoir avant de la poser.")


# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--journal", default=JOURNAL)
    ap.add_argument("--magics", default="240003,240004")
    ap.add_argument("--terminal", default="")
    ap.add_argument("--sans-mt5", action="store_true", dest="sans_mt5")
    a = ap.parse_args()

    L = []

    def dire(msg):
        print(msg, flush=True)
        L.append(msg)

    try:
        magics = [int(x) for x in a.magics.split(",") if x.strip()]
    except ValueError:
        print("ABANDON : --magics illisible.")
        return 2
    if len(magics) != 2:
        print("ABANDON : il faut exactement deux magics, les deux jumeaux.")
        return 2

    journal, ko = lire_jsonl(a.journal)
    if not journal:
        print("ABANDON : %s vide ou absent." % a.journal)
        return 2

    noms = {}
    try:
        import papers_moteur as PM
        pe, pr, manque = PM._charge_modules()
        if not manque:
            noms = dict((j[0], j[1]) for j in PM.papers(pe, pr))
    except Exception:
        pass

    jour_par_jour(dire, journal, magics[0], magics[1], noms)

    if not a.sans_mt5:
        term = a.terminal
        if not term:
            try:
                import rejoue_sorties as RS
                term = RS.TERMINAL_MOTEUR
            except Exception:
                term = ""
        if term:
            r_en_points(dire, journal, magics, term, noms)
        else:
            dire("")
            dire("  R en points : pas de chemin de terminal, mesure sautee.")

    txt = "\n".join(L)
    for d in ("panels", "cartes"):
        if not os.path.isdir(d):
            os.makedirs(d)
    io.open(SORTIE_T, "w", encoding="utf-8", newline="").write(txt + "\n")
    h = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    io.open(SORTIE_H, "w", encoding="utf-8", newline="").write(
        '<!doctype html><html><head><meta charset="utf-8">'
        '<title>Accord M15</title></head>'
        '<body style="margin:0;background:#0e1116">'
        '<pre style="font:12px Consolas,monospace;color:#c9d1d9;'
        'background:#0e1116;padding:16px 20px;margin:0;'
        'white-space:pre">' + h + '</pre></body></html>\n')
    print("")
    print("  ecrit : %s" % SORTIE_T)
    print("  ecrit : %s   (liste /cartes)" % SORTIE_H)
    return 0


if __name__ == "__main__":
    sys.exit(main())

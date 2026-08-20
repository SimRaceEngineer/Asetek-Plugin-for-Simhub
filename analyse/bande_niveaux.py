#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bande_niveaux.py -- qu y a-t-il dans une bande de prix, dans NOS donnees ?

LECTEUR SEUL. N ECRIT RIEN.

  python bande_niveaux.py --actif US30 --bas 53596 --haut 53705

Ce qu il repond :
  1. combien de trades sont ENTRES dans la bande, leur sens, leur PnL,
     leur MFE et leur MAE ;
  2. quels niveaux epoch (L, cible, start_price) y tombent, sur quelle
     unite de temps, avec leur nombre de retests ;
  3. et surtout : est-ce que la bande est PARTICULIERE, ou est-ce
     simplement la ou le prix a passe du temps ? La reponse vient de
     la comparaison avec les bandes voisines de meme largeur. Sans
     elle, une zone dense ne prouve rien.

CE QU IL NE PEUT PAS DIRE

  Il n y a AUCUN volume reel sur US30 dans cette stack : les CFD ne
  portent qu un compteur de ticks. Ce script ne fait donc pas de
  l orderflow -- il dit ce que la stack a vu et fait dans la bande.
  Le seul volume reel disponible est celui du .scid, et il porte
  sur le S&P, pas sur le Dow.
"""

import argparse
import gzip
import io
import json
import os
import sys

SEP = "=" * 92
DEFAUT = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")


def ouvre(chemin):
    """Ouvre en clair ou en .gz -- la rotation comprime les anciens."""
    if chemin.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(chemin, "rb"),
                                encoding="utf-8", errors="replace")
    return io.open(chemin, encoding="utf-8", errors="replace")


def fichiers(base):
    """Le fichier, plus ses versions comprimees si elles existent."""
    trouves = []
    for c in (base, base + ".gz"):
        if os.path.isfile(c):
            trouves.append(c)
    dossier = os.path.dirname(base) or "."
    racine = os.path.basename(base)
    if os.path.isdir(dossier):
        for f in sorted(os.listdir(dossier)):
            p = os.path.join(dossier, f)
            if p in trouves or not os.path.isfile(p):
                continue
            if f.startswith(racine) and (f.endswith(".gz") or f.endswith(".jsonl")):
                trouves.append(p)
    return trouves


def lit(base):
    tickets, ko = [], 0
    for chemin in fichiers(base):
        try:
            with ouvre(chemin) as f:
                for ligne in f:
                    ligne = ligne.strip()
                    if not ligne:
                        continue
                    try:
                        o = json.loads(ligne)
                    except ValueError:
                        ko += 1
                        continue
                    if isinstance(o, dict):
                        tickets.append(o)
        except Exception as e:
            print("  illisible : %s (%s)" % (chemin, e))
    return tickets, ko


def nombre(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


def mediane(v):
    if not v:
        return None
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=DEFAUT)
    p.add_argument("--actif", default="US30")
    p.add_argument("--bas", type=float, required=True)
    p.add_argument("--haut", type=float, required=True)
    p.add_argument("--voisines", type=int, default=4,
                   help="bandes de meme largeur comparees de chaque cote")
    a = p.parse_args()
    bas, haut = min(a.bas, a.haut), max(a.bas, a.haut)
    largeur = haut - bas

    print(SEP)
    print("BANDE %s  %.1f - %.1f  (%.1f points)" % (a.actif, bas, haut, largeur))
    print(SEP)
    print()
    print("  Lecture seule. Aucun volume reel sur cet actif : ce n est")
    print("  pas de l orderflow, c est ce que la stack a vu et fait.")
    print()

    tickets, ko = lit(a.fichier)
    if not tickets:
        print("  aucun ticket lu depuis %s" % a.fichier)
        return
    ntotal = len(tickets)
    tickets = [t for t in tickets if t.get("asset") == a.actif]
    print("  %d ticket(s) au total, %d sur %s%s"
          % (ntotal, len(tickets), a.actif,
             (", %d ligne(s) illisible(s)" % ko) if ko else ""))
    jours = sorted(set((t.get("entry_ts") or "")[:10] for t in tickets if t.get("entry_ts")))
    if jours:
        print("  du %s au %s (%d jour(s))" % (jours[0], jours[-1], len(jours)))
    print()

    # ---------------------------------------------------------------- 1
    print(SEP)
    print("1. LES TRADES ENTRES DANS LA BANDE")
    print(SEP)
    print()
    dedans = []
    for t in tickets:
        pr = nombre(t.get("entry_price"))
        if pr is not None and bas <= pr <= haut:
            dedans.append(t)
    if not dedans:
        print("  aucun trade n est entre dans cette bande.")
    else:
        for sens in ("BUY", "SELL"):
            lot = [t for t in dedans if t.get("dir") == sens]
            if not lot:
                continue
            pnl = [nombre(t.get("pnl_eur")) or 0.0 for t in lot]
            gagnants = sum(1 for x in pnl if x > 0)
            mfe = [nombre(t.get("mfe_pts")) for t in lot]
            mae = [nombre(t.get("mae_pts")) for t in lot]
            mfe = [x for x in mfe if x is not None]
            mae = [x for x in mae if x is not None]
            print("  %-5s %4d trade(s)   gagnants %3d (%.0f %%)   "
                  "PnL %9.2f EUR" % (sens, len(lot), gagnants,
                                     100.0 * gagnants / len(lot), sum(pnl)))
            print("        MFE median %7s pts     MAE median %7s pts"
                  % (("%.1f" % mediane(mfe)) if mfe else "-",
                     ("%.1f" % mediane(mae)) if mae else "-"))
        print()
        magics = {}
        for t in dedans:
            magics[t.get("magic")] = magics.get(t.get("magic"), 0) + 1
        haut5 = sorted(magics.items(), key=lambda kv: -kv[1])[:6]
        print("  magics les plus actifs dedans : %s"
              % ", ".join("M%s (%d)" % (m, n) for m, n in haut5))
    print()

    # ---------------------------------------------------------------- 2
    print(SEP)
    print("2. LES NIVEAUX EPOCH QUI TOMBENT DANS LA BANDE")
    print(SEP)
    print()
    compte = {}
    exemples = {}
    for t in tickets:
        ep = t.get("epoch_entry")
        if not isinstance(ep, dict):
            continue
        for tf, d in ep.items():
            if not isinstance(d, dict):
                continue
            for cle in ("L", "cible", "start_price"):
                v = nombre(d.get(cle))
                if v is None or not (bas <= v <= haut):
                    continue
                k = (tf, cle)
                compte[k] = compte.get(k, 0) + 1
                if k not in exemples:
                    exemples[k] = (v, d.get("retests"), d.get("hh_count"),
                                   d.get("event"), t.get("entry_ts"))
    if not compte:
        print("  aucun niveau epoch dans la bande.")
    else:
        print("    unite  champ         vus   exemple      retests  hh  evenement")
        print("    " + "-" * 80)
        for (tf, cle) in sorted(compte, key=lambda k: -compte[k]):
            v, ret, hh, ev, ts = exemples[(tf, cle)]
            print("    %-6s %-12s %5d   %9.1f  %7s %3s  %s"
                  % (tf, cle, compte[(tf, cle)], v, ret, hh, ev))
    print()

    # ---------------------------------------------------------------- 3
    print(SEP)
    print("3. LA BANDE EST-ELLE PARTICULIERE ?")
    print(SEP)
    print()
    print("  Bandes de meme largeur, de part et d autre. Une bande dense")
    print("  entouree de bandes denses ne prouve rien : c est juste la")
    print("  ou le prix a passe du temps.")
    print()
    print("      bande                       trades   niveaux epoch")
    print("      " + "-" * 60)
    for k in range(-a.voisines, a.voisines + 1):
        b = bas + k * largeur
        h = haut + k * largeur
        nt = sum(1 for t in tickets
                 if (nombre(t.get("entry_price")) or -1) >= b
                 and (nombre(t.get("entry_price")) or -1) <= h)
        nn = 0
        for t in tickets:
            ep = t.get("epoch_entry")
            if not isinstance(ep, dict):
                continue
            for _tf, d in ep.items():
                if not isinstance(d, dict):
                    continue
                for cle in ("L", "cible", "start_price"):
                    v = nombre(d.get(cle))
                    if v is not None and b <= v <= h:
                        nn += 1
        marque = "  <== la bande demandee" if k == 0 else ""
        print("      %9.1f - %9.1f      %6d   %8d%s" % (b, h, nt, nn, marque))
    print()

    print(SEP)
    print("  Rien n a ete ecrit, rien n a ete envoye.")
    print(SEP)


if __name__ == "__main__":
    main()

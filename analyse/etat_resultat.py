#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etat_resultat.py -- un etat change-t-il le RESULTAT, et tient-il en deux ?

LECTEUR SEUL. N ECRIT RIEN.

  python etat_resultat.py
  python etat_resultat.py --actif US30 --mini 40
  python etat_resultat.py --sortie mfe_pts

LA QUESTION

    bande_colonnes disait ce qui differe DANS une bande de prix. Mais
    une bande de prix n est visitee qu a certaines periodes : ce qui y
    differe est inseparable de ce qui differait CE JOUR-LA. On ne
    savait donc pas si on regardait une zone ou une phase.

    Ici la question est autre, et elle est utile : cet etat, OU QU IL
    SE PRODUISE, change-t-il le resultat des trades ?

LA SEULE DISCIPLINE QUI VAILLE

    Chaque etat est evalue DEUX FOIS, sur la premiere moitie de la
    periode et sur la seconde, decoupees par date. Un etat n est
    retenu que si l ecart va DANS LE MEME SENS des deux cotes et
    reste substantiel dans les deux.

    C est un substitut a la pre-enregistration : je ne peux pas
    m empecher de voir les donnees, mais je peux exiger qu un effet
    survive a un decoupage qu il ne connait pas. Un etat qui ne
    marche que sur une moitie est du bruit, et il est ecarte SANS
    discussion -- meme s il est spectaculaire sur l ensemble.

    Le classement final est trie par le PLUS FAIBLE des deux ecarts.
    Un etat n est jamais meilleur que sa moitie la plus decevante.

CE QUE CA NE DIT TOUJOURS PAS

    Le PnL est celui du moteur churn, pas celui d une strategie qui
    entrerait sur cet etat. Un etat associe a de meilleurs trades
    n est pas une strategie : c est un filtre candidat. Et deux
    moities ne font pas une preuve -- elles eliminent les accidents
    les plus grossiers, rien de plus.
"""

import argparse
import gzip
import io
import json
import math
import os
import sys

SEP = "=" * 104
DEFAUT = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")


def ouvre(c):
    if c.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(c, "rb"), encoding="utf-8",
                               errors="replace")
    return io.open(c, encoding="utf-8", errors="replace")


def lit(base, actif):
    out = []
    for c in (base, base + ".gz"):
        if not os.path.isfile(c):
            continue
        with ouvre(c) as f:
            for l in f:
                l = l.strip()
                if not l:
                    continue
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                if isinstance(o, dict) and (not actif or o.get("asset") == actif):
                    out.append(o)
    return out


def aplatis(rec, actif):
    plat = {}

    def marche(prefixe, v):
        if isinstance(v, dict):
            for k, w in v.items():
                nk = "SELF" if (prefixe == "rails_entry" and k == actif) else k
                marche("%s.%s" % (prefixe, nk) if prefixe else nk, w)
        elif isinstance(v, list):
            plat[prefixe + ".n"] = len(v)
        else:
            plat[prefixe] = v

    for k, v in rec.items():
        marche(k, v)
    return plat


def mediane(v):
    if not v:
        return None
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def wilson_bas(succes, n, z=1.96):
    """Borne basse de Wilson : la part de gagnants qu on peut defendre."""
    if n == 0:
        return 0.0
    p = succes / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    e = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - e) / d


def juge(lot, sortie):
    """(n, part de gagnants, borne basse de Wilson, mediane de sortie)."""
    vals = [t.get(sortie) for t in lot]
    vals = [v for v in vals if isinstance(v, (int, float))]
    if not vals:
        return 0, 0.0, 0.0, None
    gagnants = sum(1 for v in vals if v > 0)
    n = len(vals)
    return n, gagnants / float(n), wilson_bas(gagnants, n), mediane(vals)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=DEFAUT)
    p.add_argument("--actif", default="US30")
    p.add_argument("--sortie", default="pnl_eur",
                   choices=("pnl_eur", "mfe_pts", "mae_pts"))
    p.add_argument("--mini", type=int, default=30,
                   help="effectif minimum PAR MOITIE")
    p.add_argument("--tete", type=int, default=20)
    a = p.parse_args()

    print(SEP)
    print("UN ETAT CHANGE-T-IL LE RESULTAT ? -- et tient-il sur les deux moities ?")
    print(SEP)
    print()
    print("  Lecture seule. Rien n est ecrit, rien n est envoye.")
    print()

    tickets = lit(a.fichier, a.actif)
    tickets = [t for t in tickets
               if isinstance(t.get(a.sortie), (int, float))
               and isinstance(t.get("entry_ts"), str)]
    if len(tickets) < 4 * a.mini:
        print("  %d ticket(s) exploitables : trop peu." % len(tickets))
        return
    tickets.sort(key=lambda t: t["entry_ts"])
    coupe = len(tickets) // 2
    A, B = tickets[:coupe], tickets[coupe:]
    print("  %d ticket(s) %s, sortie jugee : %s"
          % (len(tickets), a.actif, a.sortie))
    print("  moitie 1 : %s -> %s  (%d)"
          % (A[0]["entry_ts"][:10], A[-1]["entry_ts"][:10], len(A)))
    print("  moitie 2 : %s -> %s  (%d)"
          % (B[0]["entry_ts"][:10], B[-1]["entry_ts"][:10], len(B)))
    print()

    for lot in (A, B):
        for t in lot:
            t["_plat"] = aplatis(t, a.actif)

    nA, pA, wA, mA = juge(A, a.sortie)
    nB, pB, wB, mB = juge(B, a.sortie)
    print("  reference, tous trades confondus :")
    print("    moitie 1 : %d trades, %.0f %% gagnants, median %s = %.2f"
          % (nA, 100 * pA, a.sortie, mA))
    print("    moitie 2 : %d trades, %.0f %% gagnants, median %s = %.2f"
          % (nB, 100 * pB, a.sortie, mB))
    print()

    # --- recense les etats candidats -------------------------------------
    candidats = {}
    for lot in (A, B):
        for t in lot:
            for col, v in t["_plat"].items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    continue
                if v is None:
                    continue
                candidats[(col, str(v))] = candidats.get((col, str(v)), 0) + 1

    resultats = []
    for (col, val), total in candidats.items():
        if total < 2 * a.mini:
            continue
        lotA = [t for t in A if str(t["_plat"].get(col)) == val]
        lotB = [t for t in B if str(t["_plat"].get(col)) == val]
        if len(lotA) < a.mini or len(lotB) < a.mini:
            continue
        n1, p1, w1, m1 = juge(lotA, a.sortie)
        n2, p2, w2, m2 = juge(lotB, a.sortie)
        if n1 < a.mini or n2 < a.mini:
            continue
        e1 = p1 - pA
        e2 = p2 - pB
        # L exigence : meme sens des deux cotes. Sinon, ecarte.
        if e1 * e2 <= 0:
            continue
        tenue = min(abs(e1), abs(e2)) * (1 if e1 > 0 else -1)
        resultats.append((abs(tenue), tenue, col, val, n1, p1, e1, n2, p2, e2,
                          m1, m2))

    if not resultats:
        print("  Aucun etat ne tient dans le meme sens sur les deux moities")
        print("  avec au moins %d trades de chaque cote." % a.mini)
        print("  C est un resultat, pas un echec : ca veut dire qu aucune")
        print("  des colonnes disponibles ne separe les resultats de facon")
        print("  reproductible sur cette periode.")
        return

    resultats.sort(reverse=True)
    print(SEP)
    print("LES ETATS QUI TIENNENT DANS LES DEUX MOITIES")
    print(SEP)
    print()
    print("  ecart = part de gagnants de l etat moins celle de sa moitie.")
    print("  Trie par le PLUS FAIBLE des deux ecarts : un etat ne vaut")
    print("  jamais mieux que sa moitie la plus decevante.")
    print()
    for (_abs, tenue, col, val, n1, p1, e1, n2, p2, e2, m1, m2) in resultats[:a.tete]:
        sens = "AMELIORE" if tenue > 0 else "DEGRADE "
        print("  %s  %s = %s" % (sens, col, val))
        print("      moitie 1 : n=%4d  %.0f %% gagnants (%+.0f pts)  median %.2f"
              % (n1, 100 * p1, 100 * e1, m1))
        print("      moitie 2 : n=%4d  %.0f %% gagnants (%+.0f pts)  median %.2f"
              % (n2, 100 * p2, 100 * e2, m2))
        print("      tenue    : %+.0f points dans le pire des deux"
              % (100 * tenue))
    print()

    print(SEP)
    print("CE QUE CA VAUT")
    print(SEP)
    print()
    print("  %d etat(s) examine(s), %d retenu(s)."
          % (len(candidats), len(resultats)))
    print()
    print("  Exiger le meme sens sur deux moities elimine les accidents")
    print("  les plus grossiers. Ca ne fait pas une preuve : avec assez")
    print("  d etats testes, certains passeront ce filtre par chance.")
    print()
    print("  Et le PnL est celui du moteur churn, pas d une strategie qui")
    print("  entrerait sur cet etat. Un etat associe a de meilleurs")
    print("  trades est un FILTRE candidat, pas une strategie.")
    print()
    print("  L etape suivante n est pas d en coder un : c est de le")
    print("  geler par ecrit, avec son sens et son seuil, et d attendre")
    print("  des trades qu il n a jamais vus.")
    print()
    print(SEP)
    print("  Rien n a ete ecrit, rien n a ete envoye.")
    print(SEP)


if __name__ == "__main__":
    main()

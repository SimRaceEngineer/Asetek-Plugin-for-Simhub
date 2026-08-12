# -*- coding: utf-8 -*-
"""
matin_seances.py -- le creneau 09h-11h saigne-t-il SEANCE par seance ?

  python matin_seances.py --fichier docs\\rails_trades\\tickets_rails.jsonl
  python matin_seances.py --heures 9 11 --bascule 2026-08-05

L OBJECTION A LAQUELLE CE SCRIPT REPOND

    Le panel rails post-05/08 donne, sur 09h-11h :

        TENDANCE  528 tickets  -5 193 EUR   -9.84 /ticket
        RANGE     360 tickets  -4 989 EUR  -13.86 /ticket

    Des N de 108 a 190 par cellule rassurent -- a tort. Six seances en
    tendance, cinq en range : deux mauvaises journees suffisent a
    fabriquer ces moyennes. Le ticket n est pas une unite independante,
    la seance l est davantage. C est le critere p_seance du gel V9, et il
    n a jamais ete applique a ce creneau.

CE QUE CE SCRIPT MESURE

    1. LE SIGNE, SEANCE PAR SEANCE. Sur n seances, combien finissent le
       creneau dans le rouge ? Test binomial exact contre 50/50. C est
       la question honnete : une regle d abstention doit gagner SOUVENT,
       pas seulement en moyenne.

    2. LA CONCENTRATION. Somme du creneau en retirant la pire seance,
       puis les deux pires. Si le total reste franchement negatif, l
       objection "deux mauvaises journees" tombe. Si il s effondre, elle
       tient, et c est ce script qui l aura montre.

    3. LE CONTREFACTUEL. P&L total avec et sans le creneau -- la seule
       facon de chiffrer ce que l abstention rapporterait.

CE QU IL NE FAIT PAS

    Il ne prouve aucune causalite et ne recommande rien. Un creneau
    perdant sur onze seances peut le rester par hasard ; le test dit
    seulement a quel point ce serait un hasard remarquable.

    Il ne touche a aucun fichier. Aucun appel MT5. Lecture seule.

IL LIT les memes rails_trades*.jsonl que oos_v9 et rails_trois, avec LA
MEME normalisation -- importee, jamais recopiee.
"""
import argparse
import io
import json
import math
import os
import sys

try:
    import oos_v9 as O
except ImportError:
    print("KO : oos_v9.py introuvable a cote de ce script.")
    print("Il porte la normalisation des champs rails. La recopier ici")
    print("donnerait des chiffres incomparables avec le reste de l etude.")
    sys.exit(1)

DEFAUT = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
BASCULE = "2026-08-05"
SEANCES_MINI = 8
LARG = 74


def charger(chemins):
    """jour / heure / pnl par ticket. Meme lecture que rails_trois."""
    par, brut = {}, 0
    for ch in chemins:
        if not os.path.isfile(ch):
            continue
        for l in io.open(ch, encoding="utf-8-sig"):
            l = l.strip()
            if not l or l[0] != "{":
                continue
            brut += 1
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ts = str(O._prem(o, O.CLEFS_TS) or "")
            pnl = O._nombre(O._prem(o, O.CLEFS_PNL))
            tk = O._prem(o, O.CLEFS_TICKET)
            if len(ts) < 16 or pnl is None or tk is None or tk in par:
                continue
            par[tk] = {"jour": ts[:10], "heure": int(ts[11:13]), "pnl": pnl,
                       "ticket": str(tk)}
    if not par:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        print("Verifie le chemin, ou lance  python oos_v9.py --champs")
        sys.exit(1)
    return list(par.values())


def binom_bilateral(k, n):
    """p exact du signe, contre 50/50. None si n = 0.

    Somme des probabilites au moins aussi extremes que l observe, des
    deux cotes. Pas d approximation normale : a n = 11, elle mentirait."""
    if n <= 0:
        return None
    pk = [math.comb(n, i) * 0.5 ** n for i in range(n + 1)]
    seuil = pk[k] * (1 + 1e-9)
    return min(1.0, sum(p for p in pk if p <= seuil))


def bloc(titre, seances):
    """seances : [(jour, pnl_creneau, n_tickets)] -- deja filtre."""
    print()
    print(titre)
    print("-" * LARG)
    if not seances:
        print("  aucune seance.")
        return None

    vals = sorted(s[1] for s in seances)
    n = len(seances)
    neg = sum(1 for s in seances if s[1] < 0)
    nul = sum(1 for s in seances if s[1] == 0)
    total = sum(s[1] for s in seances)
    tick = sum(s[2] for s in seances)

    for j, p, c in sorted(seances):
        print("  %s  %9.2f EUR  %4d tickets   %s"
              % (j, p, c, "rouge" if p < 0 else ("vert" if p > 0 else "nul")))

    print("-" * LARG)
    print("  %d seances, %d tickets, total %.2f EUR" % (n, tick, total))
    med = (vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2.0)
    print("  mediane par seance : %.2f EUR" % med)
    print("  seances rouges : %d / %d%s"
          % (neg, n, ("  (%d nulle(s) exclue(s) du test)" % nul) if nul else ""))

    nt = n - nul
    p = binom_bilateral(neg, nt)
    if p is None:
        print("  test du signe : impossible.")
    else:
        print("  test du signe (binomial exact, bilateral) : p = %.4f" % p)
        if nt < SEANCES_MINI:
            print("  A LIRE AVEC PRUDENCE : %d seances seulement. Le p le"
                  % nt)
            print("  plus fort atteignable ici est %.3f -- c est le plancher"
                  % binom_bilateral(nt, nt))
            print("  du test, obtenu meme si TOUTES les seances sont rouges.")
            print("  Un signe unanime sur %d seances reste peu de chose ;"
                  % nt)
            print("  c est la sous-periode qui est courte, pas le resultat")
            print("  qui est faible.")

    # La concentration : ce que devient le total sans les pires seances.
    print()
    print("  Concentration -- le total tient-il sans les pires seances ?")
    reste = list(vals)
    for k in (1, 2, 3):
        if len(reste) <= 1:
            break
        reste = reste[1:]      # vals trie croissant : on retire la pire
        print("    sans les %d pire(s) : %9.2f EUR  sur %d seances"
              % (k, sum(reste), len(reste)))
    return total


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*", default=[DEFAUT])
    p.add_argument("--heures", nargs=2, type=int, default=[9, 11],
                   metavar=("DE", "A"), help="bornes incluses, defaut 9 11")
    p.add_argument("--bascule", default=BASCULE)
    p.add_argument("--depuis", default=None)
    a = p.parse_args()

    h0, h1 = a.heures
    tk = charger(a.fichier)
    if a.depuis:
        tk = [t for t in tk if t["jour"] >= a.depuis]

    jours = sorted({t["jour"] for t in tk})
    print("=" * LARG)
    print(" SCALP-EA / LE CRENEAU %02dh-%02dh, SEANCE PAR SEANCE" % (h0, h1))
    print("=" * LARG)
    print("%d tickets, %d seances, du %s au %s"
          % (len(tk), len(jours), jours[0], jours[-1]))
    print("Creneau : heures %02d a %02d incluses. Bascule : %s"
          % (h0, h1, a.bascule))
    print()
    print("L unite est la SEANCE, pas le ticket. Deux mauvaises journees")
    print("suffisent a fabriquer une moyenne par ticket ; elles ne")
    print("suffisent pas a fabriquer un signe repete.")

    def par_seance(sous):
        d = {}
        for t in sous:
            if h0 <= t["heure"] <= h1:
                e = d.setdefault(t["jour"], [0.0, 0])
                e[0] += t["pnl"]
                e[1] += 1
        return [(j, v[0], v[1]) for j, v in d.items()]

    tout = par_seance(tk)
    bloc("TOUTES PERIODES", tout)

    av = [t for t in tk if t["jour"] < a.bascule]
    ap = [t for t in tk if t["jour"] >= a.bascule]
    bloc("TENDANCE  (avant %s)" % a.bascule, par_seance(av))
    bloc("RANGE     (a partir du %s)" % a.bascule, par_seance(ap))

    # Contrefactuel : le creneau retire, sur tout le corpus.
    dedans = sum(t["pnl"] for t in tk if h0 <= t["heure"] <= h1)
    dehors = sum(t["pnl"] for t in tk if not (h0 <= t["heure"] <= h1))
    n_d = sum(1 for t in tk if h0 <= t["heure"] <= h1)
    print()
    print("CONTREFACTUEL")
    print("-" * LARG)
    print("  P&L total actuel        : %10.2f EUR  (%d tickets)"
          % (dedans + dehors, len(tk)))
    print("  dont creneau %02dh-%02dh    : %10.2f EUR  (%d tickets)"
          % (h0, h1, dedans, n_d))
    print("  P&L sans le creneau     : %10.2f EUR  (%d tickets)"
          % (dehors, len(tk) - n_d))
    print()
    print("  Ce dernier chiffre suppose que RIEN d autre ne change : ni")
    print("  les positions du reste de la journee, ni le comportement des")
    print("  gates. C est un plafond, pas une prevision.")
    print()
    print("=" * LARG)
    return 0


if __name__ == "__main__":
    sys.exit(main())

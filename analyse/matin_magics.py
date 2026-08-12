# -*- coding: utf-8 -*-
"""
matin_magics.py -- qui perd le matin, magic par magic

  python matin_magics.py --fichier docs\\rails_trades\\tickets_rails.jsonl

D OU VIENT LA QUESTION

    matin_trail.py a montre que la perte du creneau 09h-11h est portee
    entierement par les tickets HORS TRAIL -- ceux que le trail n a
    jamais vus, exclus par leur MAGIC :

        matin  -15.08 EUR/tk sur  815 tickets   soit -12 290 EUR
        reste   -2.30 EUR/tk sur 1673 tickets

    L exclusion est decidee par le numero de magic, avant l entree, donc
    independamment du resultat : c est un groupe exogene, contrairement
    aux cellules AVEC / SANS STOP qui affichaient 100 % de gagnants et
    ne mesuraient rien d autre que leur propre selection.

    Reste a savoir QUI compose ces 815 tickets. Parce que le patch du
    11/08 fait entrer les familles 207 d US30 dans le dispositif : si la
    perte se concentre sur elles, elle va changer de nature toute seule.
    Si elle se concentre ailleurs, c est ailleurs qu il faut agir.

CE QUE LE SCRIPT MONTRE

    Par magic, cote a cote, le matin et le reste de la journee. La
    colonne qui compte n est pas le total du matin -- un magic qui perd
    partout n a pas un probleme d heure -- mais l ECART entre les deux.

    Un magic qui perd le matin ET l apres-midi est un magic a revoir.
    Un magic qui ne perd QUE le matin est un candidat au blocage
    horaire. Ce ne sont pas les memes decisions.

    La colonne TRAIL dit si le magic est desormais suivi (le patch du
    11/08 a ajoute les 207xxx d US30) ou toujours dehors. Bloquer un
    magic que le patch vient de reparer serait juger avant de mesurer.

CE QU IL NE FAIT PAS

    Il ne teste rien. Decouper 815 tickets en une dizaine de magics rend
    chaque cellule petite : a ce niveau, les chiffres DECRIVENT, ils ne
    concluent pas. Toute regle tiree d ici doit repasser par
    matin_seances.py, qui compte les seances.

LECTURE SEULE. Aucun appel MT5. Aucune ecriture.
"""
import argparse
import csv
import io
import json
import os
import sys

try:
    import oos_v9 as O
except ImportError:
    print("KO : oos_v9.py introuvable a cote de ce script.")
    print("Il porte la normalisation des champs rails.")
    sys.exit(1)

DEFAUT = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
CSV_TRAIL = "mfe_trail_events.csv"
CLEFS_MAGIC = ["magic", "magic_number", "magicnumber", "mg"]
MINI = 30
LARG = 92


def charger(chemins):
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
            mg = O._nombre(O._prem(o, CLEFS_MAGIC))
            par[tk] = {"jour": ts[:10], "heure": int(ts[11:13]), "pnl": pnl,
                       "ticket": str(tk),
                       "magic": ("M%d" % int(mg)) if mg else "M?"}
    if not par:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        sys.exit(1)
    return list(par.values())


def vus_du_trail(chemin):
    vus = set()
    if not os.path.isfile(chemin):
        return vus
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            tk = str(r.get("ticket") or "").strip()
            if tk:
                vus.add(tk)
    return vus


def stat(lot):
    if not lot:
        return None
    p = sum(t["pnl"] for t in lot)
    n = len(lot)
    w = sum(1 for t in lot if t["pnl"] > 0)
    return p, n, p / n, 100.0 * w / n


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*", default=[DEFAUT])
    p.add_argument("--trail", default=CSV_TRAIL)
    p.add_argument("--heures", nargs=2, type=int, default=[9, 11])
    p.add_argument("--tous", action="store_true",
                   help="ne pas se limiter aux tickets hors trail")
    a = p.parse_args()

    h0, h1 = a.heures
    tk = charger(a.fichier)
    vus = vus_du_trail(a.trail)
    if not vus and not a.tous:
        print("KO : %s introuvable. Sans lui, impossible de savoir qui"
              % a.trail)
        print("est hors trail. Relance avec --tous pour ignorer ce filtre.")
        return 1

    sous = tk if a.tous else [t for t in tk if t["ticket"] not in vus]
    matin = [t for t in sous if h0 <= t["heure"] <= h1]
    reste = [t for t in sous if not (h0 <= t["heure"] <= h1)]

    print("=" * LARG)
    print(" SCALP-EA / QUI PERD ENTRE %02dh ET %02dh" % (h0, h1))
    print("=" * LARG)
    print("Perimetre : %s" % ("TOUS les tickets" if a.tous
                              else "tickets HORS TRAIL (exclus par leur magic)"))
    print("%d tickets retenus sur %d : %d le matin, %d le reste."
          % (len(sous), len(tk), len(matin), len(reste)))

    magics = sorted({t["magic"] for t in matin})
    lignes = []
    for m in magics:
        sm = stat([t for t in matin if t["magic"] == m])
        sr = stat([t for t in reste if t["magic"] == m])
        lignes.append((sm[0], m, sm, sr))
    lignes.sort()      # le plus gros perdant du matin en premier

    print()
    print("%-10s %26s %26s %12s" % ("magic", "MATIN", "RESTE", "ecart"))
    print("%-10s %9s %5s %5s %5s %9s %5s %5s %5s %12s"
          % ("", "EUR", "tk", "/tk", "WR", "EUR", "tk", "/tk", "WR", "EUR/tk"))
    print("-" * LARG)
    for _, m, sm, sr in lignes:
        out = "%-10s %9.0f %5d %5.1f %4.0f%%" % (m, sm[0], sm[1], sm[2], sm[3])
        if sr:
            out += " %9.0f %5d %5.1f %4.0f%%" % (sr[0], sr[1], sr[2], sr[3])
            out += " %12.1f" % (sm[2] - sr[2])
        else:
            out += " %26s %12s" % ("(aucun)", "-")
        if sm[1] < MINI:
            out += "  ?"
        print(out)
    print("-" * LARG)
    tm, tr = stat(matin), stat(reste)
    print("%-10s %9.0f %5d %5.1f %4.0f%% %9.0f %5d %5.1f %4.0f%% %12.1f"
          % ("TOTAL", tm[0], tm[1], tm[2], tm[3],
             tr[0], tr[1], tr[2], tr[3], tm[2] - tr[2]))
    print("  ? = moins de %d tickets le matin : la ligne decrit, elle ne"
          % MINI)
    print("      conclut pas.")

    # Concentration : combien de magics font la perte ?
    perdants = [(s, m) for s, m, _, _ in lignes if s < 0]
    if perdants:
        tot = sum(s for s, _ in perdants)
        cum, k = 0.0, 0
        for s, _ in perdants:
            cum += s
            k += 1
            if cum <= 0.8 * tot:
                break
        print()
        print("CONCENTRATION")
        print("-" * LARG)
        print("  %d magic(s) perdant(s) le matin, total %.0f EUR."
              % (len(perdants), tot))
        print("  Les %d pire(s) en font 80%% : %s"
              % (k, ", ".join(m for _, m in perdants[:k])))

    print()
    print("COMMENT LIRE LA COLONNE ECART")
    print("-" * LARG)
    print("  Un magic qui perd le matin ET le reste n a pas un probleme")
    print("  d heure : c est le magic qu il faut revoir. Seul un ecart")
    print("  large et negatif designe un probleme propre au creneau.")
    print()
    print("  Et avant toute regle : le patch du 11/08 fait entrer les")
    print("  familles 207 d US30 dans le trail. Un magic 207xxx qui")
    print("  apparait ici etait hors dispositif AVANT le patch et ne l est")
    print("  plus. Le bloquer maintenant, ce serait juger avant de mesurer.")
    print()
    print("=" * LARG)
    return 0


if __name__ == "__main__":
    sys.exit(main())

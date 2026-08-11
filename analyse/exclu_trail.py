# -*- coding: utf-8 -*-
"""
exclu_trail.py -- qui est exclu du trailing MFE, et combien ca represente

  python exclu_trail.py
  python exclu_trail.py --depuis 2026-08-05

LA QUESTION
    Le journal mfe_trail_events.csv ne contient AUCUNE ligne US30 du 28/07
    au 11/08, alors que le module annonce au demarrage "managing
    US30/NAS100/SPX500". Soit aucun trade US30 n a atteint le seuil, soit
    les magics US30 sont dans EXCLUDED_MAGICS.

    La liste est illisible a l oeil : trois ensembles de plusieurs dizaines
    de plages, enroules sur des lignes de deux mille caracteres. Ce script
    les evalue proprement et croise avec les magics qui tradent vraiment.

COMMENT IL LIT LA LISTE, ET POURQUOI PAS PAR import
    Importer mfe_ticket_trail executerait son en-tete, donc MetaTrader5 et
    tout ce qui suit, dans un processus qui n a rien a y faire pendant que
    le moteur tourne. On analyse le fichier avec ast et on evalue la SEULE
    expression EXCLUDED_MAGICS, dans un evaluateur qui ne connait que :

        {litteraux}         un ensemble en dur
        set(range(a, b))    une plage
        a | b               l union

    Tout le reste leve une erreur plutot que de deviner. Aucun code du
    fichier n est execute.

CE QU IL CROISE
    docs/rails_trades/tickets_rails.jsonl -- les tickets reellement passes,
    avec leur magic et leur actif. On obtient donc, par actif :
    combien de magics tradent, combien sont exclus, et surtout quelle PART
    DU VOLUME ET DU P&L se trouve hors du dispositif de trailing.

    C est ce dernier chiffre qui compte. Regler le trailing n a d interet
    que sur la portion de la stack a laquelle il s applique.
"""
import argparse
import ast
import csv
import io
import json
import os
import sys
from collections import defaultdict

CIBLE = "mfe_ticket_trail.py"
TICKETS = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
EVENTS = "mfe_trail_events.csv"

# Les noms d actifs varient d un fichier a l autre. On ramene tout aux
# trois cles de EXCLUDED_MAGICS.
NORM = {"US30": "US30", "DJ30": "US30", "US30.CASH": "US30",
        "NAS100": "NAS100", "US100": "NAS100", "USTEC": "NAS100",
        "NAS100.CASH": "NAS100", "US100.CASH": "NAS100",
        "SPX500": "SPX500", "US500": "SPX500", "SPX500.CASH": "SPX500",
        "US500.CASH": "SPX500"}


def nombre(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def norm(a):
    return NORM.get(str(a or "").strip().upper().replace(" ", ""), None)


# ------------------------------------------------- evaluation surveillee

class Refus(Exception):
    pass


def _ev(n):
    """Evalue une expression d ensemble. Tout le reste est refuse."""
    if isinstance(n, ast.Set):
        out = set()
        for e in n.elts:
            v = ast.literal_eval(e)
            if not isinstance(v, int):
                raise Refus("element non entier : %r" % (v,))
            out.add(v)
        return out
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
        return _ev(n.left) | _ev(n.right)
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
        if n.func.id == "set" and len(n.args) == 1:
            return _ev(n.args[0])
        if n.func.id == "range":
            args = [ast.literal_eval(a) for a in n.args]
            return set(range(*args))
        if n.func.id == "frozenset" and len(n.args) == 1:
            return _ev(n.args[0])
    if isinstance(n, ast.Dict):
        raise Refus("dict la ou un ensemble etait attendu")
    raise Refus("expression non prevue : %s" % type(n).__name__)


def lire_exclusions(chemin):
    """Rend {actif: set(magics)} sans executer une ligne du fichier."""
    src = io.open(chemin, encoding="utf-8-sig", errors="replace").read()
    arbre = ast.parse(src)
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Assign):
            continue
        noms = [t.id for t in n.targets if isinstance(t, ast.Name)]
        if "EXCLUDED_MAGICS" not in noms:
            continue
        if not isinstance(n.value, ast.Dict):
            raise Refus("EXCLUDED_MAGICS n est pas un dictionnaire")
        out = {}
        for k, v in zip(n.value.keys, n.value.values):
            out[str(ast.literal_eval(k))] = _ev(v)
        return out
    raise Refus("EXCLUDED_MAGICS introuvable dans %s" % chemin)


# ------------------------------------------------------------- lectures

def lire_tickets(chemin):
    """[(actif, magic, pnl, mfe)] pour chaque ticket exploitable."""
    out = []
    for l in io.open(chemin, encoding="utf-8-sig"):
        l = l.strip()
        if not l or l[0] != "{":
            continue
        try:
            o = json.loads(l)
        except ValueError:
            continue
        a = norm(o.get("asset"))
        m = nombre(o.get("magic"))
        p = nombre(o.get("pnl_eur"))
        if a is None or m is None or p is None:
            continue
        out.append((a, int(m), p, nombre(o.get("mfe_eur")) or 0.0,
                    str(o.get("ticket") or ""), str(o.get("entry_ts") or "")))
    return out


def magics_vus(chemin):
    """Les magics qui apparaissent dans le journal du trail, par actif."""
    vus = defaultdict(set)
    if not os.path.isfile(chemin):
        return vus
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            a = norm(r.get("symbol"))
            m = nombre(r.get("magic"))
            if a and m is not None:
                vus[a].add(int(m))
    return vus


def cadre(t):
    print()
    print("=" * 92)
    print("  " + t)
    print("=" * 92)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--tickets", default=TICKETS)
    p.add_argument("--events", default=EVENTS)
    p.add_argument("--depuis", default=None)
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    try:
        exclu = lire_exclusions(a.fichier)
    except (Refus, SyntaxError) as e:
        print("KO : lecture de EXCLUDED_MAGICS impossible : %s" % e)
        print("Le script refuse de deviner. Rien n a ete modifie.")
        return 1

    print("=== SCALP-EA / QUI EST EXCLU DU TRAILING MFE ===")
    print("%s : EXCLUDED_MAGICS lu sans executer le fichier." % a.fichier)

    cadre("TAILLE DES TROIS ENSEMBLES")
    print("%-12s %14s" % ("actif", "magics exclus"))
    print("-" * 92)
    for k in sorted(exclu):
        print("%-12s %14d" % (k, len(exclu[k])))
    print("-" * 92)
    cles = sorted(exclu)
    if len(cles) == 3:
        a1, a2, a3 = (exclu[c] for c in cles)
        print("communs aux trois : %d" % len(a1 & a2 & a3))
        for c in cles:
            propre = exclu[c] - set().union(*(exclu[o] for o in cles if o != c))
            print("propres a %-8s : %d" % (c, len(propre)))

    # ------------------------------------------------ ce qui trade vraiment
    if not os.path.isfile(a.tickets):
        print()
        print("%s absent : impossible de croiser avec les trades reels."
              % a.tickets)
        print("Lance rails_join.py, puis relance.")
        return 0

    tk = lire_tickets(a.tickets)
    if a.depuis:
        tk = [t for t in tk if t[5][:10] >= a.depuis]
    if not tk:
        print("Aucun ticket exploitable dans %s." % a.tickets)
        return 0

    cadre("LA PART DE LA STACK HORS DU DISPOSITIF")
    print("  Un magic exclu ne recoit JAMAIS de stop de mfe_ticket_trail,")
    print("  quel que soit son MFE. Regler le trailing ne le concerne pas.")
    print()
    print("%-10s %8s %8s %10s %12s %12s %9s"
          % ("actif", "magics", "exclus", "tickets", "P&L exclus",
             "P&L total", "part"))
    print("-" * 92)
    total_ex = total = 0.0
    for act in sorted(set(t[0] for t in tk)):
        lot = [t for t in tk if t[0] == act]
        ens = exclu.get(act, set())
        mg = sorted(set(t[1] for t in lot))
        dedans = [t for t in lot if t[1] in ens]
        pe = sum(t[2] for t in dedans)
        pt = sum(t[2] for t in lot)
        total_ex += pe
        total += pt
        print("%-10s %8d %8d %10d %12.2f %12.2f %8.0f%%"
              % (act, len(mg), sum(1 for m in mg if m in ens), len(lot),
                 pe, pt, 100.0 * len(dedans) / len(lot)))
    print("-" * 92)
    print("part des TICKETS hors dispositif, tous actifs : voir colonne part")
    print("P&L des exclus %.2f sur %.2f" % (total_ex, total))
    print()
    print("  Attention : 'part' compte des TICKETS, pas des euros. Un actif")
    print("  peut etre exclu a 90% en nombre et peser peu en resultat, ou")
    print("  l inverse. Les deux colonnes de P&L sont la pour ca.")

    # -------------------------------------------- le detail par actif exclu
    cadre("LE DETAIL -- quels magics, et ce qu ils pesent")
    for act in sorted(set(t[0] for t in tk)):
        lot = [t for t in tk if t[0] == act]
        ens = exclu.get(act, set())
        par = defaultdict(lambda: [0, 0.0, 0.0])
        for _, m, pnl, mfe, _, _ in lot:
            d = par[m]
            d[0] += 1
            d[1] += pnl
            d[2] += mfe if mfe > 0 else 0.0
        print()
        print("  %s" % act)
        print("  %-10s %6s %6s %12s %12s %9s"
              % ("magic", "excl.", "N", "P&L EUR", "MFE EUR", "capture"))
        print("  " + "-" * 88)
        for m in sorted(par, key=lambda x: -par[x][0])[:14]:
            n, pnl, mfe = par[m]
            print("  %-10d %6s %6d %12.2f %12.2f %8s"
                  % (m, "OUI" if m in ens else "-", n, pnl, mfe,
                     ("%.0f%%" % (100.0 * pnl / mfe)) if mfe > 0 else "-"))
    print()
    print("-" * 92)
    print("  Un magic marque OUI ne peut pas beneficier du reglage a 0,12%.")
    print("  Sa capture est celle qu il obtient SANS trailing : c est la")
    print("  colonne a comparer aux 57% des tickets proteges.")

    # ---------------------------------- coherence avec le journal du trail
    vus = magics_vus(a.events)
    if vus:
        cadre("CONTROLE DE COHERENCE")
        print("  Les magics vus dans %s ne doivent JAMAIS etre" % a.events)
        print("  dans l ensemble exclu de leur actif. Si l un y est, ma")
        print("  lecture de EXCLUDED_MAGICS est fausse.")
        print()
        faux = 0
        for act in sorted(vus):
            ens = exclu.get(act, set())
            mauvais = sorted(m for m in vus[act] if m in ens)
            print("  %-10s %3d magics dans le journal, %d exclus %s"
                  % (act, len(vus[act]), len(mauvais),
                     ("-> " + ", ".join(str(x) for x in mauvais[:6]))
                     if mauvais else ""))
            faux += len(mauvais)
        print()
        if faux:
            print("  INCOHERENT : %d magics apparaissent dans le journal du" % faux)
            print("  trail alors qu ils sont declares exclus. Ne pas se fier")
            print("  au reste de cette sortie tant que ce n est pas explique.")
        else:
            print("  Coherent. Aucun magic exclu n apparait dans le journal,")
            print("  ce qui confirme la lecture de la liste.")
        for act in ("US30", "NAS100", "SPX500"):
            if act not in vus and any(t[0] == act for t in tk):
                n = sum(1 for t in tk if t[0] == act)
                ex = sum(1 for t in tk if t[0] == act
                         and t[1] in exclu.get(act, set()))
                print()
                print("  %s : %d tickets trades, AUCUN dans le journal du"
                      % (act, n))
                print("  trail. %d d entre eux (%.0f%%) portent un magic exclu."
                      % (ex, 100.0 * ex / n if n else 0.0))
                if n and ex == n:
                    print("  L exclusion suffit a tout expliquer.")
                elif n and ex < n:
                    print("  L exclusion n explique que %.0f%% du silence. Le"
                          % (100.0 * ex / n))
                    print("  reste tient a autre chose -- seuil jamais atteint,")
                    print("  ou une condition que ce script ne voit pas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

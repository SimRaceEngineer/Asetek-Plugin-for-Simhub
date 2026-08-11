# -*- coding: utf-8 -*-
"""
bande_morte.py -- ce que C14 refuse a mfe_ticket_trail, mesure sur le journal

  python bande_morte.py
  python bande_morte.py --csv mfe_trail_events.csv
  python bande_morte.py --depuis 2026-08-05

CE QU ON A ETABLI LE 11/08 AU SOIR
    mfe_ticket_trail.py pose le stop en trois crans, declenches par le MFE
    absolu, et les seuils sont un pourcentage du prix d entree :

        BE     a 0.08%    stop pose a entree + buffer (0.004%)
        lock50 a 0.16%    stop pose a 50% du MFE
        lock70 a 0.32%    stop pose a 70% du MFE

    buddha_clause_gate.C14 intercepte toute requete TRADE_ACTION_SLTP et
    refuse celles qui RESSERRENT le stop a moins de C14_BE_PROXIMITY de
    l entree -- 20 points sur US30 et US100, 3 sur US500 -- quand le biais
    Buddha est HOLD ou aligne avec la position.

    Le cran BE pose le stop a 0,3 a 2,0 point de l entree selon l actif.
    Il est donc TOUJOURS dans la fenetre de veto. Le cran lock50, lui,
    pose le stop bien au-dela et passe.

    D ou une bande morte entre le cran interdit et le cran pas encore
    atteint : sur NAS100, entre 23 et 47 points de MFE, aucune protection.

    Tout cela est deduit de la lecture du code et de six lignes de log.
    Ce script le VERIFIE, ou le refute, sur le journal complet.

LES TROIS QUESTIONS, DANS L ORDRE
    1. Le modele tient-il ? Pour chaque evenement on calcule la distance
       du stop demande a l entree, on PREDIT le refus, et on compare au
       retcode reel. Un tableau croise 2x2. Si les diagonales ne sont pas
       nettes, mon explication est fausse et le reste ne vaut rien.

    2. Combien de tickets sont concernes ? Par ticket : le cran le plus
       haut TENTE, et le cran le plus haut REUSSI. L ecart entre les deux
       est le cout du veto.

    3. Combien ca coute ? Le CSV ne porte pas le P&L. Si
       docs/rails_trades/tickets_rails.jsonl est la, on joint par ticket
       et on chiffre en euros. Sinon on s arrete au comptage, et on le dit.

CE QU IL NE PEUT PAS DIRE
    Le CSV ne journalise que les tentatives de CE module. Les autres
    systemes qui deplacent des stops -- SAR M1, R8 Volcan, exit_manager,
    sorties par magic -- passent aussi par C14 mais n ecrivent pas ici.
    La bande morte mesuree est donc un PLANCHER, pas un total.

    peak_mfe_pts est le pic vu par le module a cet instant, pas le MFE
    final du trade. Un ticket peut avoir grimpe apres son dernier
    evenement journalise.
"""
import argparse
import csv
import io
import json
import os
import re
import sys
from collections import defaultdict

RE_QUEUE = re.compile(r"_[\d.]+pt\s*$")

CSV_DEFAUT = "mfe_trail_events.csv"
TICKETS = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")

OK = 10009                      # TRADE_RETCODE_DONE
BE_PCT, L50_PCT, L70_PCT = 0.0008, 0.0016, 0.0032
BUF_PCT = 0.00004

# Les cles de C14_BE_PROXIMITY, et la correspondance avec les symboles du
# CSV. mfe_ticket_trail nomme NAS100/SPX500, C14 nomme US100/US500.
PROX = {"US30": 20.0, "US500": 3.0, "US100": 20.0}
ACTIF = {"US30": "US30", "DE40": None,
         "SPX500": "US500", "US500": "US500",
         "NAS100": "US100", "US100": "US100"}
NOMS_CRAN = {0: "0 aucun", 1: "1 BE", 2: "2 lock50", 3: "3 lock70"}


def nombre(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def entier(v):
    try:
        return int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def charger(chemin, depuis):
    """Une ligne du CSV -> un dict, en ne gardant que ce qui est complet."""
    lignes = ignorees = 0
    ev = []
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            lignes += 1
            ts = str(r.get("timestamp") or "")
            if depuis and ts[:10] < depuis:
                continue
            op = nombre(r.get("open_price"))
            ns = nombre(r.get("new_sl"))
            pk = nombre(r.get("peak_mfe_pts"))
            tr = entier(r.get("tier"))
            rc = entier(r.get("retcode"))
            tk = str(r.get("ticket") or "").strip()
            if not tk or op is None or ns is None or tr is None or rc is None:
                ignorees += 1
                continue
            sym = str(r.get("symbol") or "?").strip()
            ev.append({
                "jour": ts[:10], "ticket": tk, "sym": sym,
                "actif": ACTIF.get(sym),
                "magic": str(r.get("magic") or "?").strip(),
                "open": op, "new_sl": ns, "peak": pk, "tier": tr, "rc": rc,
                "comment": str(r.get("comment") or "").strip(),
                "dist": abs(ns - op),
            })
    return ev, lignes, ignorees


def cadre(titre):
    print()
    print("=" * 92)
    print("  " + titre)
    print("=" * 92)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=CSV_DEFAUT)
    p.add_argument("--depuis", default=None,
                   help="ne garder que les evenements a partir de cette date")
    p.add_argument("--tickets", default=TICKETS)
    a = p.parse_args()

    if not os.path.isfile(a.csv):
        print("KO : %s introuvable -- lance depuis le dossier de la stack." % a.csv)
        return 1

    ev, lignes, ignorees = charger(a.csv, a.depuis)
    if not ev:
        print("Aucun evenement exploitable sur %d lignes." % lignes)
        return 1

    jours = sorted(set(e["jour"] for e in ev))
    tks = set(e["ticket"] for e in ev)
    print("=== SCALP-EA / LA BANDE MORTE DU TRAILING ===")
    print("%s : %d lignes, %d retenues, %d tickets, %s -> %s"
          % (a.csv, lignes, len(ev), len(tks), jours[0], jours[-1]))
    if ignorees:
        print("%d lignes ecartees (champ manquant ou illisible)." % ignorees)

    # ------------------------------------------------------- 1. volumetrie
    cadre("TENTATIVES PAR ACTIF ET PAR CRAN -- combien passent")
    print("%-10s %-10s %8s %8s %8s %8s"
          % ("symbole", "cran", "tentees", "reussies", "refusees", "% ok"))
    print("-" * 92)
    g = defaultdict(list)
    for e in ev:
        g[(e["sym"], e["tier"])].append(e)
    for cle in sorted(g):
        lot = g[cle]
        ok = sum(1 for e in lot if e["rc"] == OK)
        print("%-10s %-10s %8d %8d %8d %7.0f%%"
              % (cle[0], NOMS_CRAN.get(cle[1], str(cle[1])), len(lot), ok,
                 len(lot) - ok, 100.0 * ok / len(lot)))
    print("-" * 92)

    # --------------------------------------------------- 2. les refus, qui
    cadre("LES REFUS -- qui prononce le veto")
    refus = [e for e in ev if e["rc"] != OK]
    if not refus:
        print("  Aucun refus dans ce journal. Le modele est refute :")
        print("  si rien n est refuse, C14 ne bloque pas ce module.")
    else:
        # On enleve la distance de fin de commentaire -- "_1.2pt" -- sinon
        # chaque valeur fait son propre groupe et on ne voit plus la clause.
        motifs = defaultdict(int)
        for e in refus:
            c = RE_QUEUE.sub("", e["comment"])
            motifs[c[:46] or "(vide)"] += 1
        print("%-48s %8s %7s" % ("commentaire", "N", "part"))
        print("-" * 92)
        for m in sorted(motifs, key=lambda x: -motifs[x])[:18]:
            print("%-48s %8d %6.0f%%"
                  % (m, motifs[m], 100.0 * motifs[m] / len(refus)))
        print("-" * 92)
        print("%d refus sur %d tentatives, soit %.0f%%."
              % (len(refus), len(ev), 100.0 * len(refus) / len(ev)))

    # ------------------------------------------ 3. LE TEST DU MODELE (2x2)
    cadre("LE TEST -- ma prediction contre la realite")
    print("  Predit refuse = le stop demande atterrit a MOINS de la fenetre")
    print("  C14 de l entree (20 pts US30/US100, 3 pts US500), donc dans la")
    print("  zone que la clause protege. Les actifs hors de PROX sont exclus.")
    print()
    cases = {(True, True): 0, (True, False): 0,
             (False, True): 0, (False, False): 0}
    hors = 0
    for e in ev:
        pr = PROX.get(e["actif"]) if e["actif"] else None
        if pr is None:
            hors += 1
            continue
        cases[(e["dist"] <= pr, e["rc"] != OK)] += 1
    tot = sum(cases.values())
    if not tot:
        print("  Aucun evenement sur un actif connu de C14.")
    else:
        print("%-24s %14s %14s" % ("", "refuse en vrai", "passe en vrai"))
        print("-" * 92)
        print("%-24s %14d %14d" % ("predit refuse",
                                   cases[(True, True)], cases[(True, False)]))
        print("%-24s %14d %14d" % ("predit passant",
                                   cases[(False, True)], cases[(False, False)]))
        print("-" * 92)
        just = cases[(True, True)] + cases[(False, False)]
        print("accord : %d sur %d, soit %.1f%%" % (just, tot, 100.0 * just / tot))
        print()
        if 100.0 * just / tot >= 90:
            print("  Le modele tient. La distance a l entree explique le refus.")
        else:
            print("  LE MODELE NE TIENT PAS. La distance a l entree n explique")
            print("  pas les refus -- ne pas construire sur l explication C14")
            print("  avant d avoir trouve ce qui les explique vraiment.")
        if hors:
            print("  (%d evenements sur un actif hors PROX, exclus du test.)" % hors)

    # ---------------------------------------- 4. par ticket : tente / reussi
    cadre("PAR TICKET -- le cran atteint, et le cran obtenu")
    par = {}
    for e in ev:
        d = par.setdefault(e["ticket"], {
            "sym": e["sym"], "open": e["open"], "tente": 0, "reussi": 0,
            "peak": 0.0, "n": 0})
        d["n"] += 1
        d["tente"] = max(d["tente"], e["tier"])
        if e["rc"] == OK:
            d["reussi"] = max(d["reussi"], e["tier"])
        if e["peak"] is not None:
            d["peak"] = max(d["peak"], e["peak"])
    print("%-14s %10s %10s %10s" % ("cran tente", "tickets", "obtenu 0", "part 0"))
    print("-" * 92)
    for t in sorted(set(d["tente"] for d in par.values())):
        lot = [d for d in par.values() if d["tente"] == t]
        zero = sum(1 for d in lot if d["reussi"] == 0)
        print("%-14s %10d %10d %9.0f%%"
              % (NOMS_CRAN.get(t, str(t)), len(lot), zero,
                 100.0 * zero / len(lot)))
    print("-" * 92)
    jamais = [tk for tk, d in par.items() if d["reussi"] == 0]
    print("%d tickets sur %d n ont JAMAIS obtenu un seul deplacement de stop."
          % (len(jamais), len(par)))

    # ------------------------------------------------- 5. la bande morte
    cadre("LA BANDE MORTE -- ou meurent les pics de MFE")
    print("  Seuils recalcules ticket par ticket depuis son prix d entree :")
    print("  BE a 0.08%, lock50 a 0.16%, lock70 a 0.32%.")
    print()
    seaux = defaultdict(list)
    for tk, d in par.items():
        be, l50, l70 = (d["open"] * BE_PCT, d["open"] * L50_PCT,
                        d["open"] * L70_PCT)
        pk = d["peak"]
        if pk < be:
            s = "1 sous BE"
        elif pk < l50:
            s = "2 BANDE MORTE"
        elif pk < l70:
            s = "3 lock50 atteint"
        else:
            s = "4 lock70 atteint"
        seaux[s].append((tk, d))
    print("%-18s %10s %10s %12s %12s"
          % ("zone", "tickets", "part", "sans stop", "pic moyen"))
    print("-" * 92)
    for s in sorted(seaux):
        lot = seaux[s]
        zero = sum(1 for _, d in lot if d["reussi"] == 0)
        pm = sum(d["peak"] for _, d in lot) / len(lot)
        print("%-18s %10d %9.0f%% %12d %12.1f"
              % (s, len(lot), 100.0 * len(lot) / len(par), zero, pm))
    print("-" * 92)
    print("  'sans stop' = aucun deplacement de stop obtenu de tout le trade.")
    print("  La ligne BANDE MORTE est celle qui compte : le pic a depasse le")
    print("  seuil BE -- donc le module a bien essaye -- sans atteindre")
    print("  lock50, le seul cran qui franchit la fenetre de C14.")

    # ------------------------------------------------ 6. le cout, si on peut
    cadre("LE COUT EN EUROS")
    if not os.path.isfile(a.tickets):
        print("  %s absent : pas de jointure possible." % a.tickets)
        print("  Lance rails_join.py d abord, puis relance ce script.")
        print("  Sans lui on compte des tickets, on ne chiffre pas des euros.")
    else:
        pnl, mfe = {}, {}
        for l in io.open(a.tickets, encoding="utf-8-sig"):
            l = l.strip()
            if not l or l[0] != "{":
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            tk = str(o.get("ticket") or "").strip()
            if not tk:
                continue
            v = nombre(o.get("pnl_eur"))
            if v is not None:
                pnl[tk] = v
            m = nombre(o.get("mfe_eur"))
            if m is not None:
                mfe[tk] = m
        joints = sum(1 for tk in par if tk in pnl)
        print("  %d tickets du journal trail retrouves dans tickets_rails"
              " (%.0f%%)." % (joints, 100.0 * joints / len(par)))
        if not joints:
            print("  Aucune correspondance : les tickets ne portent pas le")
            print("  meme identifiant dans les deux fichiers.")
        else:
            print()
            print("%-18s %8s %12s %12s %10s"
                  % ("zone", "tickets", "P&L EUR", "MFE EUR", "capture"))
            print("-" * 92)
            for s in sorted(seaux):
                lot = [tk for tk, _ in seaux[s] if tk in pnl]
                if not lot:
                    continue
                sp = sum(pnl[tk] for tk in lot)
                sm = sum(mfe.get(tk, 0.0) for tk in lot
                         if mfe.get(tk, 0.0) > 0)
                print("%-18s %8d %12.2f %12.2f %9s"
                      % (s, len(lot), sp, sm,
                         ("%.0f%%" % (100.0 * sp / sm)) if sm > 0 else "-"))
            print("-" * 92)
            print("  capture = P&L / MFE. Negatif = fini sous zero apres")
            print("  avoir culmine. C est la mesure a comparer aux 47%/42%")
            print("  du motif 4 et aux -3%/-62% du motif 3.")

    # --------------------------------------------------------- reserves
    cadre("CE QUE CE COMPTAGE NE DIT PAS")
    print("  1. Il ne couvre que les tentatives de mfe_ticket_trail. SAR M1,")
    print("     R8 Volcan, exit_manager et les sorties par magic passent")
    print("     aussi par C14 sans ecrire ici. La bande morte mesuree est un")
    print("     PLANCHER.")
    print("  2. peak_mfe_pts est le pic VU PAR LE MODULE a cet instant, pas")
    print("     le MFE final du trade. Un ticket a pu monter apres son")
    print("     dernier evenement journalise.")
    print("  3. Un ticket en bande morte n est pas un ticket perdu. Il est")
    print("     un ticket SANS PROTECTION : son sort depend entierement du")
    print("     closer Python, dont on sait qu il rend -3%% de son MFE en")
    print("     tendance et -62%% en range.")
    print("  4. Rien ici ne dit que C14 a tort. Sa justification est ecrite")
    print("     et empirique : un stop au break-even se fait cueillir par un")
    print("     simple retour. Le probleme n est pas le veto, c est qu aucun")
    print("     module ne propose de cran INTERMEDIAIRE entre un stop a 1,2")
    print("     point de l entree et le stop d origine a mille points.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

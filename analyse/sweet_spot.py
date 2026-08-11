# -*- coding: utf-8 -*-
"""
sweet_spot.py -- ou poser le premier stop pour qu il serve a quelque chose

  python sweet_spot.py
  python sweet_spot.py --depuis 2026-08-05
  python sweet_spot.py --actif NAS100

LA QUESTION
    Le cran BE de mfe_ticket_trail pose le stop a 0.004% du prix d entree.
    La fenetre de veto de C14 fait 0.040% (US30, US500) a 0.068% (NAS100).
    Le cran BE est donc dix a dix-sept fois trop pres pour passer, et il
    est refuse 62 709 fois sur 62 732.

    D ou la question : a quelle distance de l entree faut-il poser le
    PREMIER stop pour qu il franchisse C14 sans se faire cueillir ?

LE MODELE, ET IL EST SIMPLE
    Regle simulee : quand le MFE atteint A (en % du prix d entree), on
    pose un stop a S (en % du prix d entree), avec S < A. On ne le bouge
    plus ensuite -- c est volontairement plus prudent qu un vrai trailing,
    pour ne pas gonfler le resultat.

    Consequence sur un ticket eligible (pic >= A) :
        resultat simule = max(resultat reel, S en euros)

    Pourquoi ce max : le prix a forcement touche A, donc il a traverse S
    en montant, donc le stop est valide. S il redescend a S, on sort a S.
    S il finit au-dessus de S, le stop n a jamais ete touche et rien ne
    change.

    Conversion points -> euros, par ticket : mfe_eur / peak_mfe_pts. Elle
    est propre, elle sort des donnees du ticket lui-meme, pas d une taille
    de lot supposee.

    Un candidat dont le stop tombe DANS la fenetre C14 est marque refuse
    et ne change rien -- on simule le veto, on ne fait pas semblant qu il
    n existe pas.

LE DEFAUT DU MODELE, ET IL EST GRAVE
    max(reel, S) compte tout ce que le stop RAPPORTE en sauvant des trades
    qui ont fini sous S. Il ne compte RIEN de ce qu il COUTE en sortant
    des trades qui seraient remontes.

    Ce cout existe : c est exactement la pathologie M94/M95 que C14 a ete
    ecrit pour empecher -- +6 de MFE, stop a BE+6, un retour le touche,
    sortie a +0.3 pendant que la tendance continue. Et ce journal ne
    permet pas de le mesurer : il porte le PIC de MFE, jamais les creux.

    Donc le gain affiche est un PLAFOND, et il n a de sens qu accompagne
    de la colonne suivante.

LA COLONNE QUI SAUVE LE TABLEAU : LE TAUX DE BASCULE
    Pour chaque candidat on calcule aussi l EXPOSITION -- la somme, sur
    les tickets qui ont fini AU-DESSUS de S, de ce qu ils ont gagne
    au-dela de S. C est tout ce que le stop pourrait detruire s il se
    declenchait a tort.

        taux de bascule = gain / exposition

    Il se lit ainsi : "cette regle ne paie que si MOINS DE x% des
    gagnants au-dessus de S seraient passes par S avant de finir".

    Un taux de bascule de 40% est confortable. Un taux de 3% ne l est pas
    -- il suffirait que trois pour cent des gagnants aient fait un aller-
    retour pour que la regle coute de l argent. C est ce nombre-la qu il
    faut regarder, pas le gain.

CE QU IL NE FAIT PAS
    Pas de spread, pas de slippage, pas de trailing apres le premier
    cran. Les trois vont dans le sens defavorable ; le gain reel serait
    plus bas, sauf pour le trailing qui pourrait le relever.

    Il ne regarde que les tickets presents dans mfe_trail_events.csv,
    c est-a-dire ceux qui ont atteint au moins le seuil BE actuel. Les
    trades plus petits sont hors sujet ici.
"""
import argparse
import csv
import io
import json
import os
import sys

CSV_DEFAUT = "mfe_trail_events.csv"
TICKETS = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")

OK = 10009
BE_PCT, L50_PCT = 0.0008, 0.0016
BUF_PCT = 0.00004
LARG = 100

PROX = {"US30": 20.0, "US500": 3.0, "US100": 20.0}
ACTIF = {"US30": "US30", "SPX500": "US500", "US500": "US500",
         "NAS100": "US100", "US100": "US100"}

# Grille : A = armement, en % du prix. S = stop, en fraction de A.
ARMEMENTS = [0.0008, 0.0010, 0.0012, 0.0016, 0.0020, 0.0024]
FRACTIONS = [0.30, 0.40, 0.50, 0.60, 0.70]


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


def charger(chemin, depuis, actif):
    par = {}
    lignes = 0
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            lignes += 1
            ts = str(r.get("timestamp") or "")
            if depuis and ts[:10] < depuis:
                continue
            sym = str(r.get("symbol") or "?").strip()
            if actif and sym != actif:
                continue
            op = nombre(r.get("open_price"))
            pk = nombre(r.get("peak_mfe_pts"))
            tk = str(r.get("ticket") or "").strip()
            tr = entier(r.get("tier"))
            rc = entier(r.get("retcode"))
            if not tk or op is None or pk is None:
                continue
            d = par.setdefault(tk, {"sym": sym, "actif": ACTIF.get(sym),
                                    "open": op, "peak": 0.0, "obtenu": 0})
            d["peak"] = max(d["peak"], pk)
            if rc == OK and tr:
                d["obtenu"] = max(d["obtenu"], tr)
    return par, lignes


def joindre(par, chemin):
    n = 0
    if not os.path.isfile(chemin):
        return 0
    for l in io.open(chemin, encoding="utf-8-sig"):
        l = l.strip()
        if not l or l[0] != "{":
            continue
        try:
            o = json.loads(l)
        except ValueError:
            continue
        tk = str(o.get("ticket") or "").strip()
        d = par.get(tk)
        if d is None:
            continue
        p, m = nombre(o.get("pnl_eur")), nombre(o.get("mfe_eur"))
        if p is None or m is None or m <= 0 or d["peak"] <= 0:
            continue
        d["pnl"] = p
        d["mfe"] = m
        d["eur_pt"] = m / d["peak"]      # la conversion, ticket par ticket
        n += 1
    return n


def evalue(lot, a_pct, frac):
    """(gain, exposition, n_eligibles, n_refuses, n_sauves)."""
    gain = expo = 0.0
    elig = refus = sauves = 0
    for d in lot:
        a_pts = d["open"] * a_pct
        if d["peak"] < a_pts:
            continue
        elig += 1
        s_pts = a_pts * frac
        pr = PROX.get(d["actif"])
        if pr is not None and s_pts <= pr:
            refus += 1                    # C14 refuserait : rien ne change
            continue
        s_eur = s_pts * d["eur_pt"]
        if d["pnl"] < s_eur:
            gain += s_eur - d["pnl"]
            sauves += 1
        else:
            expo += d["pnl"] - s_eur
    return gain, expo, elig, refus, sauves


def cadre(t):
    print()
    print("=" * LARG)
    print("  " + t)
    print("=" * LARG)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=CSV_DEFAUT)
    p.add_argument("--tickets", default=TICKETS)
    p.add_argument("--depuis", default=None)
    p.add_argument("--actif", default=None,
                   help="US30, NAS100 ou SPX500 pour isoler un actif")
    a = p.parse_args()

    if not os.path.isfile(a.csv):
        print("KO : %s introuvable -- lance depuis le dossier de la stack." % a.csv)
        return 1
    par, lignes = charger(a.csv, a.depuis, a.actif)
    joints = joindre(par, a.tickets)
    lot = [d for d in par.values() if "eur_pt" in d]
    if not lot:
        print("Aucun ticket avec P&L ET pic exploitables.")
        print("Il faut docs/rails_trades/tickets_rails.jsonl -- lance")
        print("rails_join.py d abord.")
        return 1

    print("=== SCALP-EA / OU POSER LE PREMIER STOP ===")
    print("%d lignes, %d tickets, %d exploitables" % (lignes, len(par), len(lot)))
    print("reel : %.2f EUR sur ces %d tickets"
          % (sum(d["pnl"] for d in lot), len(lot)))

    # ------------------------------------------------ la geometrie d abord
    cadre("LA GEOMETRIE -- pourquoi le cran BE ne peut pas passer")
    print("%-10s %8s %10s %12s %12s %10s"
          % ("actif", "prix", "fenetre", "fenetre %", "stop BE %", "rapport"))
    print("-" * LARG)
    vus = {}
    for d in lot:
        vus.setdefault(d["sym"], []).append(d["open"])
    for sym in sorted(vus):
        px = sum(vus[sym]) / len(vus[sym])
        cle = ACTIF.get(sym)
        pr = PROX.get(cle)
        if pr is None:
            continue
        print("%-10s %8.0f %10.1f %11.3f%% %11.3f%% %9.0fx"
              % (sym, px, pr, 100.0 * pr / px, 100.0 * BUF_PCT,
                 (pr / px) / BUF_PCT))
    print("-" * LARG)
    print("  Le stop BE est pose a 0.004% du prix, la fenetre en fait dix a")
    print("  dix-sept fois plus. Aucun niveau de MFE ne peut l en sortir :")
    print("  le cran BE pose toujours le stop au meme endroit, a l entree.")

    # ------------------------------------------------------- 2. la grille
    cadre("LA GRILLE -- gain plafond, et taux de bascule qui le relativise")
    print("  A = MFE d armement, en % du prix. S = stop, en fraction de A.")
    print("  gain    = plafond, ne compte aucun gagnant sorti a tort.")
    print("  expo    = ce que le stop pourrait detruire s il se declenchait")
    print("            trop tot, sur les tickets finis au-dessus de S.")
    print("  bascule = gain / expo. La regle ne paie que si MOINS de ce")
    print("            pourcentage de gagnants seraient passes par S avant")
    print("            de finir. Plus il est haut, plus la marge est large.")
    print("            Au-dela de 100%, la regle survit meme si TOUS les")
    print("            gagnants au-dessus du stop etaient sortis a tort.")
    print()
    print("%-8s %-7s %7s %7s %7s %11s %11s %9s"
          % ("A", "S/A", "elig.", "refus", "sauves", "gain EUR",
             "expo EUR", "bascule"))
    print("-" * LARG)
    res = []
    for ap in ARMEMENTS:
        for fr in FRACTIONS:
            g, e, n, rf, sv = evalue(lot, ap, fr)
            if n == 0:
                continue
            bas = (100.0 * g / e) if e > 0 else None
            res.append((g, bas, ap, fr, n, rf, sv, e))
            print("%-8s %-7s %7d %7d %7d %11.2f %11.2f %8s"
                  % ("%.2f%%" % (100 * ap), "%.0f%%" % (100 * fr),
                     n, rf, sv, g, e,
                     ("%.0f%%" % bas) if bas is not None else "-"))
    print("-" * LARG)

    # ------------------------------------------------- 3. la recommandation
    cadre("CE QUE LE TABLEAU DIT")
    if not res:
        print("  Aucun candidat evaluable.")
        return 0
    # Le meilleur n est PAS le gain max : c est le meilleur gain parmi les
    # candidats dont la marge d erreur est confortable.
    surs = [r for r in res if r[1] is not None and r[1] >= 25.0]
    if surs:
        g, bas, ap, fr, n, rf, sv, e = max(surs, key=lambda r: r[0])
        print("  Meilleur candidat A MARGE CONFORTABLE (bascule >= 25%) :")
        print("    armement a %.2f%% du prix, stop a %.0f%% de l armement"
              % (100 * ap, 100 * fr))
        print("    %d tickets eligibles, %d sauves, %d refuses par C14"
              % (n, sv, rf))
        print("    gain plafond %.2f EUR, exposition %.2f EUR, bascule %.0f%%"
              % (g, e, bas))
        print()
        print("    A lire : cette regle rapporte au plus %.0f EUR, et elle" % g)
        print("    reste gagnante tant que moins de %.0f%% des gagnants" % bas)
        print("    au-dessus du stop seraient repasses par lui.")
    else:
        print("  AUCUN candidat n atteint 25% de bascule.")
        print("  Autrement dit, chacun des reglages testes serait detruit par")
        print("  un taux d aller-retour tres faible. Ce n est pas un mauvais")
        print("  reglage a trouver : c est le principe meme du stop rapproche")
        print("  qui ne tient pas sur ces donnees. Ne pas patcher C14.")
    print()
    g0, e0, n0, rf0, sv0 = evalue(lot, BE_PCT, BUF_PCT / BE_PCT)
    print("  Pour reference, la regle ACTUELLE (armement 0.08%, stop a")
    print("  0.004%%) : %d eligibles, %d refuses par C14, gain %.2f EUR."
          % (n0, rf0, g0))
    print("  Les refus sont le chiffre a retenir : c est la regle en vigueur,")
    print("  et elle ne s applique presque jamais.")

    # ------------------------------------------------------ 4. les reserves
    cadre("AVANT D EN FAIRE QUOI QUE CE SOIT")
    print("  1. Le gain est un PLAFOND. Le journal porte le pic de MFE,")
    print("     jamais les creux : on ne peut pas savoir combien de gagnants")
    print("     seraient passes par le stop avant de finir. C est pour ca")
    print("     que la colonne bascule existe, et c est elle qu il faut")
    print("     regarder en premier.")
    print("  2. Ni spread ni slippage. Les deux vont contre le resultat.")
    print("  3. Pas de trailing apres le premier cran -- ce qui va, lui,")
    print("     dans l autre sens.")
    print("  4. Le taux d aller-retour reel est mesurable, mais pas ici :")
    print("     il faudrait le chemin du prix, ou au minimum le MAE apres le")
    print("     pic. Tant qu il n est pas mesure, aucun de ces reglages ne")
    print("     doit partir en production autrement qu en OBSERVE.")
    print()
    print("  Et il y a un moyen de l observer sans rien risquer :")
    print("  c14_set_live(False) met la clause en mode observation -- elle")
    print("  journalise ce qu elle aurait bloque et laisse passer. Le meme")
    print("  interrupteur existe donc pour mesurer le cout du stop rapproche")
    print("  en conditions reelles, sur quelques seances, avant de trancher.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

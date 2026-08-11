# -*- coding: utf-8 -*-
"""
motif4.py -- qui sort par le stop broker, qui sort par le code, et pourquoi

  python motif4.py
  python motif4.py --bascule 2026-08-05 --fichier docs/rails_trades/tickets_rails.jsonl

CE QU EST LE MOTIF 4
    close_reason vient de history_deals_get -- c est le DEAL_REASON de MT5.
    3 = EXPERT (une ligne de Python a ferme la position), 4 = SL (le stop
    cote broker a ete touche), 5 = TP.

    Un "SL" a 91 pour cent de reussite n est pas un stop de perte : c est un
    trailing deja remonte en profit, que le prix vient toucher en retracant.
    MT5 le declare SL quand meme, parce que du point de vue du serveur c est
    un stop-loss -- peu importe de quel cote de l entree il se trouve.

    Le motif 4 n est donc pas une strategie qu on pourrait choisir. C est
    la trace de la seule facon de sortir qui ne demande a personne son avis :
    l ordre est deja chez le courtier, il part meme si le VPS est tombe.

CE QU ON A ETABLI LE 11/08
        motif 4  tendance +39,79 WR 91%  rendu 53%  |  range +29,64 WR 77%  58%
        motif 3  tendance  -6,19 WR 32%  rendu 103% |  range -23,60 WR 25% 163%

    Le motif 4 tient dans les deux regimes. Le motif 3 s effondre deux fois :
    il monte 36 pour cent moins haut, et rend 163 pour cent de ce qu il a
    atteint -- c est-a-dire qu il finit SOUS zero apres avoir culmine.

LES TROIS QUESTIONS, ET CE QUE CE SCRIPT PEUT VRAIMENT DIRE
    1. QUI produit du motif 4 ? Croisement motif x magic. Repond
       completement : chaque module a une signature de sortie.
    2. POURQUOI si peu ? Repond en partie. On voit quels modules ferment en
       code ; on ne voit pas si un stop etait pose au moment ou le code a
       ferme, parce que le journal ne porte pas le SL. C est la limite, et
       elle est signalee la ou elle compte.
    3. TOUTES les sorties pourraient-elles y passer ? Le script chiffre la
       borne haute -- ce que rapporteraient les tickets du motif 3 s ils
       capturaient la meme fraction de leur MFE que ceux du motif 4. C est
       une BORNE, pas une prevision : les tickets qui finissent en motif 3
       sont peut-etre precisement ceux ou le trailing ne s est jamais
       accroche. Le chiffre dit combien il y a a gagner, pas qu on le
       gagnera.

CE QU IL LIT
    De preference docs/rails_trades/tickets_rails.jsonl -- la sortie de
    rails_join.py -- qui porte en plus le biais des rails a l entree. A
    defaut, churn_trades*.jsonl, et les blocs rails sont alors vides.
"""
import argparse
import glob
import io
import json
import os
import sys

CANDIDATS = [os.path.join("docs", "rails_trades", "tickets_rails.jsonl"),
             os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
             os.path.join("docs", "churn_trades", "churn_trades.jsonl"),
             "churn_trades_archive.jsonl", "churn_trades.jsonl"]
NOMS = {"3": "3 EXPERT (code)", "4": "4 SL (stop broker)", "5": "5 TP",
        "6": "6 STOP OUT", "0": "0 CLIENT", "1": "1 MOBILE", "2": "2 WEB"}
BASCULE = "2026-08-05"
MINI = 30


def nombre(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def verdict(v):
    if isinstance(v, dict):
        for k in ("VERDICT", "verdict", "Verdict"):
            if v.get(k):
                return str(v[k]).strip().upper()
        return "?"
    return str(v).strip().upper() if v else "?"


def charger(exp):
    ch = exp or [p for p in CANDIDATS if os.path.isfile(p)]
    if not ch:
        for m in ("docs/*/churn_trades*.jsonl", "churn_trades*.jsonl"):
            ch = sorted(glob.glob(m))
            if ch:
                break
    if not ch:
        print("KO : aucun journal trouve. Utilise --fichier CHEMIN.")
        sys.exit(1)
    par = {}
    for f in ch:
        for l in io.open(f, encoding="utf-8-sig"):
            l = l.strip()
            if not l or l[0] != "{":
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ts = str(o.get("entry_ts") or "")
            pnl = nombre(o.get("pnl_eur"))
            tk = o.get("ticket")
            if len(ts) < 16 or pnl is None or tk is None or tk in par:
                continue
            cts = str(o.get("close_ts") or "")
            mg = nombre(o.get("magic"))
            par[tk] = {
                "jour": ts[:10],
                "hsortie": (cts[11:13] if len(cts) >= 16 else "??") + "h",
                "pnl": pnl,
                "mfe": nombre(o.get("mfe_eur")),
                "motif": str(o.get("close_reason")),
                "magic": ("M%d" % int(mg)) if mg else "M?",
                "actif": str(o.get("asset") or "?"),
                "churn": verdict(o.get("churn_entry")),
                "m1": str(o.get("rails_pos_m1") or "-"),
                "m5": str(o.get("rails_pos_m5") or "-"),
            }
    if not par:
        print("Aucun enregistrement exploitable.")
        sys.exit(1)
    print("journaux : %s" % ", ".join(os.path.basename(c) for c in ch))
    return list(par.values())


def part4(lot):
    """(part du motif 4 en %, N). La mesure centrale de tout ce fichier."""
    n = len(lot)
    if not n:
        return 0.0, 0
    return 100.0 * sum(1 for s in lot if s["motif"] == "4") / n, n


def capture(lot):
    """Fraction du MFE reellement encaissee, en %. Negatif = fini sous zero."""
    g = [s for s in lot if s["mfe"] is not None and s["mfe"] > 0]
    smfe = sum(s["mfe"] for s in g)
    if smfe <= 0:
        return 0.0
    return 100.0 * sum(s["pnl"] for s in g) / smfe


def bloc(titre, clef, av, dp, ordre=None, largeur=20):
    print()
    print("=" * 96)
    print("  " + titre)
    print("=" * 96)
    print("%-*s %26s %26s" % (largeur, "", "TENDANCE avant bascule",
                              "RANGE depuis bascule"))
    print("%-*s %7s %5s %8s %7s   %7s %5s %8s %7s"
          % (largeur, "", "%mot.4", "N", "EUR/tk", "capt.",
             "%mot.4", "N", "EUR/tk", "capt."))
    print("-" * 96)
    ga, gd = {}, {}
    for s in av:
        ga.setdefault(clef(s), []).append(s)
    for s in dp:
        gd.setdefault(clef(s), []).append(s)
    vus = False
    for c in (ordre if ordre is not None else sorted(set(ga) | set(gd))):
        ligne, vide = "%-*s" % (largeur, str(c)[:largeur]), True
        for g in (ga.get(c, []), gd.get(c, [])):
            if not g:
                ligne += "%27s" % "-"
                continue
            vide = False
            p, n = part4(g)
            ligne += "%6.0f%% %5d %8.2f %6.0f%%%s" % (
                p, n, sum(x["pnl"] for x in g) / n, capture(g),
                " ?" if n < MINI else "  ")
        if not vide:
            print(ligne)
            vus = True
    if not vus:
        print("  (aucune donnee -- le champ n est pas renseigne)")
    print("-" * 96)


def main():
    global MINI
    p = argparse.ArgumentParser()
    p.add_argument("--bascule", default=BASCULE)
    p.add_argument("--mini", type=int, default=MINI)
    p.add_argument("--fichier", nargs="*")
    a = p.parse_args()
    MINI = a.mini

    lot = charger(a.fichier)
    lot.sort(key=lambda s: s["jour"])
    av = [s for s in lot if s["jour"] < a.bascule]
    dp = [s for s in lot if s["jour"] >= a.bascule]

    print("=== SCALP-EA / LE MOTIF 4, LE STOP QUI N A BESOIN DE PERSONNE ===")
    print("%d tickets, %s -> %s" % (len(lot), lot[0]["jour"], lot[-1]["jour"]))
    print("capt. = fraction du MFE encaissee. Negatif = fini sous zero.")
    if not av or not dp:
        print("Un des deux compartiments est vide -- verifie --bascule.")
        return 1

    # ------------------------------------------------- repartition globale
    print()
    print("=" * 96)
    print("  REPARTITION DES MOTIFS")
    print("=" * 96)
    print("%-22s %8s %8s %10s %8s %8s"
          % ("motif", "N", "part", "total EUR", "EUR/tk", "capt."))
    print("-" * 96)
    for lab, sel in (("TENDANCE", av), ("RANGE", dp)):
        print("%s" % lab)
        for m in sorted(set(s["motif"] for s in sel)):
            g = [s for s in sel if s["motif"] == m]
            print("  %-20s %8d %7.0f%% %10.2f %8.2f %7.0f%%"
                  % (NOMS.get(m, "motif " + m), len(g),
                     100.0 * len(g) / len(sel), sum(s["pnl"] for s in g),
                     sum(s["pnl"] for s in g) / len(g), capture(g)))
    print("-" * 96)

    # --------------------------------------------------------- croisements
    bloc("PAR FAMILLE DE MAGIC -- quel module laisse le stop faire son travail",
         lambda s: s["magic"][:4], av, dp)

    mags = sorted(set(s["magic"] for s in lot),
                  key=lambda m: -sum(1 for s in lot if s["magic"] == m))
    bloc("PAR MAGIC ENTIER", lambda s: s["magic"], av, dp, ordre=mags[:22])

    bloc("PAR HEURE DE SORTIE", lambda s: s["hsortie"], av, dp,
         ordre=["%02dh" % h for h in range(24)] + ["??h"])

    bloc("PAR VERDICT CHURN A L ENTREE", lambda s: s["churn"], av, dp)

    bloc("PAR BIAIS DES RAILS M1 A L ENTREE", lambda s: s["m1"], av, dp)
    bloc("PAR BIAIS DES RAILS M5 A L ENTREE", lambda s: s["m5"], av, dp)

    bloc("PAR ACTIF", lambda s: s["actif"], av, dp)

    # ------------------------------------------------ evolution jour a jour
    print()
    print("=" * 96)
    print("  JOUR PAR JOUR -- la part du motif 4 se deplace-t-elle ?")
    print("=" * 96)
    print("%-12s %8s %8s %10s %8s" % ("jour", "N", "%motif4", "PnL", "capt."))
    print("-" * 96)
    for j in sorted(set(s["jour"] for s in lot)):
        g = [s for s in lot if s["jour"] == j]
        p4, n = part4(g)
        print("%-12s %8d %7.0f%% %10.2f %7.0f%%"
              % (j, n, p4, sum(s["pnl"] for s in g), capture(g)))
    print("-" * 96)

    # ---------------------------------------------------------- borne haute
    print()
    print("=" * 96)
    print("  ET SI TOUTES LES SORTIES PASSAIENT PAR LE MOTIF 4 ?")
    print("=" * 96)
    for lab, sel in (("TENDANCE", av), ("RANGE", dp)):
        q4 = [s for s in sel if s["motif"] == "4"]
        q3 = [s for s in sel if s["motif"] != "4"]
        if not q4 or not q3:
            continue
        c4 = capture(q4) / 100.0
        mfe3 = sum(s["mfe"] for s in q3 if s["mfe"] and s["mfe"] > 0)
        reel = sum(s["pnl"] for s in q3)
        print()
        print("  %s" % lab)
        print("    le motif 4 encaisse %.0f%% de son MFE" % (100.0 * c4))
        print("    les %d autres tickets ont atteint %+10.2f EUR au plus haut"
              % (len(q3), mfe3))
        print("    ils ont rendu                      %+10.2f EUR" % reel)
        print("    a la meme capture ils feraient     %+10.2f EUR" % (mfe3 * c4))
        print("    ecart                              %+10.2f EUR"
              % (mfe3 * c4 - reel))
    print()
    print("-" * 96)
    print("  C EST UNE BORNE HAUTE, PAS UNE PREVISION.")
    print("  Les tickets qui finissent hors motif 4 sont peut-etre justement")
    print("  ceux ou le trailing ne s est jamais accroche -- parce qu ils ne")
    print("  sont jamais montes assez pour l armer. Leur appliquer la capture")
    print("  des autres suppose qu ils leur ressemblent, ce que rien ici ne")
    print("  demontre. Le chiffre dit combien il y a a gagner, pas qu on le")
    print("  gagnera.")

    print()
    print("CE QUE CE JOURNAL NE PERMET PAS DE SAVOIR")
    print("  Il ne porte pas le stop-loss. On voit donc quels modules ferment")
    print("  en code, mais pas si un stop etait deja pose au moment ou le code")
    print("  a ferme. La question 'le closer a-t-il devance un stop qui aurait")
    print("  mieux fait' reste ouverte, et c est la plus importante des trois.")
    print("  Pour la trancher il faudrait journaliser sl au moment de la")
    print("  cloture -- une ligne dans churn_trade_logger.")
    print()
    print("  Une cellule suivie de ? compte moins de %d tickets." % MINI)
    return 0


if __name__ == "__main__":
    sys.exit(main())

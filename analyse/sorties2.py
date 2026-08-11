# -*- coding: utf-8 -*-
"""
sorties2.py -- le rendu, mesure correctement cette fois

  python sorties2.py
  python sorties2.py --bascule 2026-08-05 --seuil 20

CE QUE LA PREMIERE VERSION A RATE
    sorties.py a sorti le bon ordre de grandeur -- 405 tickets montes a
    +20 EUR ou plus et termines a zero ou en perte, 35 331 EUR laisses en
    route -- mais avec quatre defauts qu il faut corriger avant d en tirer
    quoi que ce soit.

    1. churn_entry est un DICTIONNAIRE, {'VERDICT': 'CHURN', ...}, pas une
       chaine. Le bloc churn est sorti en sept cents lignes illisibles.
       Corollaire qui compte davantage : ajouter churn_entry a CLEFS_CHURN
       dans oos_v9.py ne suffit pas, il faut en extraire VERDICT. Et le
       vocabulaire contient OK, que CHURN_VALIDES ne connait pas.

    2. close_reason est NUMERIQUE (3, 4, 5). On ne devine pas la table,
       donc on l imprime telle quelle avec son profil -- motif 3 perd,
       motif 4 gagne a 91 pour cent -- et on la nommera quand on aura lu
       le module qui ecrit ce journal.

    3. L heure affichee etait celle de l ENTREE. Impossible, donc, de
       localiser un evenement de sortie -- typiquement le break-even de
       15:27. close_ts est dans le journal ; il est utilise ici.

    4. Le rendu etait en euros absolus. 78 EUR rendus a 15h contre 38 le
       matin ne dit rien tant qu on ne sait pas si les tickets de 15h
       montent deux fois plus haut. La colonne qui compte est la PART du
       MFE rendue, et elle est ajoutee.

CE QUI EST NOUVEAU
    Un bloc jumeaux. Dans les vingt pires tickets du 11/08, quatorze
    etaient des paires M206/M207 : meme minute, meme actif, meme MFE au
    centime. Ce ne sont pas deux strategies qui se diversifient, c est une
    strategie en taille double, et chaque desastre est compte deux fois.
    Le bloc le chiffre au lieu de le supposer.

CE QU IL NE FAIT PAS
    Il ne touche a rien. Il lit un journal, il compte.
"""
import argparse
import io
import json
import os
import sys

NOMS = ["churn_trades_archive.jsonl", "churn_trades.jsonl",
        "rails_trades_archive.jsonl", "rails_trades.jsonl"]
DOSSIERS = [os.path.join("docs", "churn_trades"), r"docs\churn_trades",
            os.path.join("docs", "rails_trades"), r"docs\rails_trades",
            r"C:\ScalpExport\docs\churn_trades"]
BASCULE = "2026-08-05"
SEUIL = 20.0
MINI = 30


def sources(exp):
    if exp:
        return exp
    for d in DOSSIERS:
        t = [os.path.join(d, n) for n in NOMS
             if os.path.isfile(os.path.join(d, n))]
        if t:
            return t
    t = [n for n in NOMS if os.path.isfile(n)]
    if t:
        return t
    print("Aucun churn_trades*.jsonl trouve. Utilise --fichier CHEMIN.")
    sys.exit(1)


def nombre(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def verdict(v):
    """churn_entry est un dict {'VERDICT': ..., ...} -- on en sort VERDICT.

    Tolere aussi une chaine, au cas ou le format changerait.
    """
    if isinstance(v, dict):
        for k in ("VERDICT", "verdict", "Verdict"):
            if v.get(k):
                return str(v[k]).strip().upper()
        return "(dict sans VERDICT)"
    if v in (None, ""):
        return "(vide)"
    return str(v).strip().upper()


def charger(chemins):
    par = {}
    brut = 0
    for ch in chemins:
        for l in io.open(ch, encoding="utf-8-sig"):
            l = l.strip()
            if not l or l[0] != "{":
                continue
            brut += 1
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
                "jour": ts[:10], "hm": ts[11:16], "heure": ts[11:13],
                "hsortie": cts[11:13] if len(cts) >= 16 else "??",
                "mssortie": cts[11:16] if len(cts) >= 16 else "??:??",
                "pnl": pnl,
                "mfe": nombre(o.get("mfe_eur")),
                "mae": nombre(o.get("mae_eur")),
                "motif": str(o.get("close_reason")),
                "magic": ("M%d" % int(mg)) if mg else "M?",
                "actif": str(o.get("asset") or "?"),
                "sens": str(o.get("dir") or "?").strip().upper(),
                "churn": verdict(o.get("churn_entry")),
            }
    if not par:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        sys.exit(1)
    return list(par.values())


def stats(lot):
    n = len(lot)
    if not n:
        return None
    gagne = [s for s in lot if s["mfe"] is not None and s["mfe"] > 0]
    smfe = sum(s["mfe"] for s in gagne)
    rendu = smfe - sum(s["pnl"] for s in gagne)
    perdus = [s for s in lot
              if s["mfe"] is not None and s["mfe"] >= SEUIL and s["pnl"] <= 0]
    return {
        "n": n,
        "pnl": sum(s["pnl"] for s in lot),
        "wr": 100.0 * sum(1 for s in lot if s["pnl"] > 0) / n,
        "mfe_moy": smfe / len(gagne) if gagne else 0.0,
        "rendu": rendu,
        "rendu_moy": rendu / len(gagne) if gagne else 0.0,
        # La colonne qui compte : quelle PART de ce qui a ete atteint est
        # rendue. Un montant absolu confond "mal sorti" et "monte haut".
        "part": 100.0 * rendu / smfe if smfe > 0 else 0.0,
        "ng": len(gagne),
        "perdus": len(perdus),
        "perdus_mfe": sum(s["mfe"] for s in perdus),
        "perdus_pnl": sum(s["pnl"] for s in perdus),
    }


def bloc(titre, clef, av, dp, ordre=None, largeur=18):
    print()
    print("=" * 104)
    print("  " + titre)
    print("=" * 104)
    print("%-*s %30s %30s" % (largeur, "", "TENDANCE avant bascule",
                              "RANGE depuis bascule"))
    print("%-*s %8s %4s %4s %6s %6s   %8s %4s %4s %6s %6s"
          % (largeur, "", "EUR/tr", "N", "WR", "MFE", "rendu",
             "EUR/tr", "N", "WR", "MFE", "rendu"))
    print("-" * 104)
    ga, gd = {}, {}
    for s in av:
        ga.setdefault(clef(s), []).append(s)
    for s in dp:
        gd.setdefault(clef(s), []).append(s)
    for c in (ordre if ordre is not None else sorted(set(ga) | set(gd))):
        ligne = "%-*s" % (largeur, str(c)[:largeur])
        vide = True
        for g in (ga.get(c, []), gd.get(c, [])):
            st = stats(g)
            if st is None:
                ligne += "%31s" % "-"
                continue
            vide = False
            ligne += "%9.2f %4d %3.0f%% %6.1f %5.0f%%%s" % (
                st["pnl"] / st["n"], st["n"], st["wr"], st["mfe_moy"],
                st["part"], " ?" if st["n"] < MINI else "  ")
        if not vide:
            print(ligne)
    print("-" * 104)


def main():
    global SEUIL, MINI
    p = argparse.ArgumentParser()
    p.add_argument("--bascule", default=BASCULE)
    p.add_argument("--seuil", type=float, default=SEUIL)
    p.add_argument("--mini", type=int, default=MINI)
    p.add_argument("--fichier", nargs="*")
    a = p.parse_args()
    SEUIL, MINI = a.seuil, a.mini

    ch = sources(a.fichier)
    lot = charger(ch)
    lot.sort(key=lambda s: (s["jour"], s["hm"]))

    print("=== SCALP-EA / CE QUI A ETE ATTEINT, PUIS RENDU (v2) ===")
    print("fichiers : %s" % ", ".join(os.path.basename(c) for c in ch))
    print("%d tickets, %s -> %s" % (len(lot), lot[0]["jour"], lot[-1]["jour"]))
    k = sum(1 for s in lot if s["hsortie"] != "??")
    print("  close_ts exploitable sur %d tickets  %3.0f%%"
          % (k, 100.0 * k / len(lot)))
    print("  colonne MFE = MFE moyen des tickets passes en gain")
    print("  colonne rendu = PART du MFE rendue, en pour cent")

    av = [s for s in lot if s["jour"] < a.bascule]
    dp = [s for s in lot if s["jour"] >= a.bascule]
    if not av or not dp:
        print("\nUn des deux compartiments est vide -- verifie --bascule.")
        return 1

    for lab, sel in (("TENDANCE", av), ("RANGE   ", dp)):
        st = stats(sel)
        print()
        print("  %s  %d tickets  %+10.2f EUR  %+6.2f/ticket  WR %.0f%%"
              % (lab, st["n"], st["pnl"], st["pnl"] / st["n"], st["wr"]))
        print("            atteint %.2f EUR au plus haut sur %d tickets,"
              % (st["rendu"] + sum(s["pnl"] for s in sel
                                   if s["mfe"] is not None and s["mfe"] > 0),
                 st["ng"]))
        print("            rendu %.2f EUR, soit %.0f%% de ce qui etait atteint"
              % (st["rendu"], st["part"]))
        print("            gagnants perdus : %d tickets montes a +%.2f,"
              % (st["perdus"], st["perdus_mfe"]))
        print("            termines a %+.2f -- %.2f EUR laisses en route,"
              % (st["perdus_pnl"], st["perdus_mfe"] - st["perdus_pnl"]))
        print("            soit %.0f%% du resultat de la periode"
              % (100.0 * (st["perdus_mfe"] - st["perdus_pnl"])
                 / max(1.0, abs(st["pnl"]))))

    bloc("PAR MOTIF DE CLOTURE (codes bruts -- la table reste a trouver)",
         lambda s: "motif " + s["motif"], av, dp)

    bloc("PAR HEURE DE SORTIE -- ou le rendu se produit vraiment",
         lambda s: s["hsortie"] + "h", av, dp,
         ordre=["%02dh" % h for h in range(24)] + ["??h"])

    bloc("PAR HEURE D ENTREE -- pour comparaison",
         lambda s: s["heure"] + "h", av, dp,
         ordre=["%02dh" % h for h in range(24)])

    bloc("PAR FAMILLE DE MAGIC", lambda s: s["magic"][:4], av, dp)

    bloc("PAR VERDICT CHURN A L ENTREE", lambda s: s["churn"], av, dp)

    # ------------------------------------------------------------ jumeaux
    print()
    print("=" * 104)
    print("  LES JUMEAUX -- une strategie en taille double, ou deux strategies ?")
    print("=" * 104)
    for lab, sel in (("TENDANCE", av), ("RANGE   ", dp)):
        grp = {}
        for s in sel:
            grp.setdefault((s["jour"], s["hm"], s["actif"], s["sens"]),
                           []).append(s)
        doubles = [g for g in grp.values()
                   if len(set(x["magic"] for x in g)) > 1]
        nd = sum(len(g) for g in doubles)
        pd_ = sum(x["pnl"] for g in doubles for x in g)
        seuls = [g for g in grp.values()
                 if len(set(x["magic"] for x in g)) == 1]
        ns = sum(len(g) for g in seuls)
        ps = sum(x["pnl"] for g in seuls for x in g)
        print("  %s  %d ouvertures simultanees (meme minute, meme actif,"
              % (lab, len(doubles)))
        print("            meme sens, magics differents) = %d tickets, %.0f%%"
              % (nd, 100.0 * nd / max(1, len(sel))))
        print("            resultat %+10.2f EUR  %+6.2f/ticket"
              % (pd_, pd_ / nd if nd else 0.0))
        print("            le reste %+10.2f EUR sur %d tickets  %+6.2f/ticket"
              % (ps, ns, ps / ns if ns else 0.0))
    print("-" * 104)
    print("  Si la quasi-totalite des tickets sont apparies, les deux magics")
    print("  ne se diversifient pas : ils doublent la taille. Chaque perte")
    print("  est alors comptee deux fois, et la moitie de la flotte n apporte")
    print("  aucune decorrelation -- seulement du risque.")

    # ------------------------------------------------- les gagnants perdus
    print()
    print("=" * 104)
    print("  LES VINGT PLUS GROS GAGNANTS PERDUS -- MFE >= %.0f EUR, "
          "termines a zero ou en perte" % SEUIL)
    print("=" * 104)
    perdus = [s for s in lot
              if s["mfe"] is not None and s["mfe"] >= SEUIL and s["pnl"] <= 0]
    perdus.sort(key=lambda s: -(s["mfe"] - s["pnl"]))
    if not perdus:
        print("  aucun -- ce serait une excellente nouvelle, donc a verifier.")
    else:
        print("%-11s %6s %6s %-9s %-7s %8s %9s %9s %5s"
              % ("jour", "entree", "sortie", "magic", "actif", "MFE",
                 "final", "rendu", "motif"))
        print("-" * 104)
        for s in perdus[:20]:
            print("%-11s %6s %6s %-9s %-7s %8.2f %9.2f %9.2f %5s"
                  % (s["jour"], s["hm"], s["mssortie"], s["magic"],
                     s["actif"][:7], s["mfe"], s["pnl"],
                     s["mfe"] - s["pnl"], s["motif"]))
        print("-" * 104)
        print("  %d tickets au total, %.2f EUR laisses en route."
              % (len(perdus), sum(s["mfe"] - s["pnl"] for s in perdus)))

    print()
    print("COMMENT LIRE")
    print("  Une part rendue SUPERIEURE A 100%% n est pas une erreur : elle")
    print("  signifie qu en moyenne les positions ne se sont pas contentees de")
    print("  rendre leur gain, elles ont fini SOUS zero apres avoir culmine.")
    print("  C est le signal le plus severe du tableau.")
    print("  La colonne rendu est une PART du MFE, plus un montant : elle ne")
    print("  confond plus 'mal sorti' et 'monte haut'. Comparer les heures")
    print("  entre elles, pas la valeur absolue a zero -- personne ne sort au")
    print("  plus haut, et 0%% de rendu signifierait une sortie parfaite a")
    print("  chaque fois.")
    print("  Les gagnants perdus, eux, ne se discutent pas : un ticket monte")
    print("  a +%.0f puis termine negatif n a pas ete mal sorti, il n a pas" % SEUIL)
    print("  ete sorti.")
    print("  Une cellule suivie de ? compte moins de %d tickets." % MINI)
    print("  Le MFE vaut ce que vaut son echantillonnage par le module qui")
    print("  ecrit ce journal : un pic entre deux mesures n y figure pas, donc")
    print("  le rendu reel est plutot sous-estime.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

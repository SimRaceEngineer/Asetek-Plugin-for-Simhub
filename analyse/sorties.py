# -*- coding: utf-8 -*-
"""
sorties.py -- ce que le dispositif a atteint, puis rendu

  python sorties.py
  python sorties.py --bascule 2026-08-05 --seuil 20

CE QU ON CHERCHE
    Le 11/08, oos_v9 --champs a montre que churn_trades*.jsonl ne contient
    aucun champ rails -- mais qu il contient mieux, pour la question qui
    bloque depuis une semaine :

        mfe_eur, mfe_pts   l excursion la plus favorable atteinte
        mae_eur, mae_pts   la plus defavorable
        close_reason       comment la position est morte

    Aucune EA ne tourne sur MT5 : tout ce qui ferme, met a break-even ou
    deplace un stop est du Python. Une trentaine de modules ecrivent des
    stops sur les memes positions sans se consulter, et le 10/08 a 15:27
    trois stops deja verrouilles ont ete ramenes au prix d entree, 105,7
    points rendus.

    On a corrige preopen_protect, puis pose un arbitre unique en mode
    observation. Ce qu on n a jamais fait, c est CHIFFRER le probleme.
    Ce script le chiffre.

LA MESURE, ET SA LIMITE
    rendu = MFE atteint - resultat final, pour les tickets passes en gain.

    Ce n est PAS de l argent perdu : personne ne sort au plus haut, et
    viser le MFE serait viser l impossible. Un rendu nul signifierait une
    sortie parfaite a chaque fois, ce qui n existe pas.

    Ce qui se lit, c est la COMPARAISON : entre motifs de cloture, entre
    heures, entre regimes. Si une heure rend deux fois plus que ses
    voisines, ou si un motif rend deux fois plus qu un autre a MFE egal,
    l anomalie est la, et elle est mecanique.

LE CHIFFRE QUI TRANCHE
    Les "gagnants perdus" : les tickets qui ont atteint au moins SEUIL
    euros de gain latent et qui finissent a zero ou en perte. Ceux-la ne
    se discutent pas. Un ticket qui monte a +40 puis termine a -15 n a pas
    ete mal sorti, il n a pas ete sorti du tout.

POURQUOI SCINDER AU 05/08
    Le 28/07-04/08 est une jambe de tendance, le 05/08-11/08 un range. Un
    trailing qui se comporte bien en tendance peut etre exactement le
    mauvais outil en range, ou chaque poussee retombe. Melanger les deux
    periodes moyennerait ces deux comportements et n en decrirait aucun.

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
SEUIL = 20.0     # euros de gain latent atteint : au-dela, un ticket perdu compte
MINI = 30        # sous ce nombre de tickets, une cellule ne se lit pas


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
    print("Aucun churn_trades*.jsonl ni rails_trades*.jsonl trouve.")
    print("Utilise --fichier suivi du chemin complet.")
    sys.exit(1)


def nombre(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


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
            mg = nombre(o.get("magic"))
            par[tk] = {
                "jour": ts[:10], "heure": ts[11:13], "hm": ts[11:16],
                "pnl": pnl,
                "mfe": nombre(o.get("mfe_eur")),
                "mae": nombre(o.get("mae_eur")),
                "mfe_pts": nombre(o.get("mfe_pts")),
                "motif": str(o.get("close_reason") or "(vide)").strip().upper(),
                "magic": ("M%d" % int(mg)) if mg else "M?",
                "actif": str(o.get("asset") or "?"),
                "sens": str(o.get("dir") or "?").strip().upper(),
                "churn": str(o.get("churn_entry") or "?").strip().upper(),
                "live": o.get("entry_captured_live"),
            }
    if not par:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        sys.exit(1)
    return list(par.values())


def rendu(s):
    """MFE atteint moins resultat final, pour les tickets passes en gain.

    None si le ticket n est jamais passe positif : son resultat parle de
    l entree, pas de la sortie, et le melanger fausserait la mesure.
    """
    if s["mfe"] is None or s["mfe"] <= 0:
        return None
    return s["mfe"] - s["pnl"]


def stats(lot):
    n = len(lot)
    if not n:
        return None
    p = sum(s["pnl"] for s in lot)
    w = sum(1 for s in lot if s["pnl"] > 0)
    r = [rendu(s) for s in lot]
    r = [x for x in r if x is not None]
    perdus = [s for s in lot
              if s["mfe"] is not None and s["mfe"] >= SEUIL and s["pnl"] <= 0]
    return {"n": n, "pnl": p, "wr": 100.0 * w / n,
            "rendu": sum(r), "rendu_moy": sum(r) / len(r) if r else 0.0,
            "nr": len(r),
            "perdus": len(perdus),
            "perdus_mfe": sum(s["mfe"] for s in perdus),
            "perdus_pnl": sum(s["pnl"] for s in perdus)}


def duo(lab, a, b, largeur=20):
    out = "%-*s" % (largeur, str(lab)[:largeur])
    for lot in (a, b):
        st = stats(lot)
        if st is None:
            out += "%28s" % "-"
            continue
        out += "%8.2f %4d %3.0f%% %8.2f%s" % (
            st["pnl"] / st["n"], st["n"], st["wr"], st["rendu_moy"],
            " ?" if st["n"] < MINI else "  ")
    return out


def bloc(titre, clef, av, dp, ordre=None, largeur=20):
    print()
    print("=" * 100)
    print("  " + titre)
    print("=" * 100)
    print("%-*s %27s %27s" % (largeur, "", "TENDANCE avant bascule",
                              "RANGE depuis bascule"))
    print("%-*s %8s %4s %4s %8s   %8s %4s %4s %8s"
          % (largeur, "", "EUR/tr", "N", "WR", "rendu", "EUR/tr", "N", "WR",
             "rendu"))
    print("-" * 100)
    ga, gd = {}, {}
    for s in av:
        ga.setdefault(clef(s), []).append(s)
    for s in dp:
        gd.setdefault(clef(s), []).append(s)
    for c in (ordre if ordre is not None else sorted(set(ga) | set(gd))):
        if not ga.get(c) and not gd.get(c):
            continue
        print(duo(c, ga.get(c, []), gd.get(c, []), largeur))
    print("-" * 100)


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

    print("=== SCALP-EA / CE QUI A ETE ATTEINT, PUIS RENDU ===")
    print("fichiers : %s" % ", ".join(os.path.basename(c) for c in ch))
    print("%d tickets, %s -> %s" % (len(lot), lot[0]["jour"], lot[-1]["jour"]))
    for nom, cle in (("mfe_eur", "mfe"), ("mae_eur", "mae"),
                     ("close_reason", "motif")):
        k = sum(1 for s in lot
                if s[cle] is not None and s[cle] != "(vide)")
        print("  %-14s renseigne sur %5d tickets  %3.0f%%"
              % (nom, k, 100.0 * k / len(lot)))
    live = sum(1 for s in lot if s["live"])
    print("  %-14s vrai sur     %5d tickets  %3.0f%%"
          % ("captured_live", live, 100.0 * live / len(lot)))
    if live and live < len(lot):
        print("  Les entrees non capturees en direct ont un MFE reconstitue :")
        print("  il peut etre moins fidele. A garder en tete si la proportion")
        print("  differe entre les deux periodes.")

    av = [s for s in lot if s["jour"] < a.bascule]
    dp = [s for s in lot if s["jour"] >= a.bascule]
    if not av or not dp:
        print()
        print("Un des deux compartiments est vide -- verifie --bascule.")
        return 1

    for lab, sel in (("TENDANCE", av), ("RANGE   ", dp)):
        st = stats(sel)
        print()
        print("  %s  %d tickets  %+9.2f EUR  %+6.2f/ticket  WR %.0f%%"
              % (lab, st["n"], st["pnl"], st["pnl"] / st["n"], st["wr"]))
        print("            rendu total %9.2f EUR sur %d tickets passes en gain"
              % (st["rendu"], st["nr"]))
        print("            gagnants perdus : %d tickets montes a +%.2f au total,"
              % (st["perdus"], st["perdus_mfe"]))
        print("            termines a %+.2f -- soit %.2f EUR laisses en route"
              % (st["perdus_pnl"], st["perdus_mfe"] - st["perdus_pnl"]))

    bloc("PAR MOTIF DE CLOTURE -- comment les positions meurent",
         lambda s: s["motif"], av, dp)

    bloc("PAR HEURE -- ou se concentre le rendu",
         lambda s: s["heure"] + "h", av, dp,
         ordre=["%02dh" % h for h in range(24)])

    bloc("PAR FAMILLE DE MAGIC", lambda s: s["magic"][:4], av, dp)

    bloc("PAR VERDICT CHURN A L ENTREE", lambda s: s["churn"], av, dp)

    # -------------------------------------------------- les gagnants perdus
    print()
    print("=" * 100)
    print("  LES VINGT PLUS GROS GAGNANTS PERDUS -- MFE >= %.0f EUR, "
          "termines a zero ou en perte" % SEUIL)
    print("=" * 100)
    perdus = [s for s in lot
              if s["mfe"] is not None and s["mfe"] >= SEUIL and s["pnl"] <= 0]
    perdus.sort(key=lambda s: -(s["mfe"] - s["pnl"]))
    if not perdus:
        print("  aucun -- ce qui serait une excellente nouvelle, donc a verifier.")
    else:
        print("%-11s %6s %-9s %-8s %9s %9s %9s %-14s"
              % ("jour", "heure", "magic", "actif", "MFE", "final", "rendu",
                 "motif"))
        print("-" * 100)
        for s in perdus[:20]:
            print("%-11s %6s %-9s %-8s %9.2f %9.2f %9.2f %-14s"
                  % (s["jour"], s["hm"], s["magic"], s["actif"][:8],
                     s["mfe"], s["pnl"], s["mfe"] - s["pnl"], s["motif"][:14]))
        print("-" * 100)
        print("  %d tickets concernes au total, %.2f EUR laisses en route."
              % (len(perdus), sum(s["mfe"] - s["pnl"] for s in perdus)))

    print()
    print("COMMENT LIRE")
    print("  Le rendu n est pas une perte : personne ne sort au plus haut, et")
    print("  un rendu nul signifierait une sortie parfaite a chaque fois. Ce")
    print("  qui se lit est la COMPARAISON entre motifs, entre heures, entre")
    print("  regimes. Une heure qui rend le double de ses voisines a MFE")
    print("  comparable, c est une anomalie mecanique, pas du marche.")
    print("  Les gagnants perdus, eux, ne se discutent pas : un ticket monte")
    print("  a +%.0f puis termine negatif n a pas ete mal sorti, il n a pas" % SEUIL)
    print("  ete sorti.")
    print("  Une cellule suivie de ? compte moins de %d tickets." % MINI)
    print("  Enfin le MFE est mesure par le module qui ecrit ce journal : il")
    print("  vaut ce que vaut son echantillonnage. Un pic entre deux mesures")
    print("  n y figure pas, donc le rendu reel est plutot sous-estime.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

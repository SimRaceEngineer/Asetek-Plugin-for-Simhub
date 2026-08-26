#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_reverse_tous_motifs.py -- tous les motifs, et le 207 repare.

DEUX DEFAUTS, UNE SEULE CAUSE
-----------------------------
1. La colonne 207 de l autopsie n etait pas comparable a celle du 206.
   Le 207 solde en deux fois, et seul le DERNIER morceau porte le motif
   REVERSE : la colonne ne montrait que le reliquat. La preuve est
   arithmetique -- l A/B apparie donnait REVERSE a -1703 cote 207,
   l autopsie affichait -4682. L ecart, ce sont les premiers morceaux.

   Consequence plus sournoise : le MFE d un second morceau est mesure
   sur un segment tronque, qui commence apres une prise partielle. Il
   sort artificiellement bas, et gonfle la part de MORT-NES du 207.
   Le diagnostic lui-meme etait fausse.

2. L asymetrie achat / vente ne se voyait que sur REVERSE. Si elle se
   retrouve sur TOUS les motifs, ce n est plus un accident de
   mecanisme mais un biais directionnel du papier entier.

La fusion des morceaux regle les deux : elle rend au 207 son resultat
complet, son vrai MFE, et permet de lever le filtre sur le motif sans
compter deux fois les memes entrees.

CE QUE LA FUSION FAIT, ET CE QU ELLE SUPPOSE
    Cle (bras, actif, horizon, instant d ouverture). Les resultats se
    somment. Le MFE devient le MAXIMUM des morceaux et le MAE leur
    MINIMUM -- les extremes du chemin complet, pas ceux d un segment.
    Le motif et la duree sont ceux du DERNIER morceau, celui qui
    solde : la duree est mesuree depuis l ouverture, donc le dernier
    la porte deja en entier.

    Le nombre d entrees fusionnees est affiche. Une transformation des
    donnees doit se voir.

--motif TOUS
    Lève le filtre. Deux tableaux s ajoutent alors : PAR MOTIF et
    MOTIF x SENS -- celui qui dira si l asymetrie traverse les
    mecanismes ou n appartient qu a l un d eux.

USAGE
-----
    python patch_reverse_tous_motifs.py                <- simulation
    python patch_reverse_tous_motifs.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\reverse_autopsie.py"
SUFFIXE_BAK = ".bak_motifs"
MARQUEUR = "FUSION_V1"

A1 = '''            if o.get("quoi") != "TRADE" or o.get("motif") != motif:
                continue'''
B1 = '''            if o.get("quoi") != "TRADE":
                continue
            if motif and o.get("motif") != motif:
                continue'''

A2 = '''def rangs(d):
    return [(k, d[k]) for k in sorted(d, key=str)]'''
B2 = '''def rangs(d):
    return [(k, d[k]) for k in sorted(d, key=str)]


def fusionne(T):
    """FUSION_V1 -- (trades fusionnes, nombre d entrees en plusieurs
    morceaux).

    Un bras peut solder une entree en DEUX FOIS. Sans fusion, seul le
    dernier morceau portait le motif de sortie, et son MFE etait
    mesure sur un segment qui commence APRES une prise partielle : il
    sortait artificiellement bas et gonflait la part de mort-nes. Le
    diagnostic lui-meme etait fausse.

    Les resultats se somment. Le MFE devient le MAXIMUM des morceaux
    et le MAE leur MINIMUM : les extremes du chemin complet, pas ceux
    d un segment. Le motif et la duree viennent du DERNIER morceau --
    la duree est comptee depuis l ouverture, donc il la porte deja en
    entier."""
    par = {}
    for o in T:
        cle = (str(o.get("bras")), o.get("actif"), o.get("mn"),
               o.get("ouvert"))
        par.setdefault(cle, []).append(o)
    out, coupes = [], 0
    for cle, recs in par.items():
        if len(recs) == 1:
            out.append(recs[0])
            continue
        coupes += 1
        recs = sorted(recs, key=lambda x: str(x.get("ts", "")))
        d = dict(recs[-1])
        d["eur"] = sum(float(x.get("eur", 0.0)) for x in recs)
        d["points"] = sum(float(x.get("points", 0.0)) for x in recs)
        d["mfe"] = max(float(x.get("mfe", 0.0)) for x in recs)
        d["mae"] = min(float(x.get("mae", 0.0)) for x in recs)
        d["parts"] = len(recs)
        out.append(d)
    return out, coupes'''

A3 = '''    T, lus, casse = lis(a.trades, a.motif, depuis)
    if T is None:
        print("introuvable : %s" % a.trades)
        return 2
    txt = rendu_txt(T, a.motif, lus, casse, depuis)'''
B3 = '''    motif = None if a.motif.upper() in ("TOUS", "TOUT", "*") else a.motif
    T, lus, casse = lis(a.trades, motif, depuis)
    if T is None:
        print("introuvable : %s" % a.trades)
        return 2
    T, coupes = fusionne(T)
    txt = rendu_txt(T, motif or "TOUS", lus, casse, depuis, coupes)'''

A4 = "def rendu_txt(T, motif, lus, casse, depuis):"
B4 = "def rendu_txt(T, motif, lus, casse, depuis, coupes=0):"

A5 = '''    L += ["  MORT-NE   MFE < %.0f %% de la perte. Le trade n a jamais"
          % (100 * SEUIL_MORT),'''
B5 = '''    L += ["  fusionnees : %d entrees soldees en plusieurs morceaux," % coupes,
          "            resultats sommes, MFE = max des morceaux, MAE =",
          "            min. Sans ca le MFE d un second morceau, mesure",
          "            apres une prise partielle, sortait trop bas et",
          "            gonflait la part de mort-nes.",
          "",
          "  MORT-NE   MFE < %.0f %% de la perte. Le trade n a jamais"
          % (100 * SEUIL_MORT),'''

A6 = '''    L += bloc("PAR CRENEAU",
              rangs(groupe(T, lambda o: o.get("creneau") or "?")), "creneau")'''
B6 = '''    L += bloc("PAR CRENEAU",
              rangs(groupe(T, lambda o: o.get("creneau") or "?")), "creneau")
    if len(set(str(o.get("motif")) for o in T)) > 1:
        L += bloc("PAR MOTIF",
                  rangs(groupe(T, lambda o: o.get("motif") or "?")), "motif")
        L += bloc("MOTIF x SENS -- l asymetrie traverse-t-elle les"
                  " mecanismes ?",
                  rangs(groupe(T, lambda o: "%s %s"
                               % (o.get("motif"), sens_mot(o.get("sens"))))),
                  "motif x sens")'''

A7 = '''    txt = rendu_txt(T, a.motif, lus, casse, depuis)
    if not a.html_seul:
        print(txt)'''

A8 = '''    io.open(h, "w", encoding="utf-8", newline="").write(
        page(T, a.motif, lus, casse, depuis, txt))'''
B8 = '''    io.open(h, "w", encoding="utf-8", newline="").write(
        page(T, motif or "TOUS", lus, casse, depuis, txt))'''

A9 = '''            ("Par creneau",
             rangs(groupe(T, lambda x: x.get("creneau") or "?")), "creneau"),'''
B9 = '''            ("Par creneau",
             rangs(groupe(T, lambda x: x.get("creneau") or "?")), "creneau"),
            ("Par motif",
             rangs(groupe(T, lambda x: x.get("motif") or "?")), "motif"),
            ("Motif &times; sens &mdash; l asymetrie traverse-t-elle les"
             " mecanismes ?",
             rangs(groupe(T, lambda x: "%s %s" % (x.get("motif"),
                                                  sens_mot(x.get("sens"))))),
             "motif x sens"),'''

REMPL = ((A1, B1, "le filtre sur le motif"),
         (A2, B2, "rangs(), ou s insere fusionne()"),
         (A3, B3, "l appel a lis() dans main()"),
         (A4, B4, "la signature de rendu_txt"),
         (A5, B5, "l en-tete des definitions"),
         (A6, B6, "le tableau PAR CRENEAU du texte"),
         (A8, B8, "l ecriture du HTML"),
         (A9, B9, "le tableau Par creneau de la page"))


def lire(chemin):
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        return f.read()


def applique(s):
    for a, _, quoi in REMPL:
        if s.count(a) != 1:
            return None, "%s attendu 1 fois, trouve %d" % (quoi, s.count(a))
    if s.count(A7) != 1:
        return None, "l appel a rendu_txt attendu 1 fois"
    for a, b, _ in REMPL:
        s = s.replace(a, b, 1)
    return s, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 68)
    print("patch_reverse_tous_motifs -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 68)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))
    if MARQUEUR in s:
        print("")
        print("Deja pose : la fusion des morceaux est en place.")
        return 0

    neuf, err = applique(s)
    if neuf is None:
        print("")
        print("REFUS : %s." % err)
        return 1
    print("        les huit ancres uniques.")
    print("")
    print("a faire :")
    print("   + fusionne() : un trade solde en deux fois redevient UN")
    print("     trade. Resultats sommes, MFE = max, MAE = min.")
    print("     Sans ca le MFE du second morceau sortait trop bas et")
    print("     gonflait la part de mort-nes -- le diagnostic etait")
    print("     fausse, pas seulement les montants.")
    print("   + --motif TOUS leve le filtre")
    print("   + deux tableaux : PAR MOTIF et MOTIF x SENS")
    print("   + le nombre d entrees fusionnees est affiche")

    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer.")
        return 0

    bak = a.cible + SUFFIXE_BAK
    if not os.path.exists(bak):
        shutil.copy2(a.cible, bak)
        print("")
        print("sauvegarde : %s" % bak)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    print("ecrit : %s" % a.cible)

    relu = lire(a.cible)
    manques = [x for x in (MARQUEUR, "def fusionne(", "MOTIF x SENS",
                           "TOUS", "coupes") if x not in relu]
    if manques:
        print("relu  : INCOMPLET, manque %s -- RESTAURER %s"
              % (", ".join(manques), bak))
        return 1
    try:
        compile(relu, a.cible, "exec")
        print("relu  : les cinq marques y sont, et le fichier compile.")
    except SyntaxError as e:
        print("relu  : ERREUR DE SYNTAXE ligne %s -- RESTAURER %s"
              % (e.lineno, bak))
        return 1

    print("")
    print("-" * 68)
    print("  python reverse_autopsie.py                  REVERSE, repare")
    print("  python reverse_autopsie.py --motif TOUS     tous les motifs")
    print("")
    print("Le controle : la colonne 207 doit maintenant retrouver le")
    print("-1703 de l A/B sur REVERSE. Si elle affiche encore -4682, la")
    print("fusion n a pas pris.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

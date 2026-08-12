# -*- coding: utf-8 -*-
"""
x60_oos.py -- le x60 tient-il sur des donnees qui ne l ont pas fait naitre ?

  python x60_oos.py
  python x60_oos.py --setup 60 --coupure 2026-08-04
  python x60_oos.py --depuis 2026-07-21 --detail

POURQUOI CE FICHIER EXISTE

    Le setup 60 a ete REMARQUE dans les donnees, puis mesure dans les
    memes donnees. C est le peche originel : sur trente magics, il y en
    a forcement un qui sort devant, et il sortira devant meme si tout
    est du bruit. +31 EUR/ticket contre -2.79 pour le reste ne prouve
    donc rien tant que le chiffre n a pas ete refait ailleurs.

    Ce module coupe le corpus en deux dans le temps et refait les
    memes mesures de chaque cote. La premiere moitie est celle qui a
    servi a trouver l hypothese ; la seconde ne l a jamais vue.

    COUPURE CHRONOLOGIQUE, PAS ALEATOIRE. Deux tickets de la meme
    seance partagent le meme marche : les tirer au hasard melangerait
    les deux moities et ferait passer la fuite pour une confirmation.

LES QUATRE TESTS, ET CE QUE CHACUN PEUT INFIRMER

    1. LE SETUP, DES DEUX COTES
       EUR/ticket du setup vise contre le reste, sur A puis sur B. Si
       l ecart s effondre en B, l edge etait un artefact de A.

    2. LA SELECTION A L AVEUGLE -- le test le plus dur
       On oublie le x60. On classe TOUS les setups sur A, on prend le
       meilleur, et on regarde ce qu il fait en B. Puis le deuxieme, le
       troisieme. Si « meilleur en A » ne dit rien de B, alors la
       methode qui a designe le x60 ne vaut rien -- y compris quand
       elle designe le x60. C est le seul test qui juge la facon de
       chercher, et pas seulement la trouvaille.

    3. LA CONCENTRATION
       Part du gain portee par les trois meilleures fenetres, et par
       les trois meilleurs jours. Sur le corpus complet, 3 fenetres sur
       15 portaient 92 % du gain attribue au x60. Une moyenne batie sur
       trois episodes n est pas une moyenne, c est trois episodes.

    4. LES SIX CELLULES
       actif x bras : 3 x 2 = 6 lignes independantes. Six lignes
       positives des deux cotes vaudraient plus que n importe quelle
       moyenne d ensemble. Deux ou trois, non.

CE QU IL NE FAIT PAS

    Aucune simulation, aucun ordre, aucune regle d entree. Il ne sait
    pas POURQUOI le x60 entre -- ce code n est pas ici et n a jamais
    ete lu. Il mesure ce que les tickets ont fait, rien d autre.

    Et il ne conclut pas sous MINI tickets ou MINI_FEN fenetres par
    moitie : il ecrit alors ce qui manque, et s arrete la.

LECTURE SEULE. Ecrit panels/x60_oos.txt.
"""
import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

try:
    import horloge_regime as H
except ImportError:
    print("KO : horloge_regime.py introuvable a cote de ce script.")
    print("Il porte le chargement et le decoupage en fenetres. Le")
    print("recopier ici produirait une deuxieme lecture du meme fichier,")
    print("donc des chiffres incomparables avec familles.py.")
    sys.exit(1)

ACTIF_CODE = {"1": "US30", "2": "US500", "3": "US100"}
MINI = 20             # tickets par moitie sous lesquels on ne conclut pas
MINI_FEN = 8          # fenetres par moitie sous lesquelles on ne conclut pas
TETE = 3              # « les trois meilleures », pour la concentration
DEST = os.path.join(_ICI, "panels")
LARG = 100

RE_MAGIC = re.compile(r"^M(\d+)$")


def decomposer(magic):
    m = RE_MAGIC.match(str(magic))
    if not m or len(m.group(1)) != 6:
        return None, None, None
    d = m.group(1)
    return d[:3], ACTIF_CODE.get(d[3]), d[4:]


def agrege(lot):
    n = len(lot)
    eur = sum(s["pnl"] for s in lot if s["pnl"] is not None)
    w = sum(1 for s in lot if (s["pnl"] or 0) > 0)
    return n, eur, (eur / n if n else 0.0), (100.0 * w / n if n else 0.0)


def f(x, n=2):
    return "-" if x is None else ("%.*f" % (n, x))


def fenetres_de(lot, cible):
    """Les fenetres de H, avec qui allume. Meme decoupage que familles.py :
    deux modules qui compteraient les fenetres differemment donneraient
    deux verites sur le meme corpus."""
    out = []
    for jour in sorted(set(s["jour"] for s in lot)):
        duj = [s for s in lot if s["jour"] == jour]
        ech = H.echantillons(duj, jour, H.FENETRE, 1)
        if not ech:
            continue
        for m0, m1, _e, _pa in H.intervalles(ech):
            d, eur = H.chiffres(duj, jour, m0, m1)
            if len(d) < 3:
                continue
            prem = min(d, key=lambda s: s["ts"])
            out.append({"jour": jour, "m0": m0, "m1": m1, "eur": eur,
                        "tk": len(d), "d": d, "prem": prem["magic"],
                        "allume": prem.get("setup") == cible,
                        "present": any(s.get("setup") == cible for s in d)})
    return out


def concentration(valeurs, tete=TETE):
    """(part des `tete` plus grosses contributions positives, total).
    Renvoie None si le total est nul ou negatif -- une part de rien n a
    pas de sens, et l afficher quand meme donnerait un pourcentage qui
    impressionne sans rien mesurer."""
    total = sum(valeurs)
    if total <= 0:
        return None, total
    haut = sum(sorted(valeurs, reverse=True)[:tete])
    return 100.0 * haut / total, total


def bloc_setup(L, nom, lot, cible):
    """Le setup vise contre le reste, sur une moitie."""
    fam = [s for s in lot if s.get("setup") == cible]
    aut = [s for s in lot if s.get("setup") != cible]
    nf, ef, pf, wf = agrege(fam)
    na, ea, pa, wa = agrege(aut)
    L.append("%-22s %7d %12.2f %11.2f %6.0f%%   |   %7d %11.2f %6.0f%%"
             % (nom, nf, ef, pf, wf, na, pa, wa))
    return {"n": nf, "eur": ef, "par": pf, "wr": wf,
            "n_autre": na, "par_autre": pa, "ecart": pf - pa}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--depuis")
    p.add_argument("--setup", default="60")
    p.add_argument("--coupure", help="AAAA-MM-JJ ; defaut = mediane des jours")
    p.add_argument("--detail", action="store_true")
    p.add_argument("--dest", default=DEST)
    a = p.parse_args()

    chemins = a.fichier or H.O.sources(None)
    lot, brut = H.charger(chemins)
    if not lot:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        return 1
    if a.depuis:
        lot = [s for s in lot if s["jour"] >= a.depuis]
    if not lot:
        print("Aucun ticket sur la periode demandee.")
        return 1

    for s in lot:
        bras, _att, setup = decomposer(s["magic"])
        s["bras"], s["setup"] = bras, setup

    cible = a.setup
    jours = sorted(set(s["jour"] for s in lot))

    # La coupure tombe entre deux SEANCES, jamais au milieu de l une :
    # une seance a cheval mettrait les memes minutes des deux cotes.
    if a.coupure:
        coupure = a.coupure
    else:
        coupure = jours[len(jours) // 2]
    A = [s for s in lot if s["jour"] < coupure]
    B = [s for s in lot if s["jour"] >= coupure]

    L = []
    L.append("=" * LARG)
    L.append("  x%s HORS ECHANTILLON -- la meme mesure, sur des jours qui"
             " ne l ont pas fait naitre" % cible)
    L.append("=" * LARG)
    L.append("%d tickets, %s -> %s" % (len(lot), jours[0], jours[-1]))
    L.append("coupure au %s -- A : %d tickets sur %d jours, B : %d sur %d"
             % (coupure, len(A), len(set(s["jour"] for s in A)),
                len(B), len(set(s["jour"] for s in B))))
    L.append("")
    if not A or not B:
        L.append("  UNE DES DEUX MOITIES EST VIDE. La coupure %s tombe hors"
                 % coupure)
        L.append("  du corpus. Rien ne peut etre teste ainsi.")
        for l in L:
            print(l)
        return 1

    L.append("  A = ce qui a fait naitre l hypothese. B ne l a jamais vue.")
    L.append("  La coupure est CHRONOLOGIQUE : deux tickets de la meme")
    L.append("  seance partagent le meme marche, les tirer au hasard")
    L.append("  melangerait les moities et ferait passer la fuite pour une")
    L.append("  confirmation.")
    L.append("")

    # ------------------------------------------------ 1. le setup vise
    L.append("=" * LARG)
    L.append("  1. LE SETUP %s DES DEUX COTES" % cible)
    L.append("=" * LARG)
    L.append("%-22s %7s %12s %11s %7s   |   %7s %11s %7s"
             % ("", "N", "EUR", "EUR/tk", "WR", "N", "EUR/tk", "WR"))
    L.append("%-22s %7s %12s %11s %7s   |   %s"
             % ("", "", "-- le setup %s --" % cible, "", "",
                "-------- tout le reste --------"))
    L.append("-" * LARG)
    ra = bloc_setup(L, "A  avant %s" % coupure, A, cible)
    rb = bloc_setup(L, "B  depuis %s" % coupure, B, cible)
    L.append("-" * LARG)

    if ra["n"] < MINI or rb["n"] < MINI:
        L.append("  PAS DE VERDICT : %d tickets x%s en A, %d en B, minimum"
                 % (ra["n"], cible, rb["n"]))
        L.append("  %d de chaque cote. Un ecart calcule sur moins que ca se"
                 % MINI)
        L.append("  retourne avec deux trades.")
    else:
        L.append("  ecart au reste : %+.2f EUR/ticket en A, %+.2f en B."
                 % (ra["ecart"], rb["ecart"]))
        if rb["ecart"] <= 0:
            L.append("  EN B, L EDGE A DISPARU. Le setup %s n y fait pas"
                     % cible)
            L.append("  mieux que le reste du corpus. Ce qui a ete vu en A")
            L.append("  etait un artefact de A -- c est le resultat que ce")
            L.append("  fichier existe pour pouvoir annoncer.")
        elif rb["ecart"] < ra["ecart"] / 2.0:
            L.append("  L edge SURVIT en B mais divise par plus de deux.")
            L.append("  Une partie de ce qu on voyait en A venait du fait")
            L.append("  qu on avait cherche dans A. Ce qui reste est peut-")
            L.append("  etre reel ; ce n est pas la taille annoncee.")
        else:
            L.append("  L edge tient en B a la meme echelle qu en A. C est")
            L.append("  le seul cas ou le chiffre du corpus complet peut")
            L.append("  etre cite sans precaution particuliere.")
    L.append("")

    # ------------------------------- 2. la selection a l aveugle
    L.append("=" * LARG)
    L.append("  2. LA SELECTION A L AVEUGLE -- on juge la METHODE")
    L.append("=" * LARG)
    L.append("  On oublie le x%s. On classe tous les setups sur A, puis on"
             % cible)
    L.append("  regarde ce que les premiers de A font en B.")
    L.append("")
    pa_s, pb_s = defaultdict(list), defaultdict(list)
    for s in A:
        pa_s[s["setup"] or "hors format"].append(s)
    for s in B:
        pb_s[s["setup"] or "hors format"].append(s)
    classe = sorted(((k, v) for k, v in pa_s.items() if len(v) >= MINI),
                    key=lambda kv: -agrege(kv[1])[2])
    if not classe:
        L.append("  Aucun setup n atteint %d tickets en A." % MINI)
    else:
        L.append("%-16s %6s %11s %8s   |   %6s %11s %8s   %s"
                 % ("setup", "N (A)", "EUR/tk A", "rang A",
                    "N (B)", "EUR/tk B", "rang B", ""))
        L.append("-" * LARG)
        classe_b = sorted(((k, v) for k, v in pb_s.items() if len(v) >= MINI),
                          key=lambda kv: -agrege(kv[1])[2])
        rang_b = {k: i + 1 for i, (k, _v) in enumerate(classe_b)}
        for i, (k, v) in enumerate(classe):
            vb = pb_s.get(k, [])
            nb, _eb, pb_, _wb = agrege(vb)
            marque = "  <-- x%s" % cible if k == cible else ""
            L.append("%-16s %6d %11.2f %8d   |   %6d %11s %8s   %s"
                     % ("setup %s" % k, len(v), agrege(v)[2], i + 1,
                        nb, f(pb_) if nb else "-",
                        str(rang_b.get(k, "-")) if nb >= MINI else "-",
                        marque))
        L.append("-" * LARG)
        tete_a = [k for k, _v in classe[:TETE]]
        gains_b = [agrege(pb_s.get(k, []))[2] for k in tete_a
                   if len(pb_s.get(k, [])) >= MINI]
        if len(gains_b) < 2:
            L.append("  Les premiers de A n ont pas assez de tickets en B")
            L.append("  pour etre juges. Le test ne tranche pas.")
        else:
            moy = sum(gains_b) / len(gains_b)
            tous = agrege(B)[2]
            L.append("  Les %d premiers de A font %+.2f EUR/ticket en B ;"
                     % (len(gains_b), moy))
            L.append("  l ensemble de B fait %+.2f." % tous)
            if moy > tous:
                L.append("  Choisir sur A aide en B : la methode de selection")
                L.append("  transporte quelque chose. Le x%s designe par elle"
                         % cible)
                L.append("  merite alors d etre pris au serieux.")
            else:
                L.append("  Choisir sur A n aide PAS en B : les premiers de A")
                L.append("  ne valent pas mieux que la moyenne de B. La")
                L.append("  methode qui a designe le x%s ne transporte rien,"
                         % cible)
                L.append("  et le x%s designe par elle non plus." % cible)
    L.append("")

    # ------------------------------------------ 3. la concentration
    L.append("=" * LARG)
    L.append("  3. LA CONCENTRATION -- une moyenne, ou trois episodes ?")
    L.append("=" * LARG)
    L.append("%-22s %10s %12s %14s %14s"
             % ("", "fenetres", "EUR total", "top %d fenetres" % TETE,
                "top %d jours" % TETE))
    L.append("-" * LARG)
    fen = {}
    for nom, moitie in (("A  avant %s" % coupure, A),
                        ("B  depuis %s" % coupure, B)):
        fs = fenetres_de(moitie, cible)
        al = [x for x in fs if x["allume"]]
        fen[nom] = (fs, al)
        if not al:
            L.append("%-22s %10d %12s %14s %14s"
                     % (nom, 0, "-", "-", "-"))
            continue
        par_jour = defaultdict(float)
        for x in al:
            par_jour[x["jour"]] += x["eur"]
        cf, total = concentration([x["eur"] for x in al])
        cj, _t = concentration(list(par_jour.values()))
        L.append("%-22s %10d %12.2f %13s%% %13s%%"
                 % (nom, len(al), total, f(cf, 0), f(cj, 0)))
    L.append("-" * LARG)
    L.append("  'fenetres' = celles ou un x%s est le PREMIER entre." % cible)
    L.append("  Une part au-dessus de 80 %% veut dire que la moyenne decrit")
    L.append("  trois episodes et non un comportement. Ca ne la rend pas")
    L.append("  fausse -- ca la rend intransposable a la prochaine seance.")
    L.append("  Une part vide signifie un total nul ou negatif : une part")
    L.append("  de rien n aurait rien mesure.")
    L.append("")

    # ------------------------------------------- 4. les six cellules
    L.append("=" * LARG)
    L.append("  4. LES SIX CELLULES -- six lignes independantes, ou une")
    L.append("=" * LARG)
    L.append("%-22s %7s %11s %7s   |   %7s %11s %7s"
             % ("actif  bras", "N (A)", "EUR/tk A", "WR A",
                "N (B)", "EUR/tk B", "WR B"))
    L.append("-" * LARG)
    posA = posB = cellules = 0
    for act in ("US30", "US500", "US100"):
        for bras in sorted(set(s["bras"] for s in lot
                               if s["bras"] and s["setup"] == cible)):
            va = [s for s in A if s["setup"] == cible
                  and s["actif"] == act and s["bras"] == bras]
            vb = [s for s in B if s["setup"] == cible
                  and s["actif"] == act and s["bras"] == bras]
            if not (va or vb):
                continue
            cellules += 1
            na, _ea, pa_, wa = agrege(va)
            nb, _eb, pb_, wb = agrege(vb)
            if na and pa_ > 0:
                posA += 1
            if nb and pb_ > 0:
                posB += 1
            L.append("%-22s %7d %11s %6s%%   |   %7d %11s %6s%%"
                     % ("%s  %s" % (act, bras), na,
                        f(pa_) if na else "-", f(wa, 0) if na else "-",
                        nb, f(pb_) if nb else "-", f(wb, 0) if nb else "-"))
    L.append("-" * LARG)
    L.append("  %d cellules sur %d positives en A, %d sur %d en B."
             % (posA, cellules, posB, cellules))
    if cellules and posB == cellules:
        L.append("  Toutes positives en B : c est ce qui vaudrait le plus")
        L.append("  cher ici. Six lignes qui ne partagent ni actif ni bras")
        L.append("  ne tombent pas du meme cote par hasard.")
    elif cellules and posB <= cellules // 2:
        L.append("  La moitie ou moins tient en B : l edge n est pas dans")
        L.append("  le setup, il est dans une ou deux cellules -- donc")
        L.append("  peut-etre dans un ou deux episodes.")
    L.append("")
    L.append("  Les effectifs par cellule sont petits par construction :")
    L.append("  le setup %s trade dix a vingt fois moins que les autres."
             % cible)
    L.append("  C est ce qui rend le compte de cellules plus parlant que")
    L.append("  leurs chiffres pris un par un.")

    if a.detail:
        for nom in sorted(fen):
            fs, al = fen[nom]
            if not al:
                continue
            L.append("")
            L.append("=" * LARG)
            L.append("  LES FENETRES OU x%s ALLUME -- %s" % (cible, nom))
            L.append("=" * LARG)
            for x in sorted(al, key=lambda y: -y["eur"]):
                L.append("  %s  %s-%s  %2d tickets  %+10.2f  premier : %s"
                         % (x["jour"], H.hm(x["m0"]), H.hm(x["m1"]),
                            x["tk"], x["eur"], x["prem"]))

    for l in L:
        print(l)
    H.ecrire(["# x60_oos.txt",
              "# ecrit le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "# via x60_oos.py --setup %s --coupure %s" % (cible, coupure),
              ""] + L, os.path.join(a.dest, "x60_oos.txt"))
    print()
    print("ecrit : %s" % os.path.join(a.dest, "x60_oos.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

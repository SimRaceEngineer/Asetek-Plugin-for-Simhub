# -*- coding: utf-8 -*-
r"""
papers_compare.py -- dimensionnement 1 lot / 20 k, et le jeu DeepSeek en
                     230000 face au mien en 220000

  python papers_compare.py

LE DIMENSIONNEMENT, IDENTIQUE POUR LES DEUX JEUX

    Chaque magic part d une balance FICTIVE de 20 000 et prend

        lots = balance_courante / 20 000

    recalcule AVANT CHAQUE PRISE. A 20 k : 1,00 lot. A 30 k : 1,50.
    A 15 k : 0,75. La taille suit dans les deux sens.

    POURQUOI CA NE BIAISE PAS LA COMPARAISON, et c est le point :
    avec des lots proportionnels a la balance et un stop exprime en
    POINTS, le risque par trade est un POURCENTAGE CONSTANT du compte.
    Deux strategies de rendements differents sont alors comparables --
    ce qui ne serait pas le cas a lot fixe, ou la plus frequente
    accumulerait mecaniquement plus de risque absolu.

    Le plancher du courtier (0,01 lot) s applique : sous 200 de
    balance le compte ne peut plus dimensionner, et le journal doit le
    dire au lieu de continuer a 0.

CE QUE JE NE PEUX PAS FIXER, ET JE NE L INVENTE PAS

    La DISTANCE du stop en points. Elle depend de la volatilite de
    l actif a l instant de la prise -- un ATR, un pivot, une borne de
    canal. Aucune de ces grandeurs n est dans l export.

    Ce que je PEUX fixer, et qui ne depend d aucune donnee manquante :

        RR MINIMUM = (1 - p) / p       arithmetique pure
        RR CIBLE   = RR minimum x 1,5  marge declaree

    Une strategie a 45 % de reussite doit tenir 1,22 pour ne rien
    gagner, et vise 1,83 pour avoir de la marge. Le stop peut etre
    place ou le marche le dicte ; c est le RAPPORT qui est contraint.

    Poser ici un "SL = -30 EUR" sans connaitre la valeur du point
    serait un chiffre habille en mesure.

LES DEUX JEUX

    220001-220012   mes douze, croisant chacune trois sections
    2301xx-2303xx   les onze de DeepSeek, eclatees par actif :
                        1xx = US30    2xx = US500    3xx = US100

    Meme horaire, meme dimensionnement, memes donnees sources. Ce qui
    differe est le DECOUPAGE et la maniere de justifier -- donc c est
    bien les deux lectures qu on compare, pas deux echantillons.

L ARITHMETIQUE DE DEEPSEEK A ETE VERIFIEE

    Tous ses PnL par trade recalcules depuis l export tombent juste.
    Les MFE/MAE qu il cite ne sont PAS dans l export : ils viennent
    des panneaux complets que le REPL lit dans `panels\`. Une seule
    valeur est contredite par l export et elle est marquee dans la
    sortie.

LECTEUR SEUL. N ecrit que dans `cartes\`.
"""
import argparse
import io
import os
import sys
from datetime import datetime

import papers_optimized as po

BALANCE0 = 20000.0
LOT_PAR = 20000.0
LOT_MINI = 0.01
MARGE_RR = 1.5

ACTIFS = {"US30": 100, "US500": 200, "US100": 300}

# =====================================================================
# LES ONZE DE DEEPSEEK. `src` cite les lignes de l export qu il invoque,
# ce qui permet de recalculer ses chiffres. `hors_export` liste ce qu il
# avance et qui n y figure pas.
# =====================================================================
DEEPSEEK = [
 {"i": 1, "nom": "US BASE CLEAN", "actifs": ["US30", "US500", "US100"],
  "src": ["TC_CLEAN"], "profil": "fondation, frequence elevee",
  "note": "la base la plus robuste en effectif ; rendement modeste."},
 {"i": 2, "nom": "US TIGHT MIXED MOMENTUM", "actifs": ["US500", "US30", "US100"],
  "src": ["TC_MIXED", "US500_BU_CL"], "profil": "momentum, risque moyen",
  "note": "TIGHT_CROSS mixte croise avec le leader aligne."},
 {"i": 3, "nom": "US MID CLEAN TREND", "actifs": ["US30", "US500", "US100"],
  "src": ["MID_CLEAN", "M15_T_CL", "M3_T_MX"], "profil": "suivi, effectif tres large",
  "note": "la travailleuse : beaucoup de signaux, edge moyen."},
 {"i": 4, "nom": "US WIDE WIDENING", "actifs": ["US30", "US500", "US100"],
  "src": ["WIDE_CLEAN", "M5_WIDE_CL"], "profil": "cassure, volatilite",
  "note": "ECART : il annonce +11,04 sur N=250 pour US+WIDENING ; la "
          "seule ligne a 250 de l export donne 6,08."},
 {"i": 5, "nom": "US LEADER ROTATION", "actifs": ["US500"],
  "src": ["US500_BU_CL"], "profil": "conviction, meilleur couple N/R",
  "note": "leader detecte, churn propre, seance US."},
 {"i": 6, "nom": "US LEADER ROTATION", "actifs": ["US30"],
  "src": ["US30_BE_CL"], "profil": "conviction, meilleur couple N/R",
  "note": "le pendant baissier du Dow."},
 {"i": 7, "nom": "US HLC SPLIT CONFLUENCE", "actifs": ["US30", "US500", "US100"],
  "src": ["M15_SPL_CL"], "profil": "confluence, effectif robuste",
  "note": "suit le majoritaire 2/3, pas le divergent."},
 {"i": 8, "nom": "US PULLBACK M5 ANCHOR", "actifs": ["US30", "US500"],
  "src": ["M5_ET_YES"], "profil": "chirurgical, tres rare",
  "note": "43 prises. Une qualification, pas une preuve."},
 {"i": 9, "nom": "US CONTRARIAN M5 AGAINST", "actifs": ["US30", "US500", "US100"],
  "src": ["M5_AGA_CH", "M15_SCA_MX"], "profil": "fade du pack, risque eleve",
  "note": "son edge vient du CHURN, instable par nature."},
 {"i": 10, "nom": "US MULTI-TF M3+M5+M15", "actifs": ["US500"],
  "src": ["M3M5M15"], "profil": "ultra-selectif, rendement explosif",
  "note": "38 prises a 76 %. A surveiller, pas a conclure."},
 {"i": 11, "nom": "US VIX MOMENTUM BULL", "actifs": ["US500"],
  "src": ["MID_CLEAN", "US500_BU_CL"], "profil": "macro, complementaire",
  "note": "s appuie sur vix_trend.bias, qui n est PAS dans l export -- "
          "il vient d un autre panneau, invérifiable ici."},
]


def lots(balance):
    """Taille de position pour une balance donnee. Plancher courtier."""
    return max(LOT_MINI, round(balance / LOT_PAR, 2))


def bloc_dimensionnement():
    L = []
    a = L.append
    a("=" * 100)
    a("DIMENSIONNEMENT -- identique pour les deux jeux")
    a("=" * 100)
    a("  balance de depart (fictive) : %.0f" % BALANCE0)
    a("  regle                       : 1,00 lot par tranche de %.0f" % LOT_PAR)
    a("  recalcul                    : AVANT CHAQUE PRISE, a la hausse")
    a("                                comme a la baisse")
    a("  plancher courtier           : %.2f lot" % LOT_MINI)
    a("")
    a("  %12s  %8s   %12s  %8s" % ("balance", "lots", "balance", "lots"))
    paliers = [5000, 10000, 15000, 20000, 25000, 30000, 40000, 60000,
               80000, 100000, 150000, 200000]
    for k in range(0, len(paliers), 2):
        g, d = paliers[k], paliers[k + 1]
        a("  %12.0f  %8.2f   %12.0f  %8.2f"
          % (g, lots(g), d, lots(d)))
    a("")
    a("  POURQUOI CA NE BIAISE PAS LA COMPARAISON")
    a("  Des lots proportionnels a la balance, avec un stop en POINTS,")
    a("  donnent un risque par trade qui est un POURCENTAGE CONSTANT du")
    a("  compte. A lot fixe, la strategie la plus frequente accumulerait")
    a("  mecaniquement plus de risque absolu et paraitrait meilleure ou")
    a("  pire pour une raison qui n a rien a voir avec sa qualite.")
    a("")
    a("  CE QUE JE NE FIXE PAS : la distance du stop en points. Elle")
    a("  demande une volatilite par actif et par unite de temps, absente")
    a("  de l export. Ce qui est fixe, c est le RAPPORT :")
    a("")
    a("      RR MINIMUM = (1 - p) / p          arithmetique pure")
    a("      RR CIBLE   = RR minimum x %.1f     marge declaree" % MARGE_RR)
    a("")
    a("  Ecrire ici un SL en euros sans connaitre la valeur du point")
    a("  serait un chiffre habille en mesure.")
    return L


def ligne_strategie(magic, nom, profil, cles, actif):
    n_max, n_tot, taux, pnl_tr = po.agrege(cles)
    rr = po.rr_equilibre(taux)
    b = po.wilson_bas(taux, n_tot)
    return ("  %-7d %-8s %-26s %6d %5.0f%% %6.0f%% %6.2f %6.2f %8.2f"
            % (magic, actif, nom[:26], n_max, 100 * taux, 100 * b,
               rr, rr * MARGE_RR, pnl_tr))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sortie", default="cartes")
    p.add_argument("--cartes", default="cartes",
                   help="dossier des .html servis par l onglet CARTES")
    a = p.parse_args()

    L = []
    add = L.append
    add("=" * 100)
    add("PAPERS -- COMPARAISON DES DEUX LECTURES")
    add("=" * 100)
    add("  horaire commun : %s" % po.HORAIRE)
    add("  220001-220012  : douze strategies, croisement de trois sections")
    add("  2301xx-2303xx  : onze strategies DeepSeek, eclatees par actif")
    add("                   1xx = US30   2xx = US500   3xx = US100")
    add("")
    L.extend(bloc_dimensionnement())
    add("")
    add("=" * 100)
    add("JEU A -- 220001 a 220012")
    add("=" * 100)
    add("  %-7s %-8s %-26s %6s %6s %6s %6s %6s %8s"
        % ("MAGIC", "ACTIF", "NOM", "n max", "taux", "borne", "RRmin",
           "RRvis", "PnL/tr"))
    add("  " + "-" * 96)
    for s in po.STRATEGIES:
        add(ligne_strategie(s["magic"], s["nom"], s["profil"],
                            s["croise"], "US30+500"))
    add("")
    add("=" * 100)
    add("JEU B -- DEEPSEEK, eclate par actif")
    add("=" * 100)
    add("  %-7s %-8s %-26s %6s %6s %6s %6s %6s %8s"
        % ("MAGIC", "ACTIF", "NOM", "n max", "taux", "borne", "RRmin",
           "RRvis", "PnL/tr"))
    add("  " + "-" * 96)
    n_ds = 0
    for d in DEEPSEEK:
        for act in d["actifs"]:
            magic = 230000 + ACTIFS[act] + d["i"]
            add(ligne_strategie(magic, d["nom"], d["profil"], d["src"], act))
            n_ds += 1
    add("  " + "-" * 96)
    add("  %d magics DeepSeek pour %d strategies." % (n_ds, len(DEEPSEEK)))
    add("")
    add("=" * 100)
    add("LES NOTES DE DEEPSEEK, ET CE QUI EST VERIFIABLE")
    add("=" * 100)
    for d in DEEPSEEK:
        add("")
        add("  %s  (%s)" % (d["nom"], ", ".join(d["actifs"])))
        for k in d["src"]:
            lib, n, t, pnl, x = po.EXPORT[k]
            add("     %-30s n=%4d  %3.0f%%  %6.2f/trade"
                % (lib, n, 100 * t, pnl / float(n)))
        for ligne in po.decoupe(d["note"], 92):
            add("     %s" % ligne)
    add("")
    add("=" * 100)
    add("CE QUE LA COMPARAISON POURRA DIRE, ET CE QU ELLE NE POURRA PAS")
    add("=" * 100)
    add("  Les deux jeux lisent LE MEME export. Ils ne different que par")
    add("  le decoupage et la justification. La comparaison porte donc sur")
    add("  DEUX LECTURES, pas sur deux echantillons.")
    add("")
    add("  Consequence directe : si l export est sur-ajuste, les deux jeux")
    add("  se tromperont ENSEMBLE. Que l un batte l autre ne dira pas")
    add("  qu il a raison -- seulement qu il a mieux decoupe un meme")
    add("  echantillon, ce qui peut n etre que de la chance.")
    add("")
    add("  Ce qui sera vraiment informatif : qu un jeu tienne ses RR")
    add("  minimums et pas l autre. Le RR d equilibre ne depend d aucun")
    add("  ajustement -- c est le seul critere du tableau qui ne puisse")
    add("  pas etre sur-ajuste.")
    add("")
    add("  Genere le %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))

    txt = "\n".join(L)
    print(txt)

    # --- LES DEUX PANNEAUX EN HTML, POUR L ONGLET CARTES --------------
    # panels\ est ce que le REPL lit ; il n est servi par aucune route.
    # cartes\ est ce que l onglet CARTES sert, avec l en-tete et le
    # bouton copier. Les deux dossiers ne servent pas le meme lecteur,
    # et on ecrit dans les deux plutot que de choisir.
    #
    # Un <pre> suffit : la route prepose deja le style, la barre de
    # navigation et le bouton copier. Ecrire une seconde mise en page
    # ici serait le "deuxieme style a maintenir" du 14/08.
    if not os.path.isdir(a.cartes):
        os.makedirs(a.cartes)
    for nom, contenu in (("papers_220.html", po.rendu()),
                         ("papers_compare.html", txt)):
        h = (contenu.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;"))
        io.open(os.path.join(a.cartes, nom), "w", encoding="utf-8",
                newline="").write(
            '<pre style="font:12px Consolas,monospace;color:#c9d1d9;'
            'background:#0e1116;padding:16px 20px;margin:0;'
            'white-space:pre">' + h + "</pre>\n")
        print("  carte : %s" % os.path.join(a.cartes, nom))
    if not os.path.isdir(a.sortie):
        os.makedirs(a.sortie)
    che = os.path.join(a.sortie, "panel_papers_compare.txt")
    io.open(che, "w", encoding="utf-8", newline="").write(txt + "\n")
    print()
    print("  ecrit : %s (%d octets)" % (che, len(txt.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

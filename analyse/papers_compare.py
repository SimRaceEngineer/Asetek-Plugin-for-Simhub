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

    CE QUE CETTE REGLE NEUTRALISE : la TAILLE DU COMPTE. Le risque par
    trade vaut points_SL x valeur_point x balance / 20 000 ; rapporte a
    la balance il ne depend plus d elle. Une strategie ne paraitra donc
    ni meilleure ni pire selon qu elle a grossi ou fondu.

    CE QU ELLE NE NEUTRALISE PAS : l ECART DE STOPS entre strategies.
    J avais ecrit ici que le risque etait un pourcentage constant du
    compte. C est vrai A DISTANCE DE STOP EGALE, et faux entre deux
    strategies dont les stops different en points -- or les stops se
    posent sur la structure, donc ils different. Celle qui vise large
    risque mecaniquement plus par prise. Le vrai risque constant
    demanderait lot = (balance x risque%) / (points_SL x valeur_point),
    qui exige la valeur du point, absente de l export.

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
import json
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
 {"i": 1, "tf": "toutes", "sens": "les deux", "nom": "US BASE CLEAN", "actifs": ["US30", "US500", "US100"],
  "src": ["TC_CLEAN"], "profil": "fondation, frequence elevee",
  "note": "la base la plus robuste en effectif ; rendement modeste."},
 {"i": 2, "tf": "toutes", "sens": "les deux", "nom": "US TIGHT MIXED MOMENTUM", "actifs": ["US500", "US30", "US100"],
  "src": ["TC_MIXED", "US500_BU_CL"], "profil": "momentum, risque moyen",
  "note": "TIGHT_CROSS mixte croise avec le leader aligne."},
 {"i": 3, "tf": "M15 + M3", "sens": "les deux", "nom": "US MID CLEAN TREND", "actifs": ["US30", "US500", "US100"],
  "src": ["MID_CLEAN", "M15_T_CL", "M3_T_MX"], "profil": "suivi, effectif tres large",
  "note": "la travailleuse : beaucoup de signaux, edge moyen."},
 {"i": 4, "tf": "M5", "sens": "les deux", "nom": "US WIDE WIDENING", "actifs": ["US30", "US500", "US100"],
  "src": ["WIDE_CLEAN", "M5_WIDE_CL"], "profil": "cassure, volatilite",
  "note": "ECART : il annonce +11,04 sur N=250 pour US+WIDENING ; la "
          "seule ligne a 250 de l export donne 6,08."},
 {"i": 5, "tf": "toutes", "sens": "achat", "nom": "US LEADER ROTATION", "actifs": ["US500"],
  "src": ["US500_BU_CL"], "profil": "conviction, meilleur couple N/R",
  "note": "leader detecte, churn propre, seance US."},
 {"i": 6, "tf": "toutes", "sens": "vente", "nom": "US LEADER ROTATION", "actifs": ["US30"],
  "src": ["US30_BE_CL"], "profil": "conviction, meilleur couple N/R",
  "note": "le pendant baissier du Dow."},
 {"i": 7, "tf": "M15", "sens": "les deux", "nom": "US HLC SPLIT CONFLUENCE", "actifs": ["US30", "US500", "US100"],
  "src": ["M15_SPL_CL"], "profil": "confluence, effectif robuste",
  "note": "suit le majoritaire 2/3, pas le divergent."},
 {"i": 8, "tf": "M5", "sens": "les deux", "nom": "US PULLBACK M5 ANCHOR", "actifs": ["US30", "US500"],
  "src": ["M5_ET_YES"], "profil": "chirurgical, tres rare",
  "note": "43 prises. Une qualification, pas une preuve."},
 {"i": 9, "tf": "M5 + M15", "sens": "les deux", "nom": "US CONTRARIAN M5 AGAINST", "actifs": ["US30", "US500", "US100"],
  "src": ["M5_AGA_CH", "M15_SCA_MX"], "profil": "fade du pack, risque eleve",
  "note": "son edge vient du CHURN, instable par nature."},
 {"i": 10, "tf": "M3+M5+M15", "sens": "les deux", "nom": "US MULTI-TF M3+M5+M15", "actifs": ["US500"],
  "src": ["M3M5M15"], "profil": "ultra-selectif, rendement explosif",
  "note": "38 prises a 76 %. A surveiller, pas a conclure."},
 {"i": 11, "tf": "M15 + M3", "sens": "achat", "nom": "US VIX MOMENTUM BULL", "actifs": ["US500"],
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
    a("  balance de depart (FICTIVE)  : %.0f" % BALANCE0)
    a("")
    a("  CETTE BALANCE EST UNE VARIABLE A PART, ET DOIT LE RESTER.")
    a("  Le compte reel ne vaut pas %.0f. Un moteur papier qui lirait le" % BALANCE0)
    a("  solde reel dimensionnerait a balance_reelle / %.0f -- soit un" % LOT_PAR)
    a("  lot different du 1,00 attendu, sans que rien ne le signale, et")
    a("  les deux jeux seraient compares a des tailles qui n ont jamais")
    a("  ete celles de leur enonce.")
    a("")
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
    a("  CE QUE CETTE REGLE NEUTRALISE, ET CE QU ELLE NE NEUTRALISE PAS")
    a("")
    a("  ELLE NEUTRALISE la taille du compte. Le risque par trade vaut")
    a("  points_SL x valeur_point x balance / %.0f : rapporte a la" % LOT_PAR)
    a("  balance, il ne depend plus d elle. Une strategie ne paraitra")
    a("  donc ni meilleure ni pire selon qu elle a grossi ou fondu.")
    a("")
    a("  ELLE NE NEUTRALISE PAS l ecart de stops entre strategies.")
    a("  J avais ecrit que le risque etait un pourcentage constant du")
    a("  compte -- c est vrai A DISTANCE DE STOP EGALE, et faux entre")
    a("  deux strategies dont les stops different en points. Les stops")
    a("  se posent sur la structure : celle qui vise large risque")
    a("  mecaniquement plus par prise que celle qui vise serre.")
    a("")
    a("  Le vrai risque constant demanderait de dimensionner DEPUIS le")
    a("  stop :")
    a("")
    a("      lot = (balance x risque%) / (points_SL x valeur_point)")
    a("")
    a("  C est plus juste et plus contraignant -- il faut la valeur du")
    a("  point, que l export ne donne pas. La regle retenue reste le")
    a("  1 pour %.0f ; ce paragraphe dit ce qu elle laisse passer plutot" % LOT_PAR)
    a("  que de le taire.")
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


# ======================================================================
# CE QUI TOURNE VRAIMENT   (19/08/2026)
# ======================================================================
# Le tableau annoncait "AUCUN de ces magics n a pris un seul trade".
# C etait vrai le 18/08 et c est faux depuis que papers_moteur.py
# tourne. Un panneau qui affirme une chose fausse est pire qu un
# panneau absent : on lui fait confiance.
#
# CONSTATE se lit donc dans le journal, et le jeu en ligne se lit dans
# le moteur -- pas dans une liste recopiee ici qui divergerait au
# premier magic ajoute.
JOURNAL = os.path.join("docs", "papers_live", "trades.jsonl")


def charge_journal(chemin=JOURNAL):
    """Rend {magic: [prises]}. Journal absent = dict vide, sans erreur."""
    par = {}
    if not os.path.isfile(chemin):
        return par
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for l in f:
            l = l.strip()
            if not l:
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            if isinstance(o, dict) and o.get("magic") is not None:
                par.setdefault(o["magic"], []).append(o)
    return par


def jeu_en_ligne():
    """Rend {magic: nom} tel que le MOTEUR le definit, ou None.

    On l importe au lieu de le recopier : une liste de magics tenue a
    deux endroits diverge au premier ajout, et c est exactement ce qui
    a produit les deux TIGHT_SPREAD et les deux plafonds jumeaux."""
    try:
        import papers_moteur as pm
        pe, pr, manque = pm._charge_modules()
        if manque:
            return None
        return dict((m, nom) for m, nom, _a, _s, _p in pm.papers(pe, pr))
    except Exception:
        return None


def mesure(prises):
    """(n, pnl total, RR realise). RR None s il n y a aucune perte :
    un rapport gain/perte sans perte n existe pas, il ne vaut pas zero."""
    n = len(prises)
    if not n:
        return 0, 0.0, None
    pnls = [x.get("pnl") or 0.0 for x in prises]
    g = [v for v in pnls if v > 0]
    pe_ = [-v for v in pnls if v < 0]
    rr = ((sum(g) / len(g)) / (sum(pe_) / len(pe_))) if g and pe_ else None
    return n, sum(pnls), rr


def ligne_strategie(magic, nom, profil, cles, actif):
    n_max, n_tot, taux, pnl_tr = po.agrege(cles)
    rr = po.rr_equilibre(taux)
    b = po.wilson_bas(taux, n_tot)
    return ("  %-7d %-8s %-26s %6d %5.0f%% %6.0f%% %6.2f %6.2f %8.2f"
            % (magic, actif, nom[:26], n_max, 100 * taux, 100 * b,
               rr, rr * MARGE_RR, pnl_tr))



def tableau():
    """Le tableau de bord : une ligne par magic, ATTENDU puis CONSTATE.

    Les quatre dernieres colonnes sont VIDES et le resteront tant que
    rien n executera ces definitions. C est le fait le plus important
    du panneau, et il doit se voir au premier coup d oeil plutot que
    de se deduire d une absence."""
    L = []
    a = L.append
    a("=" * 132)
    a("TABLEAU DE BORD -- 36 magics, ATTENDU contre CONSTATE")
    a("=" * 132)
    par = charge_journal()
    roster = jeu_en_ligne()
    total = sum(len(v) for v in par.values())
    if roster is None:
        a("  MOTEUR ILLISIBLE : papers_moteur.py ou ses modules sont")
        a("  absents. CONSTATE ne peut pas etre rempli, et l ignorer")
        a("  aurait affiche des zeros pour une absence de mesure.")
    elif not total:
        a("  Les colonnes CONSTATE sont vides : le moteur tourne (%d"
          % len(roster))
        a("  papers en ligne) mais son journal est vide. Lance")
        a("  papers_moteur.py.")
    else:
        a("  CONSTATE est LU DANS LE JOURNAL depuis le 19/08 : %d prises"
          % total)
        a("  sur %d papers en ligne. Ce panneau affirmait jusqu ici qu"
          % len(roster))
        a("  AUCUN magic n avait pris un trade -- c etait vrai le 18/08,")
        a("  et faux depuis. Un panneau qui affirme une chose fausse est")
        a("  pire qu un panneau absent : on lui fait confiance.")
        a("")
        a("  'hors moteur' n est PAS zero. Zero veut dire que le filtre")
        a("  n a jamais accroche ; hors moteur veut dire que personne ne")
        a("  pose la question. Les confondre ferait passer une absence")
        a("  de mesure pour un resultat.")
    a("")
    a("  ET LA COLONNE ATTENDU N EST PAS VERIFIABLE SUR L HISTORIQUE.")
    a("  Mesure du 18/08 (papers_regime.py) : sept lectures du regime")
    a("  ont ete confrontees aux effectifs annonces par l export sur la")
    a("  section ecartement -- 214 / 154 / 251 / 231. AUCUNE ne les")
    a("  reproduit ; la moins eloignee est a 494. Les ecarts vont dans")
    a("  LES DEUX SENS (93 contre 214, mais 391 contre 154), ce qui")
    a("  exclut l explication d une periode plus courte : une fenetre")
    a("  trop petite produit des manques, jamais des exces.")
    a("")
    a("  Je ne sais donc pas reproduire la population dont ces chiffres")
    a("  sont issus. ATTENDU reste affiche parce qu il documente ce qui")
    a("  a ete promis, mais il ne peut etre ni confirme ni infirme ici.")
    a("  Le seul juge possible reste la mesure EN AVANT.")
    a("")
    a("  Par ailleurs 14 des 36 magics reposent sur des etats que rien")
    a("  ne journalise : le T/S (6 cles), l etoile (4), le with/against")
    a("  (3), les pentes (1). Ce ne sont pas des donnees egarees -- ces")
    a("  etats n ont jamais ete ecrits. 220001, designe comme socle de")
    a("  reference, en cumule deux.")
    a("")
    a("  %-7s %-3s %-8s %-10s %-11s | %5s %5s %5s %5s %7s | %6s %8s %6s"
      % ("MAGIC", "JEU", "ACTIF", "UNITE", "SENS",
         "nmax", "taux", "born", "RRmn", "PnL/tr",
         "TRADES", "PnL", "RR"))
    a("  " + "-" * 130)
    lignes = []
    for s2 in po.STRATEGIES:
        lignes.append((s2["magic"], "A", "US30+500", s2["tf"], s2["sens"],
                       s2["croise"]))
    for d in DEEPSEEK:
        for act in d["actifs"]:
            lignes.append((230000 + ACTIFS[act] + d["i"], "B", act,
                           d["tf"], d["sens"], d["src"]))
    for magic, jeu, act, tf, sens, cles in lignes:
        n_max, n_tot, taux, pnl_tr = po.agrege(cles)
        if roster is None:
            c_n, c_pnl, c_rr = "?", "?", "?"
        elif magic not in roster:
            c_n, c_pnl, c_rr = "hors", "moteur", "--"
        else:
            n, pnl, rr = mesure(par.get(magic) or [])
            c_n = "%d" % n
            c_pnl = ("%+.0f" % pnl) if n else "0"
            c_rr = ("%.2f" % rr) if rr is not None else "--"
        a("  %-7d %-3s %-8s %-10s %-11s | %5d %4.0f%% %4.0f%% %5.2f %7.2f "
          "| %6s %8s %6s"
          % (magic, jeu, act, tf[:10], sens[:11], n_max, 100 * taux,
             100 * po.wilson_bas(taux, n_tot), po.rr_equilibre(taux),
             pnl_tr, c_n, c_pnl, c_rr))
    a("  " + "-" * 130)
    a("  %d magics : %d dans le jeu A, %d dans le jeu B."
      % (len(lignes), len(po.STRATEGIES), len(lignes) - len(po.STRATEGIES)))
    a("")
    a("  horaire commun a tous : %s" % po.HORAIRE)
    a("  dimensionnement commun : 1,00 lot par tranche de %.0f de balance,"
      % LOT_PAR)
    a("  depart a %.0f, recalcule avant chaque prise." % BALANCE0)
    a("")
    a("  nmax   PLAFOND d effectif de l echantillon source, pas une")
    a("         prevision de frequence.")
    a("  born   borne basse de Wilson a 95 % sur le taux.")
    a("  RRmn   (1-p)/p : le rapport gain/perte sous lequel la strategie")
    a("         perd, quelle que soit sa qualite par ailleurs.")
    a("  PnL/tr attendu depuis l export -- IN ECHANTILLON, jamais verifie.")
    a("  TRADES/PnL/RR  CONSTATE, lu dans docs\\papers_live\\trades.jsonl.")

    if roster:
        dedans = set(m for m, _j, _a, _t, _s, _c in lignes)
        restants = sorted(m for m in roster if m not in dedans)
        a("")
        a("=" * 132)
        a("LE MOTEUR -- les %d papers en ligne, dont %d hors de ce tableau"
          % (len(roster), len(restants)))
        a("=" * 132)
        a("  Le tableau ci-dessus est le registre de ce qui a ete PROMIS.")
        a("  Le moteur, lui, fait tourner un autre ensemble : la serie")
        a("  240000 n a jamais figure dans l export, et les magics leader")
        a("  reparees le 19/08 ne sont entrees qu apres. Les deux listes")
        a("  ne coincident pas, et les fondre en une seule aurait cache")
        a("  laquelle repond de quoi.")
        a("")
        a("  %-7s %-30s %6s %10s %6s" % ("MAGIC", "NOM", "PRISES", "PnL",
                                         "RR"))
        a("  " + "-" * 64)
        for m in sorted(roster):
            n, pnl, rr = mesure(par.get(m) or [])
            a("  %-7d %-30s %6d %+10.0f %6s"
              % (m, roster[m][:30], n, pnl,
                 ("%.2f" % rr) if rr is not None else "--"))
        a("  " + "-" * 64)
        a("  RR realise, pas attendu. '--' = aucune perte encore, donc")
        a("  pas de rapport gain/perte : ce n est pas un zero.")
    return L


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
    L.extend(tableau())
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
    for nom, contenu in (("papers_tableau.html", "\n".join(tableau())),
                         ("papers_220.html", po.rendu()),
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

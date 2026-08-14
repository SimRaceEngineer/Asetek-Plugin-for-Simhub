# -*- coding: utf-8 -*-
"""
profils_croises.py -- la carte des profils, coloree par t et non par
                      la moyenne

  python profils_croises.py --schema
  python profils_croises.py
  python profils_croises.py --actif US30 --ut M5
  python profils_croises.py --min-n 54 --montre 25

CE QU IL FAIT, ET POURQUOI IL DIFFERE DE LA MATRICE

    matrice_croisement.py croise les filtres DEUX A DEUX. La question
    posee ici est autre : un PROFIL complet, du type

        TIGHT + WIDENING + seance US + CLEAN + PAS aligne

    par ACTIF et par UNITE DE TEMPS. Ce n est pas une paire, c est un
    point du produit cartesien des familles :

        seance     US / hors / indifferent                      3
        rails      TIGHT / MID / WIDE / indifferent             4
        churn      CLEAN / MIXED / CHURN / hors-CHURN / indiff. 5
        gap        WIDENING / NARROWING / STEADY / indifferent  4
        consensus  ALIGNE / PAS ALIGNE / indifferent            3
                                                     -> 720 profils

    fois 4 unites de temps, fois 4 actifs (les trois plus TOUS), fois
    2 cotes de la cassure = 23 040 cellules.

LA COULEUR EST UN t, PAS UNE MOYENNE -- c est tout le sujet

    Si le degrade rouge-vert codait la MOYENNE, le haut du classement
    serait toujours une cellule a trois signaux a +200 EUR, et la
    table deviendrait une machine a fabriquer des regles. On classe
    donc par

        t = e * racine(n) / sigma        avec e = ecart a la reference
                                         de sa propre periode

    Une cellule ne verdit que si son ecart ET son effectif le
    meritent. Les cellules sous --min-n ne sont pas colorees du tout :
    elles sont marquees `.` et sortent du classement.

    A 23 040 cellules enumerees, le seuil honnete n est ni 1,96 ni
    2,9 mais environ |t| = 4,4 (correction de Bonferroni : le z tel
    que 2*(1-Phi(z)) = 0,05/23040). Il est imprime en tete et chaque
    ligne dit si elle le passe.

CE QU IL FAUT ATTENDRE, calcule d avance

    Post-cassure il y a ~1 645 signaux. Repartis sur 3 actifs, ~550
    chacun ; repartis sur 720 profils, MOINS D UN SIGNAL par cellule
    en moyenne. La quasi-totalite de la carte sera vide ou grise.

    Ce n est pas un echec de l outil. C est la reponse : a ce volume,
    un profil multi-criteres par actif et par unite de temps n est pas
    mesurable. La carte rend cette phrase verifiable au lieu de la
    laisser discutable -- et elle montre EXACTEMENT ou l echantillon
    suffit encore, ce qui est la carte de ce qu on peut esperer
    trancher au 1er septembre.

LES PROFILS EMBOITES

    Un profil ou tout est `indifferent` est la reference elle-meme.
    Un profil qui n ajoute qu une famille est un filtre seul. La carte
    affiche donc la PROFONDEUR (nombre de familles contraintes) : a
    profondeur egale on compare des objets comparables, et on voit
    tout de suite qu ajouter une contrainte divise l effectif sans
    toujours ajouter de l ecart.

OU VA LA SORTIE, ET POURQUOI PAS DANS panels/

    Dans `cartes/`, pas dans `panels/`. Le REPL balaye panels/ et
    notes/ au demarrage : y deposer cette carte l ajouterait au
    contexte, qui pese deja ~206 000 jetons pour 250 000 caracteres.
    Un tableau de nombres alignes coute ~1,2 caractere par jeton,
    trois fois pire que de la prose -- c est le pire format possible
    pour un modele et le meilleur pour un oeil.

    Si tu veux que le REPL la lise malgre tout :
    --sortie panels\panel_profils.txt

Lecteur SEUL : lit un .jsonl, ecrit un .txt. Aucun ordre, aucun
collecteur, aucun etat modifie.
"""
import argparse
import collections
import io
import json
import math
import os
import sys
import datetime as dt

TRADES = os.path.join("docs", "churn_trades", "churn_trades.jsonl")
# HORS de `panels` a dessein. Le REPL balaye panels/ et notes/ au
# demarrage : y deposer cette carte l ajouterait automatiquement au
# contexte, qui pese deja ~206 000 jetons. Les tableaux de nombres
# alignes se tokenisent a ~1,2 caractere par jeton -- trois fois pire
# que de la prose. Cette carte est faite pour l ecran, pas pour le
# modele. `--sortie panels\panel_profils.txt` si tu veux qu il la lise.
SORTIE = os.path.join("cartes", "panel_profils.txt")
CASSURE = "2026-08-05"
SIGMA = 60.0
MIN_N = 54
LARG = 108

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def horo(ts):
    if not ts:
        return None
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(str(ts)[:19], f)
        except ValueError:
            continue
    return None


def charger(chemin, limite):
    lot = []
    if not os.path.isfile(chemin):
        return lot
    for l in io.open(chemin, encoding="utf-8", errors="replace"):
        if not l.strip():
            continue
        try:
            lot.append(json.loads(l))
        except ValueError:
            continue
        if len(lot) >= limite:
            break
    return lot


def seau_churn(v):
    v = (v or "").upper()
    if v in ("CLEAN", "OK", "TRADE"):
        return "CLEAN"
    if v in ("CHURN", "NOISE", "NO"):
        return "CHURN"
    if v:
        return "MIXED"
    return None


def signaux(trades, uts):
    """Jumeaux 206/207 fusionnes -- meme regle que _signals() de
    rails_trades_panel.py. Chaque signal porte, POUR CHAQUE UT, son
    gap (self_mom) et son consensus, afin que la carte puisse etre
    refaite par unite de temps sans relire le fichier."""
    grp, ordre = {}, []
    for t in trades:
        if not t.get("entry_captured_live"):
            continue
        te = horo(t.get("entry_ts"))
        if te is None or t.get("pnl_eur") is None:
            continue
        m = int(t.get("magic") or 0)
        if m // 1000 in (206, 207):
            cle = ("IGN", t.get("asset"), t.get("dir"), m % 1000,
                   int(te.timestamp() // 30))
        else:
            cle = ("SOLO", t.get("ticket"))
        if cle not in grp:
            grp[cle] = []
            ordre.append(cle)
        grp[cle].append(t)
    out = []
    for cle in ordre:
        arr = grp[cle]
        b = arr[0]
        pn = [float(x.get("pnl_eur") or 0) for x in arr]
        h = str(b.get("entry_ts") or "")[11:16]
        hl = b.get("hlc_churn_entry") or {}
        gap, cons = {}, {}
        for u in uts:
            d = hl.get(u)
            if isinstance(d, dict):
                # self_mom et non mom : verifie sur les donnees, pas
                # suppose depuis le code.
                gap[u] = d.get("self_mom") or d.get("mom")
                cons[u] = d.get("consensus")
            else:
                gap[u] = None
                cons[u] = None
        out.append({
            "jour": str(b.get("entry_ts") or "")[:10],
            "seance": "US" if "15:30" <= h < "19:30" else "hors",
            "actif": b.get("asset") or "?",
            "pnl": sum(pn) / len(pn),
            "rails": b.get("rails_setup"),
            "churn": seau_churn((b.get("churn_entry") or {}).get("verdict")),
            "gap": gap,
            "cons": cons,
        })
    return out


# --- les familles. `None` = indifferent, et c est une valeur, pas une
# absence : un profil tout-indifferent EST la reference.
FAM = [
    ("seance", (None, "US", "hors")),
    ("rails", (None, "TIGHT_CROSS", "MID", "WIDE")),
    ("churn", (None, "CLEAN", "MIXED", "CHURN", "horsCHURN")),
    ("gap", (None, "WIDENING", "NARROWING", "STEADY")),
    ("cons", (None, "ALIGNE", "PASALIGNE")),
]


def colle(s, fam, val, ut):
    if val is None:
        return True
    if fam == "seance":
        return s["seance"] == val
    if fam == "rails":
        return s["rails"] == val
    if fam == "churn":
        if val == "horsCHURN":
            return s["churn"] in ("CLEAN", "MIXED")
        return s["churn"] == val
    if fam == "gap":
        return s["gap"].get(ut) == val
    if fam == "cons":
        c = str(s["cons"].get(ut) or "")
        if val == "ALIGNE":
            return c.startswith("ALIGNED")
        return bool(c) and not c.startswith("ALIGNED")
    return True


def profils():
    lot = [{}]
    for fam, vals in FAM:
        neuf = []
        for p in lot:
            for v in vals:
                q = dict(p)
                q[fam] = v
                neuf.append(q)
        lot = neuf
    return lot


def nom(p):
    bouts = [("%s" % v) for f, v in
             (("seance", p["seance"]), ("rails", p["rails"]),
              ("churn", p["churn"]), ("gap", p["gap"]),
              ("cons", p["cons"])) if v is not None]
    return " + ".join(bouts) if bouts else "(reference)"


def prof(p):
    return sum(1 for f, _ in FAM if p[f] is not None)


def depend_ut(p):
    """Un profil qui ne contraint ni le gap ni le consensus ne depend
    d AUCUNE unite de temps. Le repeter par UT gonfle le compte de
    cellules et affiche quatre fois la meme trouvaille -- vu sur le
    banc, ou `US + horsCHURN` sortait a l identique sur M1, M3, M5 et
    M15. On l evalue une seule fois, etiquete `-`."""
    return p["gap"] is not None or p["cons"] is not None


def teinte(t, seuil):
    """Le degrade. Il ne code PAS la moyenne -- il code le t, donc l
    ecart ET l effectif. Une cellule sous le seuil n est jamais
    coloree."""
    if t is None:
        return " . "
    a = abs(t)
    if a >= seuil:
        return "###" if t > 0 else "XXX"
    if a >= seuil * 0.66:
        return "## " if t > 0 else "XX "
    if a >= seuil * 0.33:
        return "#  " if t > 0 else "X  "
    return " o "


def seuil_bonferroni(cellules):
    """z tel que 2*(1-Phi(z)) = 0,05 / cellules. Approximation
    rationnelle, sans dependance externe."""
    alpha = 0.05 / max(1, cellules)
    q = alpha / 2.0
    if q <= 0:
        return 6.0
    # inverse de la loi normale, approximation d Acklam simplifiee
    x = math.sqrt(-2.0 * math.log(q))
    z = x - (2.30753 + 0.27061 * x) / (1.0 + 0.99229 * x + 0.04481 * x * x)
    return z


def grille(a, sig, uts, zc, actifs):
    """La grille de couleurs. Lignes = gap x consensus (12), colonnes =
    churn (5). Une grille par unite de temps. Le rails et la seance
    sont FIXES par la ligne de commande : une grille a deux dimensions
    ne peut pas en montrer cinq, et empiler des dimensions dans une
    seule case est le meilleur moyen de la rendre illisible."""
    GAPS = (None, "WIDENING", "NARROWING", "STEADY")
    CONS = (None, "ALIGNE", "PASALIGNE")
    CHUR = (None, "CLEAN", "MIXED", "CHURN", "horsCHURN")
    ETI = {None: "indiff", "WIDENING": "WIDEN", "NARROWING": "NARROW",
           "STEADY": "STEADY", "ALIGNE": "ALIGNE", "PASALIGNE": "PAS-AL",
           "CLEAN": "CLEAN", "MIXED": "MIXED", "CHURN": "CHURN",
           "horsCHURN": "horsCH"}

    dis()
    dis("=" * LARG)
    dis("GRILLE DE COULEURS")
    dis("=" * LARG)
    dis("  cote %s  |  seance %s  |  rails %s  |  actif %s"
        % (a.cote, a.seance, a.rails or "indifferent",
           a.actif or "TOUS"))
    dis()
    dis("  Lignes = trajectoire du gap x consensus. Colonnes = churn.")
    dis("  Le rails et la seance sont fixes : une grille a deux")
    dis("  dimensions n en montre pas cinq. --rails et --seance pour")
    dis("  changer de page, --cote pour l autre cote de la cassure.")
    dis()
    dis("  Chaque case : symbole + effectif. La couleur code le t,")
    dis("  jamais la moyenne. Sous %d signaux : `.`, non colore."
        % a.min_n)
    dis("  ### tres vert  ##  vert  #  faible  o  neutre")
    dis("  XXX tres rouge XX  rouge X  faible")
    dis("=" * LARG)

    act = a.actif or "TOUS"
    for u in uts:
        lot = [s for s in sig if s["jour"]
               and ((s["jour"] >= a.cassure) == (a.cote == "DEPUIS"))
               and (act == "TOUS" or s["actif"] == act)
               and (a.seance == "toutes" or s["seance"] == a.seance)
               and (a.rails is None or s["rails"] == a.rails)]
        if not lot:
            dis()
            dis("  ut %s : aucun signal dans cette page." % u)
            continue
        mref = sum(x["pnl"] for x in lot) / len(lot)
        dis()
        dis("-" * LARG)
        dis("  ut %s  --  %d signaux dans la page, reference %+.2f"
            % (u, len(lot), mref))
        dis("-" * LARG)
        dis("  %-16s" % "" + "".join("%12s" % ETI[c] for c in CHUR))
        for g in GAPS:
            for c2 in CONS:
                nom_l = "%s / %s" % (ETI[g], ETI[c2])
                cases = []
                for ch in CHUR:
                    v = [x["pnl"] for x in lot
                         if (g is None or x["gap"].get(u) == g)
                         and (c2 is None or colle(x, "cons", c2, u))
                         and (ch is None or colle(x, "churn", ch, u))]
                    n = len(v)
                    # Meme gabarit pour TOUTES les cases, colorees ou
                    # non : symbole sur 3, effectif sur 6. Une case `.`
                    # formatee autrement decale la colonne entiere, et
                    # une grille mal alignee ne se lit pas.
                    if n < a.min_n:
                        cases.append("%12s" % ("%3s%6d" % (" . ", n)))
                        continue
                    m = sum(v) / n
                    t = (m - mref) * math.sqrt(n) / a.sigma
                    cases.append("%12s" % ("%3s%6d" % (teinte(t, zc), n)))
                dis("  %-16s%s" % (nom_l, "".join(cases)))
            dis()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--trades", default=TRADES)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--cassure", default=CASSURE)
    p.add_argument("--sigma", type=float, default=SIGMA)
    p.add_argument("--min-n", type=int, default=MIN_N, dest="min_n")
    p.add_argument("--montre", type=int, default=20,
                   help="combien de profils en tete et en queue")
    p.add_argument("--actif", default=None)
    p.add_argument("--ut", default=None)
    p.add_argument("--limite", type=int, default=200000)
    p.add_argument("--schema", action="store_true")
    p.add_argument("--grille", action="store_true",
                   help="la grille de couleurs au lieu du classement")
    p.add_argument("--cote", default="DEPUIS", choices=("DEPUIS", "AVANT"))
    p.add_argument("--seance", default="US",
                   choices=("US", "hors", "toutes"))
    p.add_argument("--rails", default=None,
                   help="TIGHT_CROSS / MID / WIDE ; defaut indifferent")
    a = p.parse_args()

    uts = [a.ut] if a.ut else ["M1", "M3", "M5", "M15"]
    brut = charger(a.trades, a.limite)
    if not brut:
        print("KO : %s introuvable ou vide." % a.trades)
        print("     Lance depuis le dossier de la stack.")
        return 1
    sig = signaux(brut, uts)
    if not sig:
        print("KO : aucun signal exploitable (entry_captured_live ?).")
        return 1

    actifs = [a.actif] if a.actif else \
        sorted(set(s["actif"] for s in sig)) + ["TOUS"]
    pr = profils()

    if a.schema:
        print("%d enregistrements -> %d signaux." % (len(brut), len(sig)))
        print("actifs : %s" % ", ".join(actifs))
        for u in uts:
            g = collections.Counter(str(s["gap"].get(u)) for s in sig)
            c = collections.Counter(str(s["cons"].get(u)) for s in sig)
            print("  %-4s gap %s" % (u, dict(g.most_common(5))))
            print("       cons %s" % dict(c.most_common(5)))
        print("rails : %s"
              % dict(collections.Counter(str(s["rails"])
                                         for s in sig).most_common(6)))
        print("churn : %s"
              % dict(collections.Counter(str(s["churn"])
                                         for s in sig).most_common(6)))
        nd = sum(1 for q in pr if depend_ut(q))
        print("%d profils (%d dependent de l ut, %d non) x %d actifs"
              " x 2 cotes = %d cellules"
              % (len(pr), nd, len(pr) - nd, len(actifs),
                 (nd * len(uts) + len(pr) - nd) * len(actifs) * 2))
        return 0

    n_dep = sum(1 for q in pr if depend_ut(q))
    n_ind = len(pr) - n_dep
    cellules = (n_dep * len(uts) + n_ind) * len(actifs) * 2
    zc = seuil_bonferroni(cellules)

    if a.grille:
        grille(a, sig, uts, zc, actifs)
        d = os.path.dirname(a.sortie)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        io.open(a.sortie, "w", encoding="utf-8").write(
            "\n".join(_ECHO) + "\n")
        print()
        print("ecrit : %s (%d octets)"
              % (a.sortie, os.path.getsize(a.sortie)))
        return 0

    dis("=" * LARG)
    dis("CARTE DES PROFILS -- coloree par t, jamais par la moyenne")
    dis("=" * LARG)
    dis("  %d enregistrements -> %d signaux (jumeaux 206/207 fusionnes)."
        % (len(brut), len(sig)))
    dis("  genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dis()
    dis("  %d profils : %d dependent de l unite de temps, %d non"
        % (len(pr), n_dep, n_ind))
    dis("  (ceux qui ne contraignent ni le gap ni le consensus).")
    dis("  (%d x %d + %d) x %d actifs x 2 cotes = %d cellules."
        % (n_dep, len(uts), n_ind, len(actifs), cellules))
    dis("  A ce nombre de cellules enumerees, le seuil honnete est")
    dis("  |t| >= %.2f (Bonferroni sur 0,05). Pas 1,96, pas 2,9." % zc)
    dis()
    dis("  t = ecart a la reference DE SA PROPRE PERIODE x racine(n)")
    dis("      / sigma, avec sigma = %.0f EUR (estimation du §0)." % a.sigma)
    dis("  Une cellule sous %d signaux n est PAS coloree : `.`" % a.min_n)
    dis()
    dis("  ### / XXX : passe le seuil     ## / XX : les deux tiers")
    dis("  #   / X   : le tiers            o     : sous le tiers")
    dis("=" * LARG)

    total_cell, total_vus, passent = 0, 0, []
    tous = []   # pour la frontiere : (cote, actif, ut, n, e, t, prof, nom)
    for cote in ("DEPUIS", "AVANT"):
        for act in actifs:
            lot0 = [s for s in sig if s["jour"]
                    and ((s["jour"] >= a.cassure) == (cote == "DEPUIS"))
                    and (act == "TOUS" or s["actif"] == act)]
            if not lot0:
                continue
            mref = sum(s["pnl"] for s in lot0) / len(lot0)
            for u in uts:
                lignes = []
                for q in pr:
                    # les profils sans gap ni consensus sont evalues
                    # une fois, sur la premiere UT seulement
                    if not depend_ut(q) and u != uts[0]:
                        continue
                    eti = u if depend_ut(q) else "-"
                    total_cell += 1
                    v = [s["pnl"] for s in lot0
                         if all(colle(s, f, q[f], u) for f, _ in FAM)]
                    n = len(v)
                    if n < a.min_n:
                        continue
                    total_vus += 1
                    m = sum(v) / n
                    e = m - mref
                    t = e * math.sqrt(n) / a.sigma
                    lignes.append((t, n, m, e, prof(q), nom(q)))
                    tous.append((cote, act, eti, n, e, t, prof(q), nom(q)))
                    if abs(t) >= zc:
                        passent.append((cote, act, eti, t, n, e, nom(q)))
                if not lignes:
                    continue
                lignes.sort()
                dis()
                dis("-" * LARG)
                dis("  %s  |  actif %s  |  ut %s  |  %d signaux, "
                    "reference %+.2f" % (cote, act, u, len(lot0), mref))
                dis("  %d profils sur %d ont au moins %d signaux."
                    % (len(lignes), len(pr), a.min_n))
                dis("-" * LARG)
                dis("  %-3s %7s %8s %8s %6s %5s  %s"
                    % ("", "n", "moy", "vs ref", "t", "prof", "profil"))
                bouts = lignes[:a.montre]
                if len(lignes) > 2 * a.montre:
                    bouts = lignes[:a.montre] + [None] \
                        + lignes[-a.montre:]
                elif len(lignes) > a.montre:
                    bouts = lignes
                for x in bouts:
                    if x is None:
                        dis("  ... %d profils intermediaires ..."
                            % (len(lignes) - 2 * a.montre))
                        continue
                    t, n, m, e, d, nm = x
                    dis("  %-3s %7d %+8.2f %+8.2f %6.2f %5d  %s"
                        % (teinte(t, zc), n, m, e, t, d, nm))

    # ---------------- LA FRONTIERE ----------------------------------
    # Le vrai livrable n est pas un verdict "rien ne passe" mais la
    # CARTE du compromis : a chaque effectif atteignable, le meilleur
    # ecart disponible. Un profil a 400 signaux et +6 EUR est plus
    # jouable qu un profil a 60 signaux et +25, et aucun des deux ne
    # "passe" un seuil.
    dis()
    dis("=" * LARG)
    dis("LA FRONTIERE -- le compromis effectif / ecart")
    dis("=" * LARG)
    dis("  Un profil est SUR la frontiere si aucun autre n a a la fois")
    dis("  plus de signaux ET un meilleur ecart. Ce sont les seuls")
    dis("  points ou l on choisit vraiment : partout ailleurs il existe")
    dis("  un profil strictement meilleur sur les deux axes.")
    dis()
    dis("  Lire de haut en bas : on gagne de l ecart en perdant de l")
    dis("  effectif. La question n est pas 'lequel est le meilleur'")
    dis("  mais 'jusqu ou accepte-t-on de descendre en n'.")
    dis()
    dis("  LA FRONTIERE EST ELLE AUSSI CHOISIE APRES COUP. Elle dit ce")
    dis("  qui etait atteignable sur ces donnees, pas ce qui marchera")
    dis("  sur les suivantes. C est une carte, pas un jeu de regles.")
    for cote in ("DEPUIS", "AVANT"):
        pts = [x for x in tous if x[0] == cote and x[4] > 0]
        if not pts:
            continue
        # front de Pareto sur (n croissant, ecart croissant)
        pts.sort(key=lambda x: (-x[3], -x[4]))     # n decroissant
        front, meilleur = [], None
        for x in pts:
            if meilleur is None or x[4] > meilleur:
                front.append(x)
                meilleur = x[4]
        front.sort(key=lambda x: -x[3])
        dis()
        dis("-" * LARG)
        dis("  %s -- %d profils au-dessus de leur reference, %d sur la"
            " frontiere" % (cote, len(pts), len(front)))
        dis("-" * LARG)
        dis("  %-3s %7s %8s %6s %5s %-6s %-4s  %s"
            % ("", "n", "vs ref", "t", "prof", "actif", "ut", "profil"))
        for c, act, u, n, e, t, d, nm in front:
            dis("  %-3s %7d %+8.2f %6.2f %5d %-6s %-4s  %s"
                % (teinte(t, zc), n, e, t, d, act, u, nm))

    dis()
    dis("=" * LARG)
    dis("CE QUE LA CARTE DIT")
    dis("=" * LARG)
    dis("  %d cellules enumerees, %d avaient au moins %d signaux."
        % (total_cell, total_vus, a.min_n))
    if not passent:
        dis("  AUCUNE ne passe |t| >= %.2f." % zc)
        dis()
        dis("  Ce seuil est celui d une DEMONSTRATION, et il est presque")
        dis("  inatteignable a 23 000 cellules -- c est arithmetique, pas")
        dis("  un jugement sur la stack. Ne pas s arreter la : la")
        dis("  FRONTIERE ci-dessus est le livrable. Elle dit, a chaque")
        dis("  effectif, le meilleur ecart atteignable, et c est ce qui")
        dis("  permet de choisir un point jouable plutot que le point")
        dis("  optimal -- lequel est, par construction, le plus sur-")
        dis("  ajuste de la table.")
    else:
        dis("  %d passent |t| >= %.2f :" % (len(passent), zc))
        for c, act, u, t, n, e, nm in sorted(passent,
                                             key=lambda x: -abs(x[3])):
            dis("    %-6s %-6s %-4s t=%+6.2f n=%-5d ecart %+7.2f  %s"
                % (c, act, u, t, n, e, nm))
        dis()
        dis("  ATTENTION : passer ce seuil ne rend pas une regle vraie.")
        dis("  Ces profils n ont PAS ete annonces d avance. Le seuil")
        dis("  corrige le nombre de cellules, il ne corrige pas le fait")
        dis("  qu on a choisi apres avoir vu. Une ligne qui passe est un")
        dis("  candidat a ecrire dans HYPOTHESES.md et a mesurer sur")
        dis("  donnees neuves -- rien de plus.")
    dis()
    dis("  Rappel : la profondeur `prof` est le nombre de familles")
    dis("  contraintes. A profondeur egale on compare des objets")
    dis("  comparables. Ajouter une contrainte divise l effectif sans")
    dis("  toujours ajouter de l ecart -- c est visible en lisant une")
    dis("  colonne prof a la fois.")

    d = os.path.dirname(a.sortie)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.sortie, "w", encoding="utf-8").write("\n".join(_ECHO) + "\n")
    print()
    print("ecrit : %s (%d octets)" % (a.sortie, os.path.getsize(a.sortie)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

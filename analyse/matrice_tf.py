# -*- coding: utf-8 -*-
"""
matrice_tf.py -- croiser les durees, les seances, les heures et le
                 contexte. Un LECTEUR, pas un patch.

  python matrice_tf.py
  python matrice_tf.py --depuis 2026-08-14
  python matrice_tf.py --mini 15

POURQUOI UN LECTEUR SEPARE PLUTOT QU UN PATCH DE PLUS

    Les tableaux demandes -- duree x seance, duree x heure, contexte x
    duree -- ne changent RIEN a ce qui est enregistre. Les mettre dans
    papier_tf obligerait a toucher un observateur qui tourne, a le
    redemarrer, et a recommencer a chaque nouvelle question. Ici on lit
    les memes fichiers, on n ecrit qu un panneau texte, et on peut
    reecrire ce script vingt fois sans jamais interrompre la collecte.

    C est aussi la seule facon d avoir un vocabulaire COMMUN aux deux
    panneaux : ce fichier classe les seances lui-meme, avec les bornes
    de x60_onset, y compris pour les lignes ecrites avant qu elles
    existent.

CE QU IL LIT

    docs/papier_tf/trades.jsonl    le papier : six durees, deux bras
    docs/x60_onset/events.jsonl    le live : entrees, sorties, plateau

CE QU IL FAIT DE PARTICULIER, ET QUI COMPTE

    1. IL REGROUPE LES JAMBES. Le bras 207 ecrit DEUX lignes par
       entree : les 70 % au break M2, puis les 30 % au reverse. Les
       compter separement double son N et lui prete des gains
       "positifs par construction" -- le partiel ne se declenche qu en
       profit. Une entree n est comptee que si elle porte une jambe
       TERMINALE (REVERSE, SL, SESSION_FLAT, MAX_DUREE). Une entree qui
       n a qu un PARTIEL70 court encore : elle est ECARTEE, et le
       nombre d ecartees est affiche.

    2. IL CLASSE LES SEANCES A LA LECTURE. Les lignes anterieures au
       patch de contexte n ont pas de champ `seance` : il est recalcule
       depuis l horodatage, avec les MEMES bornes que x60_onset. Rien
       n est retouche sur le disque.

    3. IL SEPARE LES TRAVERSANTES. Hors seance rien ne remet a plat :
       une nuit calme est une nuit SANS reverse, donc le x10 ouvert a
       02h encaisse le mouvement de 09h et se fait imputer a 02h. La
       section TRAVERSANTES compare celles qui ont franchi une
       ouverture a celles qui sont nees et mortes dans la meme seance.
       Sans cette separation, la nuit paraitra un bon creneau.

    4. IL REFUSE DE CONCLURE SOUS --mini. Le risque de cette etude
       n est pas de manquer un effet, c est d en trouver un partout :
       en decoupant par duree x bras x seance x regime on obtient
       vite des cases de dix trades, et sur des cases de dix on trouve
       TOUJOURS une combinaison flatteuse. Les cases sous le seuil sont
       affichees -- on decrit -- mais marquees d un point
       d interrogation, et jamais resumees en verdict.

CE QU IL NE FAIT PAS

    Il ne dit pas si une combinaison "marche". Il montre des cases avec
    leur N. La decision d appeler un chiffre un resultat suppose une
    hypothese ecrite AVANT la collecte -- voir HYPOTHESES.md.

LECTURE SEULE. Aucun MT5, aucun ordre. Ecrit panels/matrice_tf.txt.
"""
import argparse
import io
import json
import os
import sys
from collections import defaultdict

_ICI = os.path.dirname(os.path.abspath(__file__))
PAPIER = os.path.join(_ICI, "docs", "papier_tf", "trades.jsonl")
EVENTS = os.path.join(_ICI, "docs", "x60_onset", "events.jsonl")
DEST = os.path.join(_ICI, "panels", "matrice_tf.txt")
LARG = 100
MINI = 20
TERMINAUX = ("REVERSE", "SL", "SESSION_FLAT", "MAX_DUREE")

# Bornes IDENTIQUES a x60_onset.py et a papier_tf apres patch. Trois
# fichiers, un seul decoupage : c est la condition pour croiser.
SEANCES = (("ASIE", 60, 540), ("EUROPE", 540, 930),
           ("US", 930, 1320), ("NUIT", 1320, 60))
NOMS = [s[0] for s in SEANCES]
DUREES = (10, 20, 30, 60, 120, 240)


def seance4(ts):
    try:
        m = int(ts[11:13]) * 60 + int(ts[14:16])
    except (ValueError, IndexError, TypeError):
        return "?"
    for nom, deb, fin in SEANCES:
        if deb <= fin:
            if deb <= m < fin:
                return nom
        elif m >= deb or m < fin:
            return nom
    return "?"


def libelle(mn):
    return ("M%d" % mn) if mn < 60 else ("H%d" % (mn // 60))


def lire(chemin):
    if not os.path.isfile(chemin):
        return []
    out = []
    for l in io.open(chemin, encoding="utf-8", errors="replace"):
        l = l.strip()
        if not l.startswith("{"):
            continue
        try:
            out.append(json.loads(l))
        except ValueError:
            continue
    return out


def ratios(v):
    n = len(v)
    if not n:
        return 0, 0.0, 0.0, 0.0, None
    s = sum(v)
    g = [x for x in v if x > 0]
    p = [-x for x in v if x < 0]
    pf = (sum(g) / sum(p)) if p and sum(p) > 0 else None
    return n, s, s / float(n), 100.0 * len(g) / n, pf


def fpf(pf):
    return "-" if pf is None else ("%.2f" % pf if pf < 100 else "inf")


def cellule(v, mini):
    """'N moy WR' avec un ? sous le seuil, '-' si vide."""
    n, s, moy, wr, _pf = ratios(v)
    if not n:
        return "%18s" % "-"
    marque = "?" if n < mini else " "
    return "%4d %+8.2f %3.0f%%%s" % (n, moy, wr, marque)


def par_entree(lignes):
    """Regroupe les jambes par `id`. Rend (entrees, ecartees).

    Une entree n est CLOSE que si elle porte une jambe terminale. Le
    207 qui a coupe ses 70 % en profit et dont les 30 % courent encore
    n est pas un trade fini : le compter donnerait un gain positif par
    construction, puisque le partiel ne se declenche qu en profit.
    """
    par = defaultdict(list)
    for e in lignes:
        if e.get("quoi") != "TRADE":
            continue
        par[e.get("id") or ("%s@%s" % (e.get("k"), e.get("ouvert")))].append(e)
    entrees, ecartees = [], 0
    for _i, js in par.items():
        if not any(j.get("motif") in TERMINAUX for j in js):
            ecartees += 1
            continue
        prem = min(js, key=lambda j: j.get("ts") or "")
        der = max(js, key=lambda j: j.get("ts") or "")
        d = dict(prem)
        d["eur"] = sum(float(j.get("eur") or 0.0) for j in js)
        d["mfe"] = max(float(j.get("mfe") or 0.0) for j in js)
        d["mae"] = min(float(j.get("mae") or 0.0) for j in js)
        d["minutes"] = max(int(j.get("minutes") or 0) for j in js)
        d["motif"] = der.get("motif")
        d["jambes"] = len(js)
        d["seance"] = d.get("seance") or seance4(d.get("ouvert") or "")
        d["traverse"] = der.get("traverse")
        entrees.append(d)
    return entrees, ecartees


def _chemins(o, prefixe="", prof=0):
    """Aplati un ctx en {'mtf.signal': 'CONTINUATION', ...}.

    On n ecrit AUCUNE liste de cles attendues : le contexte est
    decouvert dans les donnees. Le jour ou churn_regime en ajoute une,
    elle apparait ici sans qu on ait rien a modifier -- et le jour ou
    il en retire une, sa disparition se voit au lieu de passer pour un
    resultat.
    """
    out = {}
    if not isinstance(o, dict) or prof > 3:
        return out
    for k, v in o.items():
        nom = "%s%s" % (prefixe, k)
        if isinstance(v, dict):
            out.update(_chemins(v, nom + ".", prof + 1))
        elif isinstance(v, bool) or isinstance(v, str) or v is None:
            out[nom] = v
        elif isinstance(v, (int, float)):
            continue          # les continus ne se groupent pas tels quels
        else:
            out[nom] = str(v)[:40]
    return out


def rapport(a):
    L = []
    pap = lire(PAPIER)
    ev = lire(EVENTS)
    entrees, ecartees = par_entree(pap)
    if a.depuis:
        entrees = [e for e in entrees
                   if (e.get("ouvert") or "")[:10] >= a.depuis]
    veilles = [e for e in pap if e.get("quoi") == "VEILLE"]

    L.append("=" * LARG)
    L.append("  MATRICE -- durees, seances, heures, contexte")
    L.append("=" * LARG)
    if not entrees:
        L.append("  Aucune entree papier close a lire.")
        if not os.path.isfile(PAPIER):
            L.append("  %s n existe pas encore." % PAPIER)
        return L
    jours = sorted(set((e.get("ouvert") or "")[:10] for e in entrees))
    L.append("  %d entrees closes, %s -> %s (%d jour(s) distincts)"
             % (len(entrees), jours[0], jours[-1], len(jours)))
    L.append("  %d entree(s) ecartee(s) : un PARTIEL70 coupe, le reste court"
             % ecartees)
    L.append("  encore. Les compter donnerait un gain positif par")
    L.append("  construction -- le partiel ne se declenche qu en profit.")
    avec_ctx = len([e for e in entrees if e.get("ctx")])
    L.append("  %d / %d entrees portent un contexte (%.0f %%)."
             % (avec_ctx, len(entrees), 100.0 * avec_ctx / len(entrees)))
    if avec_ctx == 0:
        L.append("  -> patch_papier_contexte n est pas applique, ou")
        L.append("     papier_tf n a pas ete relance depuis. La section")
        L.append("     CONTEXTE restera vide et ces heures sont perdues.")
    L.append("  seuil de conclusion : %d entrees par case." % a.mini)
    L.append("")

    # ---------------------------------------------------- duree x seance
    L.append("=" * LARG)
    L.append("  1. DUREE x SEANCE -- N, EUR/trade, WR")
    L.append("=" * LARG)
    L.append("%-7s %-5s%s" % ("duree", "bras",
                              "".join("%18s" % n for n in NOMS)))
    L.append("-" * LARG)
    for mn in DUREES:
        for bras in ("206", "207"):
            v = [e for e in entrees
                 if e.get("mn") == mn and e.get("bras") == bras]
            if not v:
                continue
            lig = "%-7s %-5s" % (libelle(mn), bras)
            for nom in NOMS:
                lig += cellule([e["eur"] for e in v
                                if e.get("seance") == nom], a.mini)
            L.append(lig)
    L.append("-" * LARG)
    obs = defaultdict(int)
    for e in veilles:
        obs[seance4(e.get("ts") or "")] += 1
    L.append("  observe : " + " | ".join(
        "%s %.1f h" % (n, obs.get(n, 0) * 10 / 60.0) for n in NOMS))
    L.append("  Une case vide en face d une couverture nulle ne dit rien.")
    L.append("  En face d une couverture longue, elle dit que rien ne s est")
    L.append("  declenche -- et ca, c est un resultat.")
    L.append("  Un ? marque une case sous %d entrees : on decrit, on ne"
             % a.mini)
    L.append("  conclut pas.")
    L.append("")

    # ------------------------------------------------------ duree x heure
    L.append("=" * LARG)
    L.append("  2. DUREE x HEURE D ENTREE -- EUR/trade, horloge machine")
    L.append("=" * LARG)
    L.append("%-7s%s" % ("duree", "".join("%3d" % h for h in range(24))))
    L.append("-" * LARG)
    for mn in DUREES:
        v = [e for e in entrees if e.get("mn") == mn]
        if not v:
            continue
        lig = "%-7s" % libelle(mn)
        for h in range(24):
            hv = [e["eur"] for e in v
                  if (e.get("ouvert") or "")[11:13] == "%02d" % h]
            if not hv:
                lig += "  ."
            else:
                moy = int(round(sum(hv) / float(len(hv))))
                # Au-dela de 99 la colonne deborderait et decalerait
                # toute la ligne : on marque la saturation au lieu de
                # casser l alignement, qui est ce qui rend ce tableau
                # lisible d un coup d oeil.
                lig += ("+++" if moy > 99 else
                        "---" if moy < -99 else "%3d" % moy)
        L.append(lig)
    L.append("-" * LARG)
    L.append("  '.' = aucune entree a cette heure. Le chiffre est l EUR par")
    L.append("  trade arrondi -- le N n y figure pas, donc AUCUNE case de")
    L.append("  ce tableau ne se lit seule : elle sert a reperer ou")
    L.append("  regarder, et la section 1 dit avec quel effectif.")
    L.append("")

    # ------------------------------------------------------- traversantes
    L.append("=" * LARG)
    L.append("  3. TRAVERSANTES -- le biais qui fabrique de bonnes nuits")
    L.append("=" * LARG)
    L.append("%-7s %18s %18s %18s"
             % ("duree", "n a rien franchi", "a franchi 1+", "inconnu"))
    L.append("-" * LARG)
    for mn in DUREES:
        v = [e for e in entrees if e.get("mn") == mn]
        if not v:
            continue
        sans = [e["eur"] for e in v if e.get("traverse") == []]
        avec = [e["eur"] for e in v if e.get("traverse")]
        inc = [e["eur"] for e in v if e.get("traverse") is None]
        L.append("%-7s%s%s%s" % (libelle(mn), cellule(sans, a.mini),
                                 cellule(avec, a.mini),
                                 cellule(inc, a.mini)))
    L.append("-" * LARG)
    L.append("  Une position ouverte hors seance ne meurt qu au reverse, au")
    L.append("  SL ou a MAX_DUREE. Une nuit calme est une nuit SANS")
    L.append("  reverse : le trade de 02h vit jusqu au matin et encaisse le")
    L.append("  mouvement de 09h, mais le tableau par heure l impute a 02h.")
    L.append("  Si la colonne 'a franchi' porte tout le gain nocturne, ce")
    L.append("  n est pas la nuit qui paie -- c est l ouverture suivante,")
    L.append("  et l heure d entree est une etiquette trompeuse.")
    L.append("  'inconnu' = lignes anterieures au patch de contexte : le")
    L.append("  champ manque, on ne suppose pas qu il vaut zero.")
    L.append("")

    # ------------------------------------------------------------ contexte
    L.append("=" * LARG)
    L.append("  4. CONTEXTE A L ENTREE x DUREE")
    L.append("=" * LARG)
    champs = defaultdict(lambda: defaultdict(list))
    for e in entrees:
        for k, v in _chemins(e.get("ctx") or {}).items():
            champs[k][str(v)].append(e)
    if not champs:
        L.append("  Aucun contexte enregistre. Cette section se remplira")
        L.append("  au prochain demarrage de papier_tf apres application de")
        L.append("  patch_papier_contexte -- pas avant, et pas")
        L.append("  retroactivement.")
    else:
        for k in sorted(champs):
            vals = champs[k]
            if len(vals) < 2 or len(vals) > 8:
                continue      # une seule valeur ne discrimine rien
            L.append("  %s" % k)
            L.append("  %-14s %s" % ("valeur",
                                     "".join("%18s" % libelle(m)
                                             for m in DUREES)))
            for val in sorted(vals):
                lig = "  %-14s" % val[:14]
                for mn in DUREES:
                    lig += cellule([e["eur"] for e in vals[val]
                                    if e.get("mn") == mn], a.mini)
                L.append(lig)
            L.append("")
        L.append("  Les cles sont DECOUVERTES dans les donnees, pas")
        L.append("  ecrites ici : si churn_regime en ajoute une, elle")
        L.append("  apparait sans qu on touche a ce script.")
        L.append("  Les champs continus sont ecartes : ils ne se groupent")
        L.append("  pas sans un decoupage arbitraire, et un decoupage")
        L.append("  choisi apres coup fabrique le resultat qu il cherche.")
    L.append("")

    # ---------------------------------------------------------- le live
    L.append("=" * LARG)
    L.append("  5. LE LIVE A COTE -- x60_onset")
    L.append("=" * LARG)
    if not ev:
        L.append("  %s illisible ou vide." % EVENTS)
    else:
        q = defaultdict(int)
        for e in ev:
            q[e.get("quoi") or "?"] += 1
        L.append("  " + " | ".join("%s %d" % (k, q[k]) for k in sorted(q)))
        clot = [e for e in ev if e.get("quoi") == "CLOTURE"]
        if clot:
            setups = defaultdict(list)
            for c in clot:
                m = str(c.get("magic") or "")
                s = m[-2:] if len(m) == 6 else "?"
                setups[s].append(float(c.get("final") or 0.0))
            L.append("")
            L.append("  clotures live par setup (dernier latent vu, pas le"
                     " resultat exact) :")
            L.append("  %-8s %6s %11s %11s" % ("setup", "N", "EUR", "EUR/t"))
            for s in sorted(setups):
                n, tot, moy, _wr, _pf = ratios(setups[s])
                L.append("  %-8s %6d %11.2f %11.2f" % (s, n, tot, moy))
            L.append("")
            L.append("  Le plateau -- qui est en position quand une cellule")
            L.append("  entre -- n est enregistre QUE pour les x60. Tant que")
            L.append("  le miroir x10/x20/x30 n est pas pose, la question")
            L.append("  'qui accompagne un x10' n a pas de donnee, et elle")
            L.append("  ne se rattrape pas : c est une photo de positions")
            L.append("  vivantes.")
    L.append("")

    L.append("=" * LARG)
    L.append("  CE QUE CE PANNEAU NE DIT PAS")
    L.append("=" * LARG)
    L.append("  Il montre des cases avec leur N. Il ne dit pas qu une")
    L.append("  combinaison marche.")
    L.append("  En decoupant par duree x bras x seance x contexte, on")
    L.append("  fabrique des dizaines de cases. Sur des cases de dix")
    L.append("  trades, il existe TOUJOURS une combinaison flatteuse :")
    L.append("  c est arithmetique, pas empirique.")
    L.append("  Un chiffre de ce panneau ne devient un resultat que s il")
    L.append("  repond a une hypothese ECRITE AVANT d avoir vu le tableau.")
    L.append("  C est l objet de HYPOTHESES.md.")
    return L


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--depuis", default="", help="AAAA-MM-JJ")
    p.add_argument("--mini", type=int, default=MINI)
    p.add_argument("--dest", default=DEST)
    a = p.parse_args()
    L = rapport(a)
    txt = "\n".join(L)
    print(txt)
    d = os.path.dirname(a.dest)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.dest, "w", encoding="utf-8").write(txt + "\n")
    print()
    print("ecrit : %s" % a.dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())

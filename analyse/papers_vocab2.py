# -*- coding: utf-8 -*-
r"""
papers_vocab2.py -- DESCENDRE dans les structures imbriquees des tickets

  python papers_vocab2.py
  python papers_vocab2.py --profond 8

LECTEUR SEUL. N ECRIT RIEN, NULLE PART.

CE QUE LE PREMIER LECTEUR A RATE, ET C ETAIT MON ERREUR

    papers_vocab.py n a compare les jetons qu aux chaines de PREMIER
    NIVEAU. Cinq champs des tickets sont sortis en "(structure)" sans
    etre ouverts :

        churn_entry   rails_entry   hlc_churn_entry
        ll_entry      epoch_entry

    Il a donc conclu "CLEAN ABSENT de tous les champs textuels lus".
    C etait litteralement vrai -- des champs LUS -- et trompeur : un
    champ nomme `churn_entry`, present a 100 %, est l endroit le plus
    probable pour porter le verdict CLEAN / MIXED / CHURN a l entree.
    Son propre avertissement de fin ("il peut vivre dans un champ non
    lu") s appliquait a lui-meme.

    Ce lecteur-ci descend. Chaque feuille est nommee par son chemin
    complet, `churn_entry.regime` plutot que `regime`, pour qu un
    predicat ecrit ensuite vise le bon endroit.

POURQUOI SEULEMENT LES TICKETS

    Les series_*.jsonl ont un schema PLAT deja entierement connu :
    asset, bear, bull, cycle_dir, fresh, rails_pos, rsi, rsi_pos,
    spread, tf, ts. Rien a y descendre, et elles pesent 130 Mo. On ne
    les relit pas.

    Les fichiers de tickets font 4 381 lignes. Ils sont lus EN ENTIER
    -- pas d echantillon, donc pas de distribution tronquee. Le
    premier lecteur s arretait a 4 000 lignes par fichier, ce qui sur
    une serie de 33 000 lignes ne montrait que les trois premieres
    heures de la journee. Ses distributions n etaient pas des resumes
    de journee et ne doivent pas etre lues comme tels.

CE QU IL IMPRIME

    1. Par fichier, chaque FEUILLE avec son chemin complet, son taux
       de presence, et ses valeurs si elles sont peu nombreuses.
    2. La chasse aux jetons, refaite sur les chemins complets.
    3. Un verdict explicite par section de l export : calculable
       retroactivement, ou pas. C est la seule chose qui decide si les
       36 magics sont mesurables sur l historique ou seulement en
       avant.

LA DERNIERE LIGNE PEUT ETRE TRONQUEE
    Comptee, ignoree, jamais reparee.
"""
import argparse
import io
import json
import os
import sys

CIBLES = [
    os.path.join("docs", "rails_trades", "tickets_rails.jsonl"),
    os.path.join("docs", "churn_trades", "churn_trades.jsonl"),
    os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
    os.path.join("docs", "papier_tf", "trades.jsonl"),
]

JETONS = [
    "CLEAN", "MIXED", "CHURN",
    "WIDENING", "NARROWING", "STEADY",
    "TIGHT_CROSS", "MID", "WIDE",
    "ALIGNED_BULL", "ALIGNED_BEAR", "SPLIT", "SCATTER",
    "CONVERGING", "DIVERGING",
    "WITH", "AGAINST",
    "BOTH>50", "BOTH<50", "STRADDLE",
    "ABOVE", "INSIDE", "BELOW",
    "BULL", "BEAR", "FLAT",
    "leader", "laggard", "divergent", "star", "etoile",
]

# Chaque section de l export, et le jeton qui la caracterise. Le
# verdict final se lit ligne par ligne : si le jeton n est nulle part,
# la section n est pas calculable retroactivement, point.
SECTIONS = [
    ("ecartement",            ["TIGHT_CROSS", "MID", "WIDE"]),
    ("regime",                ["CLEAN", "MIXED", "CHURN"]),
    ("position rails par tf", ["BOTH>50", "BOTH<50", "STRADDLE"]),
    ("position RSI par tf",   ["ABOVE", "INSIDE", "BELOW"]),
    ("alignement",            ["ALIGNED_BULL", "SPLIT", "SCATTER"]),
    ("largeur",               ["WIDENING", "NARROWING", "STEADY"]),
    ("convergence",           ["CONVERGING", "DIVERGING"]),
    ("with / against",        ["WITH", "AGAINST"]),
    ("leader / laggard",      ["leader", "laggard", "divergent"]),
    ("etoile",                ["star", "etoile"]),
]


def feuilles(obj, prefixe, profond, sortie):
    """Aplatit un objet en (chemin, valeur). Une liste devient `nom[]`."""
    if profond <= 0:
        sortie.append((prefixe + " (trop profond)", None))
        return
    if isinstance(obj, dict):
        for k in obj:
            che = (prefixe + "." + str(k)) if prefixe else str(k)
            feuilles(obj[k], che, profond - 1, sortie)
    elif isinstance(obj, list):
        # On ne numerote pas les elements : leurs cles nous interessent,
        # pas leur rang. Sinon un tableau de 30 entrees produirait 30
        # chemins distincts pour un seul et meme champ.
        for e in obj[:40]:
            feuilles(e, prefixe + "[]", profond - 1, sortie)
    else:
        sortie.append((prefixe, obj))


def lire(chemin, profond):
    """Rend (compteurs_par_chemin, n_lignes, n_objets, n_illisibles)."""
    champs, n, nb, ko = {}, 0, 0, 0
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for ligne in f:
            n += 1
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                o = json.loads(ligne)
            except ValueError:
                ko += 1
                continue
            if not isinstance(o, dict):
                continue
            nb += 1
            plat = []
            feuilles(o, "", profond, plat)
            vus = set()
            for che, val in plat:
                d = champs.setdefault(che, {"n": 0, "txt": {}, "num": 0,
                                            "mini": None, "maxi": None,
                                            "vide": 0})
                if che not in vus:
                    d["n"] += 1
                    vus.add(che)
                if val is None:
                    d["vide"] += 1
                elif isinstance(val, bool):
                    d["txt"][str(val)] = d["txt"].get(str(val), 0) + 1
                elif isinstance(val, (int, float)):
                    d["num"] += 1
                    v = float(val)
                    d["mini"] = v if d["mini"] is None else min(d["mini"], v)
                    d["maxi"] = v if d["maxi"] is None else max(d["maxi"], v)
                else:
                    s = str(val)
                    d["txt"][s] = d["txt"].get(s, 0) + 1
    return champs, n, nb, ko


def rendre(champs, total, max_val):
    L = []
    for k in sorted(champs):
        d = champs[k]
        part = 100.0 * d["n"] / total if total else 0.0
        if d["txt"]:
            vals = sorted(d["txt"].items(), key=lambda x: -x[1])
            if len(vals) <= max_val:
                bout = "  ".join("%s(%d)" % (a, b) for a, b in vals)
            else:
                bout = ("%d distinctes : " % len(vals)) + "  ".join(
                    "%s(%d)" % (a, b) for a, b in vals[:max_val]) + "  ..."
            L.append("    %-34s %5.1f%%  txt  %s" % (k[:34], part, bout))
        elif d["num"]:
            L.append("    %-34s %5.1f%%  num  min %.4g  max %.4g"
                     % (k[:34], part, d["mini"], d["maxi"]))
        else:
            L.append("    %-34s %5.1f%%  (vide sur %d)"
                     % (k[:34], part, d["vide"]))
    return L


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--profond", type=int, default=6,
                   help="profondeur maximale de descente (defaut 6)")
    p.add_argument("--valeurs", type=int, default=12)
    a = p.parse_args()

    L = []
    add = L.append
    add("=" * 78)
    add("PAPERS -- DESCENTE DANS LES STRUCTURES DES TICKETS")
    add("=" * 78)
    add("")
    add("  Lecteur seul. Le premier lecteur n avait pas ouvert les cinq")
    add("  champs sortis en (structure) ; il a donc dit ABSENT ce qu il")
    add("  n avait pas regarde. Celui-ci descend et nomme chaque feuille")
    add("  par son chemin complet.")
    add("")
    add("  Les series_*.jsonl ne sont PAS relues : schema plat deja")
    add("  connu, 130 Mo. Les tickets sont lus EN ENTIER.")
    add("")

    ou = {}
    vus_un = False
    for c in CIBLES:
        if not os.path.isfile(c):
            add("  ABSENT : %s" % c)
            continue
        vus_un = True
        champs, n, nb, ko = lire(c, a.profond)
        add("-" * 78)
        add("%s" % c)
        add("  %d lignes, %d objets%s"
            % (n, nb, ", %d illisibles" % ko if ko else ""))
        add("-" * 78)
        for ligne in rendre(champs, nb, a.valeurs):
            add(ligne)
        add("")
        for che, d in champs.items():
            for val in d["txt"]:
                for j in JETONS:
                    if j in val:
                        cle = (os.path.basename(c), che)
                        ou.setdefault(j, {})
                        ou[j][cle] = ou[j].get(cle, 0) + d["txt"][val]

    if not vus_un:
        add("  Aucun fichier de tickets trouve. Rien a conclure.")
        print("\n".join(L))
        return 1

    add("=" * 78)
    add("CHASSE AUX JETONS -- sur les chemins COMPLETS")
    add("=" * 78)
    for j in JETONS:
        if j in ou:
            liste = sorted(ou[j].items(), key=lambda x: -x[1])
            add("  %-14s %s" % (j, "   ".join(
                "%s:%s(%d)" % (cle[0][:20], cle[1], nb)
                for cle, nb in liste[:3])))
        else:
            add("  %-14s introuvable" % j)
    add("")

    add("=" * 78)
    add("VERDICT PAR SECTION DE L EXPORT")
    add("=" * 78)
    add("  Une section dont AUCUN jeton n est journalise ne peut pas")
    add("  etre reconstituee apres coup. Les magics qui s appuient")
    add("  dessus ne sont donc mesurables QU EN AVANT, a partir du jour")
    add("  ou quelque chose les executera.")
    add("")
    ok, ko2 = 0, 0
    for nom, jets in SECTIONS:
        trouves = [j for j in jets if j in ou]
        if trouves:
            ok += 1
            src = sorted(ou[trouves[0]].items(), key=lambda x: -x[1])[0]
            add("  %-24s CALCULABLE   via %s" % (nom, src[0][1]))
        else:
            ko2 += 1
            add("  %-24s NON CALCULABLE  (%s)" % (nom, " / ".join(jets[:3])))
    add("")
    add("  %d section(s) calculable(s), %d non." % (ok, ko2))
    add("")
    add("  Ce compte ne dit pas si les magics sont bons. Il dit")
    add("  seulement lesquels peuvent etre juges sur l historique et")
    add("  lesquels devront attendre. Confondre les deux serait")
    add("  presenter une attente comme une mesure.")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())

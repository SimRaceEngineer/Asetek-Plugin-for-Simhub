# -*- coding: utf-8 -*-
r"""
papers_vocab.py -- ou vivent les etats que les 36 magics filtrent

  python papers_vocab.py
  python papers_vocab.py --max 40

LECTEUR SEUL. N ECRIT RIEN, NULLE PART.

    Il ouvre des .jsonl en lecture, compte, et imprime. Aucun open en
    ecriture, aucun os.remove, aucun MetaTrader5. C est une ligne de
    grep.

POURQUOI CE SCRIPT EXISTE

    Les 36 magics (220001-220012 et le jeu DeepSeek en 230xxx) sont des
    FILTRES sur des etats de rails : CLEAN / MIXED / CHURN, WIDENING /
    NARROWING / STEADY, ALIGNED_BULL / SPLIT / SCATTER, leader /
    laggard, WITH / AGAINST, l etoile, les pentes.

    L export rails_trades donne chacune de ces sections SEPAREMENT. Il
    ne dit nulle part combien de trades verifient trois d entre elles
    EN MEME TEMPS. Or c est exactement ce que chaque magic demande, et
    c est le chiffre qui decide si la strategie est mesurable ou non.

    Pour calculer cette intersection il faut ecrire un predicat par
    cle d export. Pour ecrire un predicat il faut connaitre le NOM du
    champ et ses VALEURS reelles. Les deviner produirait un tableau
    plein et faux -- le piege exact decrit au §39 d oos_v9 : un champ
    non reconnu ne leve pas d erreur, il dilue la regle jusqu a la
    rendre identique a la reference, et le tableau sort plat et
    rassurant.

    Ce script ne fait donc qu une chose : dire ce qu il y a vraiment
    dans les fichiers, pour que les predicats soient ecrits contre des
    valeurs observees et non contre des valeurs esperees.

CE QU IL IMPRIME

    1. Les fichiers candidats trouves, avec leur taille et leur nombre
       de lignes. Un fichier absent est dit absent -- pas contourne.
    2. Par fichier, chaque champ present, son taux de presence, et
       pour les champs textuels a faible cardinalite la liste complete
       des valeurs avec leur effectif.
    3. Une CHASSE AUX JETONS : pour chaque mot du vocabulaire de
       l export, le fichier et le champ ou il apparait. C est la
       reponse directe a "ou vit CLEAN".

LA DERNIERE LIGNE PEUT ETRE TRONQUEE
    Un journal ecrit en continu peut etre lu au milieu d une ecriture.
    Une ligne qui ne parse pas est comptee et ignoree, jamais reparee
    ni signalee comme une perte.
"""
import argparse
import glob
import io
import json
import os
import sys

# Les emplacements sont ceux que rails_join.py declare deja. On ne
# devine pas de chemins : on reprend les siens.
CANDIDATS = [
    os.path.join("docs", "rails_trades", "tickets_rails.jsonl"),
    os.path.join("docs", "rails_trades", "series_*.jsonl"),
    os.path.join("docs", "churn_trades", "churn_trades.jsonl"),
    os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
    os.path.join("docs", "churn_trades", "series_*.jsonl"),
    os.path.join("docs", "papier_tf", "trades.jsonl"),
    "tickets_rails.jsonl",
    "churn_trades.jsonl",
    "churn_trades_archive.jsonl",
    "series_*.jsonl",
]

# Le vocabulaire que les 36 magics emploient. Chaque jeton est cherche
# tel quel dans les VALEURS de tous les champs textuels.
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
    "leader", "laggard", "divergent",
]


def fichiers():
    """Rend la liste des chemins reels, sans doublon, ordre stable."""
    vus, sortie = set(), []
    for motif in CANDIDATS:
        trouves = sorted(glob.glob(motif)) if "*" in motif else (
            [motif] if os.path.isfile(motif) else [])
        for c in trouves:
            r = os.path.normcase(os.path.abspath(c))
            if r not in vus:
                vus.add(r)
                sortie.append(c)
    return sortie


def lire(chemin, plafond):
    """Rend (objets, n_lignes, n_illisibles). Tolere une fin tronquee."""
    objets, n, ko = [], 0, 0
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
            if isinstance(o, dict) and len(objets) < plafond:
                objets.append(o)
    return objets, n, ko


def profil(objets, max_val):
    """Par champ : presence, type, et les valeurs si peu nombreuses."""
    total = len(objets)
    champs = {}
    for o in objets:
        for k, v in o.items():
            d = champs.setdefault(k, {"n": 0, "txt": {}, "num": [],
                                      "autre": 0})
            d["n"] += 1
            if isinstance(v, bool):
                d["txt"][str(v)] = d["txt"].get(str(v), 0) + 1
            elif isinstance(v, (int, float)):
                d["num"].append(float(v))
            elif isinstance(v, str):
                d["txt"][v] = d["txt"].get(v, 0) + 1
            else:
                d["autre"] += 1
    L = []
    for k in sorted(champs):
        d = champs[k]
        part = 100.0 * d["n"] / total if total else 0.0
        if d["num"] and not d["txt"]:
            s = sorted(d["num"])
            L.append("    %-22s %5.1f%%  num   min %.4g  med %.4g  max %.4g"
                     % (k, part, s[0], s[len(s) // 2], s[-1]))
        elif d["txt"]:
            vals = sorted(d["txt"].items(), key=lambda x: -x[1])
            if len(vals) <= max_val:
                bout = "  ".join("%s(%d)" % (a, b) for a, b in vals)
            else:
                bout = ("%d valeurs distinctes, les %d plus frequentes : "
                        % (len(vals), max_val)) + "  ".join(
                    "%s(%d)" % (a, b) for a, b in vals[:max_val])
            L.append("    %-22s %5.1f%%  txt   %s" % (k, part, bout))
        else:
            L.append("    %-22s %5.1f%%  (structure)" % (k, part))
    return L


def chasse(par_fichier):
    """Pour chaque jeton, dit ou il apparait. Reponse a 'ou vit CLEAN'."""
    trouve = {}
    for chemin, objets in par_fichier:
        for o in objets:
            for k, v in o.items():
                if not isinstance(v, str):
                    continue
                for j in JETONS:
                    if j in v:
                        trouve.setdefault(j, {}).setdefault(
                            (os.path.basename(chemin), k), 0)
                        trouve[j][(os.path.basename(chemin), k)] += 1
    L = []
    for j in JETONS:
        if j in trouve:
            ou = sorted(trouve[j].items(), key=lambda x: -x[1])
            L.append("  %-14s %s" % (j, "  ".join(
                "%s.%s(%d)" % (a[0], a[1], b) for a, b in ou[:4])))
        else:
            L.append("  %-14s ABSENT de tous les champs textuels lus" % j)
    return L


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--max", type=int, default=4000,
                   help="lignes lues par fichier (defaut 4000)")
    p.add_argument("--valeurs", type=int, default=14,
                   help="valeurs listees par champ (defaut 14)")
    a = p.parse_args()

    L = []
    add = L.append
    add("=" * 78)
    add("PAPERS -- VOCABULAIRE REEL DES CHAMPS")
    add("=" * 78)
    add("")
    add("  Lecteur seul. Aucune ecriture. Objet : savoir contre quelles")
    add("  valeurs ecrire les predicats des 36 magics, plutot que de les")
    add("  deviner.")
    add("")

    trouves = fichiers()
    if not trouves:
        add("  AUCUN fichier candidat trouve. Cherches :")
        for c in CANDIDATS:
            add("    %s" % c)
        add("")
        add("  Rien a conclure -- l intersection reste non calculable.")
        print("\n".join(L))
        return 1

    add("FICHIERS TROUVES")
    par_fichier = []
    for c in trouves:
        try:
            taille = os.path.getsize(c)
        except OSError:
            continue
        objets, n, ko = lire(c, a.max)
        add("  %-52s %9d o  %6d lignes%s"
            % (c, taille, n, "  (%d illisibles)" % ko if ko else ""))
        if objets:
            par_fichier.append((c, objets))
    add("")

    for c, objets in par_fichier:
        add("-" * 78)
        add("%s  --  %d objets lus" % (c, len(objets)))
        add("-" * 78)
        for ligne in profil(objets, a.valeurs):
            add(ligne)
        add("")

    add("=" * 78)
    add("CHASSE AUX JETONS -- ou vit chaque mot du vocabulaire de l export")
    add("=" * 78)
    for ligne in chasse(par_fichier):
        add(ligne)
    add("")
    add("  Un jeton ABSENT ne veut pas dire qu il n existe pas : il peut")
    add("  vivre dans un champ non lu, dans un fichier non liste, ou etre")
    add("  calcule a la volee par le panneau sans jamais etre journalise.")
    add("  Dans ce dernier cas l intersection ne sera pas calculable")
    add("  retroactivement, et il faudra le dire plutot que d approcher.")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())

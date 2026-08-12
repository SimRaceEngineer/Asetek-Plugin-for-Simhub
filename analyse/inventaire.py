# -*- coding: utf-8 -*-
"""
inventaire.py -- comparer deux copies de la stack, exactement

  Sur chaque machine :
      python inventaire.py --nom vps
      python inventaire.py --nom trident1

  Puis, avec les deux CSV cote a cote :
      python inventaire.py --comparer inventaire_vps.csv inventaire_trident1.csv

POURQUOI UN INVENTAIRE ET PAS UN DIFF

    Les deux copies sont sur des machines differentes, sans acces
    croise. On ne peut donc pas les diffuser l une contre l autre. Mais
    on peut faire dire a chacune ce qu elle contient -- chemin relatif,
    taille, empreinte SHA-256, date -- et comparer les deux listes.

    L empreinte est ce qui compte. Deux fichiers de meme taille peuvent
    differer d un caractere, et c est precisement ce genre d ecart qui
    fait qu une stack marche ici et pas la.

CE QU IL COMPTE, ET CE QU IL IGNORE

    Par defaut il inventorie le CODE et la CONFIGURATION, et il ecarte
    ce qui diverge legitimement d une machine a l autre :

        __pycache__, .git, venv          artefacts locaux
        logs\\                            journaux du jour
        docs\\rails_trades\\               corpus, des centaines de Mo
        panels\\                          exports regeneres
        *.bak-*                          sauvegardes de patch
        *.log *.dat *.jsonl *.csv        donnees, pas du code

    --tout leve toutes les exclusions. A utiliser si tu veux comparer
    aussi les donnees, en sachant que ce sera long et bruyant.

CE QUE LA COMPARAISON DIT

        SEUL_A / SEUL_B    present d un cote uniquement
        DIFFERENT          present des deux, empreintes differentes
        IDENTIQUE          meme empreinte (compte seulement)

    Et pour chaque DIFFERENT, l ecart de taille et la date la plus
    recente -- ce qui indique d ordinaire quel cote a ete modifie.

CE QU IL NE FAIT PAS

    Il ne copie rien, ne synchronise rien, n efface rien. Il lit et il
    ecrit un CSV. Une migration se decide en regardant cette liste, elle
    ne se fait pas par ce script.

    Il ne dit pas non plus si une difference est grave. Un fichier de
    configuration DOIT differer entre deux machines -- chemins, comptes,
    identifiants. C est a la lecture de trancher.
"""
import argparse
import csv
import hashlib
import io
import os
import sys
from datetime import datetime

EXCLUS_DOSSIERS = {"__pycache__", ".git", ".idea", ".vscode", "venv", ".venv",
                   "logs", "panels", "node_modules", "site-packages"}
EXCLUS_CHEMINS = (os.path.join("docs", "rails_trades"),)
EXCLUS_SUFFIXES = (".log", ".dat", ".jsonl", ".csv", ".pyc", ".zip", ".7z",
                   ".png", ".jpg", ".exe", ".dll")
EXCLUS_MOTIFS = (".bak-",)


def garde(rel, nom, tout):
    if tout:
        return True
    if any(rel.startswith(p) for p in EXCLUS_CHEMINS):
        return False
    if nom.lower().endswith(EXCLUS_SUFFIXES):
        return False
    if any(m in nom for m in EXCLUS_MOTIFS):
        return False
    return True


def empreinte(chemin):
    h = hashlib.sha256()
    try:
        with open(chemin, "rb") as f:
            for bloc in iter(lambda: f.read(131072), b""):
                h.update(bloc)
    except Exception:
        return ""
    return h.hexdigest()[:16]      # 16 chiffres suffisent ici, et se lisent


def inventorier(racine, nom, tout):
    lignes = []
    ignores = 0
    for dossier, sous, fichiers in os.walk(racine):
        sous[:] = [d for d in sous if d not in EXCLUS_DOSSIERS or tout]
        for f in fichiers:
            plein = os.path.join(dossier, f)
            rel = os.path.relpath(plein, racine)
            if not garde(rel, f, tout):
                ignores += 1
                continue
            try:
                st = os.stat(plein)
            except OSError:
                continue
            lignes.append({
                "chemin": rel.replace("\\", "/"),
                "taille": st.st_size,
                "sha256_16": empreinte(plein),
                "modifie": datetime.fromtimestamp(st.st_mtime)
                                   .strftime("%Y-%m-%d %H:%M:%S"),
            })
    lignes.sort(key=lambda x: x["chemin"])

    sortie = "inventaire_%s.csv" % nom
    with io.open(sortie, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["chemin", "taille", "sha256_16",
                                          "modifie"])
        w.writeheader()
        w.writerows(lignes)

    total = sum(l["taille"] for l in lignes)
    print("=" * 72)
    print(" INVENTAIRE : %s" % nom)
    print("=" * 72)
    print("racine   : %s" % os.path.abspath(racine))
    print("retenus  : %d fichiers, %.1f Mo" % (len(lignes), total / 1048576.0))
    print("ignores  : %d (donnees, journaux, sauvegardes)" % ignores)
    print("ecrit    : %s" % sortie)
    print()
    print("Copie ce fichier a cote de l autre inventaire, puis :")
    print("    python inventaire.py --comparer inventaire_A.csv inventaire_B.csv")
    return 0


def lire_inv(chemin):
    if not os.path.isfile(chemin):
        print("KO : %s introuvable." % chemin)
        sys.exit(1)
    d = {}
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            d[r["chemin"]] = r
    return d


def comparer(a, b):
    A, B = lire_inv(a), lire_inv(b)
    na = os.path.basename(a).replace("inventaire_", "").replace(".csv", "")
    nb = os.path.basename(b).replace("inventaire_", "").replace(".csv", "")

    seuls_a = sorted(set(A) - set(B))
    seuls_b = sorted(set(B) - set(A))
    communs = sorted(set(A) & set(B))
    diff = [c for c in communs if A[c]["sha256_16"] != B[c]["sha256_16"]]
    pareils = len(communs) - len(diff)

    print("=" * 92)
    print(" COMPARAISON  %s  contre  %s" % (na, nb))
    print("=" * 92)
    print("%-14s %d fichiers" % (na, len(A)))
    print("%-14s %d fichiers" % (nb, len(B)))
    print("identiques   : %d" % pareils)
    print("differents   : %d" % len(diff))
    print("seuls %-8s : %d" % (na, len(seuls_a)))
    print("seuls %-8s : %d" % (nb, len(seuls_b)))

    def bloc(titre, items, source=None):
        print()
        print("-" * 92)
        print(" %s (%d)" % (titre, len(items)))
        print("-" * 92)
        if not items:
            print("  aucun.")
            return
        for c in items[:60]:
            if source:
                print("  %-58s %9s o  %s"
                      % (c[:58], source[c]["taille"], source[c]["modifie"]))
            else:
                print("  %s" % c)
        if len(items) > 60:
            print("  ... et %d autres, voir le CSV." % (len(items) - 60))

    bloc("PRESENTS SEULEMENT DANS %s" % na.upper(), seuls_a, A)
    bloc("PRESENTS SEULEMENT DANS %s" % nb.upper(), seuls_b, B)

    print()
    print("-" * 92)
    print(" MEMES CHEMINS, CONTENUS DIFFERENTS (%d)" % len(diff))
    print("-" * 92)
    if not diff:
        print("  aucun.")
    else:
        print("  %-46s %10s %10s  %s" % ("chemin", na[:10], nb[:10],
                                         "le plus recent"))
        for c in diff[:60]:
            ta, tb = int(A[c]["taille"]), int(B[c]["taille"])
            recent = na if A[c]["modifie"] > B[c]["modifie"] else nb
            print("  %-46s %10d %10d  %s (%s)"
                  % (c[:46], ta, tb, recent,
                     max(A[c]["modifie"], B[c]["modifie"])))
        if len(diff) > 60:
            print("  ... et %d autres." % (len(diff) - 60))

    print()
    print("=" * 92)
    print(" COMMENT LIRE")
    print("=" * 92)
    print("  Une difference n est pas une anomalie. Les fichiers de")
    print("  configuration DOIVENT differer d une machine a l autre :")
    print("  chemins, comptes, identifiants, cles. Ce qui doit alerter,")
    print("  c est un module de LOGIQUE qui differe -- une gate, un")
    print("  trader, un module de sortie. Ceux-la devraient etre")
    print("  identiques si les deux stacks sont censees faire la meme")
    print("  chose.")
    print()
    print("  Un fichier present d un seul cote merite la meme question :")
    print("  est-il en plus ici, ou manquant la-bas ? La date du fichier")
    print("  et l historique git repondent d ordinaire.")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", default=".")
    p.add_argument("--nom", default=None,
                   help="nom de la machine, ex : vps ou trident1")
    p.add_argument("--tout", action="store_true",
                   help="n exclure ni les donnees ni les journaux")
    p.add_argument("--comparer", nargs=2, metavar=("A.csv", "B.csv"))
    a = p.parse_args()

    if a.comparer:
        return comparer(*a.comparer)
    if not a.nom:
        print("KO : donne un nom de machine, ex : --nom vps")
        return 1
    return inventorier(a.racine, a.nom, a.tout)


if __name__ == "__main__":
    sys.exit(main())

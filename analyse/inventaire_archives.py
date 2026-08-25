#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inventaire_archives.py -- de quoi sont faites les sauvegardes, et
                             qu y a-t-il vraiment a gagner a les compresser.

LECTEUR SEUL. N ECRIT RIEN, NE SUPPRIME RIEN, NE COMPRESSE RIEN.

POURQUOI CE SCRIPT
------------------
Les sauvegardes Abaure font une soixantaine de milliers de fichiers pour
treize gigaoctets. Avant d y toucher il faut savoir deux choses :

  1. de quoi elles sont faites ;
  2. quelle part est DEJA compressee.

Un JPEG, un MP4, un PDF, un .docx -- qui est un zip deguise -- ne rendent
rien. Les repasser dans 7-Zip coute des heures de calcul pour zero
gain. Seuls le texte, le CSV, le XML, les dumps et les vieux formats
bureautiques rendent vraiment du volume.

Sans cette mesure, on lancerait treize gigaoctets de lecture pour
peut-etre economiser deux.

IL PARLE PENDANT QU IL TRAVAILLE
--------------------------------
Une commande qui n affiche rien avant d avoir fini est indiscernable
d une commande bloquee. Celui-ci annonce sa progression toutes les deux
secondes : nombre de fichiers, volume, et ou il en est.

USAGE
-----
    python inventaire_archives.py
    python inventaire_archives.py --racine "G:\\...\\Sauvegarde ABAURE"
    python inventaire_archives.py --csv inventaire.csv
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time

RACINES_DEFAUT = [
    r"G:\Autres ordinateurs\My PC\Abaure\Sauvegarde ABAURE",
    r"G:\Autres ordinateurs\My PC\Abaure\Sauvegarde ddur portable imac",
]

# Facteur de compression attendu, par famille. Prudent plutot
# qu optimiste : mieux vaut annoncer moins et constater mieux.
FAMILLES = (
    ("texte et donnees", 8.0, (
        ".txt", ".csv", ".tsv", ".xml", ".json", ".sql", ".log", ".md",
        ".htm", ".html", ".css", ".js", ".py", ".php", ".c", ".h", ".cpp",
        ".java", ".ini", ".cfg", ".conf", ".yml", ".yaml", ".srt", ".vcf",
        ".eml", ".rtf", ".tex", ".bak", ".dat", ".dump")),
    ("bases", 4.0, (
        ".mdb", ".accdb", ".sqlite", ".sqlite3", ".db", ".mdf", ".ldf",
        ".dbf", ".fp7", ".myd", ".frm")),
    ("bureautique ancienne", 3.0, (
        ".doc", ".xls", ".ppt", ".pub", ".wpd", ".sxw", ".odt_old")),
    ("bureautique moderne", 1.05, (
        ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".epub")),
    ("pdf", 1.10, (".pdf", ".ps", ".eps")),
    ("images", 1.02, (
        ".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp", ".tif", ".tiff",
        ".bmp", ".raw", ".cr2", ".nef", ".arw", ".psd", ".ai", ".svg")),
    ("son et video", 1.0, (
        ".mp3", ".mp4", ".mov", ".avi", ".mkv", ".m4a", ".m4v", ".wav",
        ".aac", ".flac", ".wmv", ".mpg", ".mpeg", ".3gp", ".aiff")),
    ("deja archive", 1.0, (
        ".zip", ".7z", ".rar", ".gz", ".bz2", ".xz", ".tgz", ".zst",
        ".dmg", ".iso", ".jar", ".apk", ".pkg", ".cab")),
)

AUTRES = ("autres", 1.5)


def famille_de(ext):
    for nom, taux, exts in FAMILLES:
        if ext in exts:
            return nom, taux
    return AUTRES


def long_chemin(p):
    """Windows refuse les chemins de plus de 260 caracteres sans ce
    prefixe. Une sauvegarde de disque Mac en contient toujours."""
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        return "\\\\?\\" + os.path.abspath(p)
    return p


def humain(octets):
    for unite, seuil in (("Go", 1024 ** 3), ("Mo", 1024 ** 2), ("Ko", 1024)):
        if octets >= seuil:
            return "%.1f %s" % (octets / float(seuil), unite)
    return "%d o" % octets


def parcourir(racine, csv):
    """Parcours par os.scandir -- nettement plus rapide qu un
    Get-ChildItem -Recurse, et surtout on peut parler en chemin."""
    par_ext = {}
    n = 0
    total = 0
    erreurs = 0
    debut = time.time()
    dernier = 0.0
    pile = [racine]

    while pile:
        dossier = pile.pop()
        try:
            with os.scandir(long_chemin(dossier)) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            pile.append(e.path.replace("\\\\?\\", "", 1)
                                        if e.path.startswith("\\\\?\\")
                                        else e.path)
                            continue
                        taille = e.stat(follow_symlinks=False).st_size
                    except OSError:
                        erreurs += 1
                        continue
                    ext = os.path.splitext(e.name)[1].lower() or "(sans)"
                    c = par_ext.setdefault(ext, [0, 0])
                    c[0] += 1
                    c[1] += taille
                    n += 1
                    total += taille
                    if csv is not None:
                        csv.write('"%s";%d\n'
                                  % (e.path.replace('"', "'"), taille))
        except OSError:
            erreurs += 1

        maintenant = time.time()
        if maintenant - dernier >= 2.0:
            dernier = maintenant
            court = dossier
            if len(court) > 58:
                court = "..." + court[-55:]
            sys.stdout.write("\r   %7d fichiers  %10s  %5.0f s   %-58s"
                             % (n, humain(total), maintenant - debut, court))
            sys.stdout.flush()

    sys.stdout.write("\r" + " " * 100 + "\r")
    sys.stdout.flush()
    return par_ext, n, total, erreurs, time.time() - debut


def rapport(nom, par_ext, n, total, erreurs, duree):
    print("=" * 74)
    print(nom)
    print("=" * 74)
    print("   %d fichiers, %s, parcourus en %.0f s%s"
          % (n, humain(total), duree,
             ", %d inaccessibles" % erreurs if erreurs else ""))
    if not n:
        print("   (vide)")
        return 0, 0

    print("")
    print("   %-12s %8s %12s   %s" % ("extension", "fichiers", "volume",
                                      "famille"))
    print("   " + "-" * 62)
    for ext, (c, o) in sorted(par_ext.items(), key=lambda x: -x[1][1])[:18]:
        fam, _ = famille_de(ext)
        print("   %-12s %8d %12s   %s" % (ext, c, humain(o), fam))

    # -- par famille, et le gain attendu
    fam_tot = {}
    apres = 0.0
    for ext, (c, o) in par_ext.items():
        fam, taux = famille_de(ext)
        f = fam_tot.setdefault(fam, [0, 0, taux])
        f[0] += c
        f[1] += o
        apres += o / taux

    print("")
    print("   %-24s %8s %12s %12s" % ("famille", "fichiers", "volume",
                                      "apres (est.)"))
    print("   " + "-" * 62)
    for fam, (c, o, taux) in sorted(fam_tot.items(), key=lambda x: -x[1][1]):
        print("   %-24s %8d %12s %12s"
              % (fam, c, humain(o), humain(o / taux)))

    gain = total - apres
    print("")
    print("   AVANT %s   APRES %s (estime)   GAIN %s, soit %.0f %%"
          % (humain(total), humain(apres), humain(gain),
             100.0 * gain / total if total else 0))
    return total, apres


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", action="append", default=None)
    ap.add_argument("--csv", default=None,
                    help="ecrire la liste complete des fichiers dans ce CSV")
    args = ap.parse_args()

    racines = args.racine or RACINES_DEFAUT

    print("=" * 74)
    print("inventaire_archives -- LECTURE SEULE, rien n est modifie")
    print("=" * 74)

    csv = None
    if args.csv:
        csv = io.open(args.csv, "w", encoding="utf-8")
        csv.write('"chemin";octets\n')
        print("liste complete -> %s" % args.csv)

    grand_avant = 0
    grand_apres = 0.0
    try:
        for r in racines:
            print("")
            if not os.path.isdir(r):
                print("introuvable : %s" % r)
                continue
            print("parcours de %s" % r)
            par_ext, n, total, erreurs, duree = parcourir(r, csv)
            a, b = rapport(r, par_ext, n, total, erreurs, duree)
            grand_avant += a
            grand_apres += b
    finally:
        if csv is not None:
            csv.close()

    if len(racines) > 1 and grand_avant:
        print("")
        print("=" * 74)
        print("TOTAL   avant %s   apres %s   gain %s (%.0f %%)"
              % (humain(grand_avant), humain(grand_apres),
                 humain(grand_avant - grand_apres),
                 100.0 * (grand_avant - grand_apres) / grand_avant))
        print("=" * 74)
    print("")
    print("Estimations prudentes, par famille de format. Elles servent a")
    print("decider si l operation vaut la peine, pas a promettre un chiffre.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

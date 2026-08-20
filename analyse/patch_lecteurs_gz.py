# -*- coding: utf-8 -*-
r"""
patch_lecteurs_gz.py -- apprendre le .gz aux deux lecteurs de snapshots

  python patch_lecteurs_gz.py --essai     montre ce qui changerait
  python patch_lecteurs_gz.py             applique
  python patch_lecteurs_gz.py --defaire   restaure les .bak

CE QU IL DEBLOQUE, ET POURQUOI CA BLOQUAIT

    docs\buddha\<jour>\snapshots.csv : 2,0 Go en clair sur 22 journees.
    rotation_docs REFUSE de les comprimer, et il a raison :

      extraire_snapshots.journees()  cherche "snapshots.csv"
      audit_cadence (source 2)       cherche "snapshots.csv"

    Le nom EXACT, sans variante. Les gzipper ne provoquerait aucune
    erreur : les deux trouveraient zero journee et rendraient un
    rapport vide. Plausible, et faux.

    Ce n est donc pas une donnee a proteger, c est un lecteur a
    corriger -- et la stack sait deja le faire.

LA SOLUTION EXISTE DEJA DANS LE DEPOT

    extraire_cycles.py porte, en propres termes :

        def source(dossier):
            for nom in ("cycles.jsonl", "cycles.jsonl.gz"):
                ...
        def ouvre(chemin):
            if chemin.endswith(".gz"):
                return io.TextIOWrapper(gzip.open(chemin, "rb"), ...)
            return io.open(chemin, ...)

    et son en-tete raconte le bug qu il a corrige : "une premiere
    version ne cherchait que le nom sans extension et ignorait donc
    dix-sept journees sur dix-neuf, sans rien dire". On ne resout pas
    le meme probleme d une deuxieme facon : on recopie celle-la.

LES HUIT CHANGEMENTS

    extraire_snapshots.py
      1. import gzip
      2. une fonction ouvre() -- identique a celle d extraire_cycles --
         et entete() qui passe par elle
      3. journees() essaie le nom puis le nom + .gz
      4. une_journee() passe par ouvre()

    audit_cadence.py
      5. import gzip
      6. une fonction ouvre()
      7. lis_ts() passe par ouvre()
      8. la source 2 essaie le nom puis le nom + .gz

    PORTEE : les deux fichiers sont des LECTEURS. Ils n envoient aucun
    ordre et n ecrivent que leurs propres sorties. Aucun trader ne les
    importe. Le comportement sur un fichier NON comprime est
    rigoureusement inchange -- ouvre() ne devie que sur l extension.

    Chaque fichier est sauvegarde en .bak avant ecriture, et --defaire
    les restaure.
"""
import argparse
import io
import os
import shutil
import sys

# (fichier, libelle, ancre, remplacement)
CHANGEMENTS = [
    ("extraire_snapshots.py", "1/8  import gzip",
     "import csv\nimport io\n",
     "import csv\nimport gzip\nimport io\n"),

    ("extraire_snapshots.py", "2/8  ouvre(), et entete() qui l utilise",
     'def entete(chemin):\n'
     '    with io.open(chemin, encoding="utf-8", errors="replace") as f:\n',
     'def ouvre(chemin):\n'
     '    """Un flux de texte, que le fichier soit compresse ou non.\n'
     '\n'
     '    Copie conforme d extraire_cycles.ouvre : la stack a deja\n'
     '    resolu ce probleme une fois, on ne le resout pas autrement\n'
     '    ailleurs."""\n'
     '    if chemin.endswith(".gz"):\n'
     '        return io.TextIOWrapper(gzip.open(chemin, "rb"),\n'
     '                                encoding="utf-8", errors="replace")\n'
     '    return io.open(chemin, encoding="utf-8", errors="replace")\n'
     '\n'
     '\n'
     'def entete(chemin):\n'
     '    with ouvre(chemin) as f:\n'),

    ("extraire_snapshots.py", "3/8  journees() essaie les deux noms",
     '        c = os.path.join(racine, j, "snapshots.csv")\n'
     '        if os.path.isfile(c):\n'
     '            out.append((j, c))\n',
     '        # Le nom EXACT d abord, puis la variante comprimee. Ne\n'
     '        # chercher que le premier rendait 22 journees invisibles\n'
     '        # sans lever la moindre erreur.\n'
     '        for nom in ("snapshots.csv", "snapshots.csv.gz"):\n'
     '            c = os.path.join(racine, j, nom)\n'
     '            if os.path.isfile(c):\n'
     '                out.append((j, c))\n'
     '                break\n'),

    ("extraire_snapshots.py", "4/8  une_journee() passe par ouvre()",
     '    with io.open(src, encoding="utf-8", errors="replace") as f:\n',
     '    with ouvre(src) as f:\n'),

    ("audit_cadence.py", "5/8  import gzip et ouvre()",
     "import argparse\nimport io\n",
     "import argparse\nimport gzip\nimport io\n"),

    ("audit_cadence.py", "6/8  lis_ts() par ouvre(), source 2 sur deux noms",
     'def lis_ts(chemin, colonne, sep, echantillon, maxi):\n',
     'def ouvre(chemin):\n'
     '    """Un flux de texte, que le fichier soit compresse ou non."""\n'
     '    if chemin.endswith(".gz"):\n'
     '        return io.TextIOWrapper(gzip.open(chemin, "rb"),\n'
     '                                encoding="utf-8", errors="replace")\n'
     '    return io.open(chemin, encoding="utf-8", errors="replace")\n'
     '\n'
     '\n'
     'def lis_ts(chemin, colonne, sep, echantillon, maxi):\n'),

    ("audit_cadence.py", "7/8  lis_ts ouvre le flux",
     '        with io.open(chemin, encoding="utf-8", errors="replace") as f:\n',
     '        with ouvre(chemin) as f:\n'),

    ("audit_cadence.py", "8/8  la source 2 essaie les deux noms",
     '            c = os.path.join(a.buddha, j, "snapshots.csv")\n'
     '            if not os.path.isfile(c):\n'
     '                continue\n',
     '            for nom in ("snapshots.csv", "snapshots.csv.gz"):\n'
     '                c = os.path.join(a.buddha, j, nom)\n'
     '                if os.path.isfile(c):\n'
     '                    break\n'
     '            else:\n'
     '                continue\n'),
]

CANDIDATS = [
    os.getcwd(),
    os.path.dirname(os.path.abspath(__file__)) or ".",
    os.path.join(os.path.expanduser("~"), "Downloads",
                 "Scalp-EA-main", "Scalp-EA-main"),
]


def trouve(nom):
    vus = []
    for c in CANDIDATS:
        if c in vus:
            continue
        vus.append(c)
        p = os.path.join(c, nom)
        if os.path.isfile(p):
            return p
    return None


def lis(p):
    return io.open(p, encoding="utf-8", errors="replace").read()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--essai", action="store_true")
    p.add_argument("--defaire", action="store_true")
    a = p.parse_args()

    def dis(x):
        print(x)
        sys.stdout.flush()

    dis("=" * 78)
    dis("APPRENDRE LE .gz AUX LECTEURS DE snapshots")
    dis("=" * 78)
    dis("")

    fichiers = sorted(set(f for f, _l, _a, _r in CHANGEMENTS))
    chemins = {}
    for f in fichiers:
        c = trouve(f)
        if c is None:
            dis("  INTROUVABLE : %s" % f)
            dis("  Lance depuis le dossier du stack.")
            return 1
        chemins[f] = c
        dis("  %-26s %s" % (f, c))
    dis("")

    if a.defaire:
        for f in fichiers:
            bak = chemins[f] + ".bak"
            if os.path.isfile(bak):
                shutil.copyfile(bak, chemins[f])
                dis("  restaure : %s" % chemins[f])
            else:
                dis("  pas de .bak pour %s" % f)
        dis("")
        dis("  Restauration terminee.")
        return 0

    src = dict((f, lis(chemins[f])) for f in fichiers)
    faits, a_faire, manquants = [], [], []
    for f, lib, anc, rem in CHANGEMENTS:
        s = src[f]
        # Le deja-fait se teste EN PREMIER : plusieurs remplacements
        # contiennent leur propre ancre, et tester l ancre d abord les
        # declarerait "a faire" alors qu ils sont poses.
        if rem in s:
            faits.append(lib)
        elif s.count(anc) == 1:
            a_faire.append((f, lib, anc, rem))
        elif anc not in s:
            manquants.append((f, lib, "ancre absente"))
        else:
            manquants.append((f, lib, "ancre %d fois -- ambigu"
                              % s.count(anc)))

    if faits:
        dis("  DEJA APPLIQUE :")
        for l in faits:
            dis("    %s" % l)
        dis("")
    if manquants:
        dis("  IMPOSSIBLE -- le fichier n est pas celui attendu :")
        for f, l, pq in manquants:
            dis("    %-40s %s  (%s)" % (l, f, pq))
        dis("")
        dis("  Rien n a ete ecrit. Envoie-moi ces lignes.")
        return 1
    if not a_faire:
        dis("  Tout est deja en place. Rien a faire.")
        return 0

    dis("  A APPLIQUER :")
    for _f, l, _a, _r in a_faire:
        dis("    %s" % l)
    dis("")

    if a.essai:
        dis("  --essai : RIEN n a ete ecrit.")
        dis("  Relance sans --essai pour appliquer.")
        return 0

    for f, _l, anc, rem in a_faire:
        src[f] = src[f].replace(anc, rem, 1)
    for f in fichiers:
        bak = chemins[f] + ".bak"
        if not os.path.isfile(bak):
            shutil.copyfile(chemins[f], bak)
        io.open(chemins[f], "w", encoding="utf-8").write(src[f])
        dis("  ecrit : %s" % chemins[f])
    dis("")
    dis("  Aucun processus n a ete touche : ces deux fichiers sont des")
    dis("  lecteurs, lances a la main.")
    dis("")
    dis("  Verifie tout de suite :")
    dis("      python -m py_compile extraire_snapshots.py audit_cadence.py")
    dis("  Si ca affiche quoi que ce soit :")
    dis("      python patch_lecteurs_gz.py --defaire")
    return 0


if __name__ == "__main__":
    sys.exit(main())

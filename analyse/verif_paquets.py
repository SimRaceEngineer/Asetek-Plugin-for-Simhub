# -*- coding: utf-8 -*-
"""
verif_paquets.py -- quels paquets manquent pour faire tourner la stack ici.

LECTURE SEULE, ET SANS EXECUTER LA STACK. Il lit chaque .py, en extrait
les imports par analyse syntaxique (ast), et se contente de DEMANDER a
Python s il saurait les trouver (importlib.find_spec). Aucun module de
la stack n est execute : lancer 200 modules pour savoir ce qui manque
reviendrait a demarrer la stack, ce qu on veut precisement eviter.

Il ecarte :
  - la bibliotheque standard (sys.stdlib_module_names) ;
  - les modules de la stack elle-meme (un .py ou un dossier du meme nom) ;
  - claude_backup\\, qui n est pas du code de trading.

Il distingue deux categories, et la distinction compte :
  MANQUANT          l import est ferme -- le module plantera a coup sur.
  MANQUANT OPTIONNEL  l import est dans un try/except -- le code a prevu
                      son absence et continuera, peut-etre degrade.

Usage :
    python "G:\\Mon Drive\\ScalpEA\\verif_paquets.py" C:\\SVPS\\Scalp-EA-main
    python "G:\\Mon Drive\\ScalpEA\\verif_paquets.py"      (repertoire courant)
"""

import ast
import importlib.util
import os
import sys

IGNORE_DIRS = ("claude_backup", "__pycache__", ".git", "node_modules")

# Quelques noms d import qui ne portent pas le nom du paquet a installer.
PIP = {
    "MetaTrader5": "MetaTrader5",
    "cv2": "opencv-python",
    "yaml": "PyYAML",
    "PIL": "Pillow",
    "sklearn": "scikit-learn",
    "dateutil": "python-dateutil",
    "yfinance": "yfinance",
    "bs4": "beautifulsoup4",
    "win32api": "pywin32",
    "win32com": "pywin32",
    "win32con": "pywin32",
    "win32gui": "pywin32",
    "pythoncom": "pywin32",
    "psutil": "psutil",
    "serial": "pyserial",
    "OpenSSL": "pyOpenSSL",
    "zmq": "pyzmq",
    "google": "google-api-python-client",
}


def fichiers_py(racine):
    for base, dirs, fics in os.walk(racine):
        dirs[:] = [d for d in dirs if d.lower() not in IGNORE_DIRS]
        for f in fics:
            if f.endswith(".py"):
                yield os.path.join(base, f)


def lignes_protegees(arbre):
    """Lignes couvertes par un try qui rattrape une erreur d import.

    Un import dans un tel bloc est facultatif : le code a prevu de s en
    passer. Le confondre avec un import obligatoire ferait paniquer pour
    rien -- et l inverse ferait rater un vrai manque.
    """
    prot = set()
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Try):
            continue
        rattrape = False
        for h in n.handlers:
            if h.type is None:
                rattrape = True
                break
            noms = []
            if isinstance(h.type, ast.Name):
                noms = [h.type.id]
            elif isinstance(h.type, ast.Tuple):
                noms = [e.id for e in h.type.elts if isinstance(e, ast.Name)]
            if any(x in ("ImportError", "ModuleNotFoundError", "Exception")
                   for x in noms):
                rattrape = True
                break
        if not rattrape:
            continue
        for corps in n.body:
            for sub in ast.walk(corps):
                if hasattr(sub, "lineno"):
                    prot.add(sub.lineno)
    return prot


def imports_du_fichier(chemin):
    """Retourne {nom_racine: protege_partout} et l erreur de lecture s il y en a."""
    try:
        with open(chemin, "rb") as f:
            src = f.read()
    except OSError as e:
        return {}, "illisible : %s" % e
    try:
        arbre = ast.parse(src, filename=chemin)
    except SyntaxError as e:
        return {}, "syntaxe refusee par Python %d.%d : ligne %s" % (
            sys.version_info[0], sys.version_info[1], e.lineno)

    prot = lignes_protegees(arbre)
    trouves = {}
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            noms = [a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            # level > 0 = import relatif : c est du code local, pas un paquet.
            if n.level and n.level > 0:
                continue
            if not n.module:
                continue
            noms = [n.module.split(".")[0]]
        else:
            continue
        p = n.lineno in prot
        for nom in noms:
            if nom in trouves:
                trouves[nom] = trouves[nom] and p
            else:
                trouves[nom] = p
    return trouves, None


def main():
    racine = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    racine = os.path.abspath(racine)
    if not os.path.isdir(racine):
        print("Ce chemin n est pas un dossier : %s" % racine)
        return 1

    print("=" * 68)
    print("racine  : %s" % racine)
    print("python  : %s" % sys.version.split()[0])
    print("=" * 68)
    print("")

    fics = sorted(fichiers_py(racine))
    if not fics:
        print("Aucun fichier .py trouve. Mauvais chemin ?")
        return 1

    # Tout ce qui porte le nom d un fichier ou d un dossier de la stack
    # est du code local, pas un paquet a installer.
    locaux = set()
    for base, dirs, fs in os.walk(racine):
        if any(x in base.lower() for x in IGNORE_DIRS):
            continue
        for d in dirs:
            locaux.add(d)
        for f in fs:
            if f.endswith(".py"):
                locaux.add(f[:-3])

    std = set(getattr(sys, "stdlib_module_names", ()))

    besoins = {}       # nom -> [nb_fichiers, protege_partout]
    illisibles = []
    for c in fics:
        trouves, err = imports_du_fichier(c)
        if err:
            illisibles.append((os.path.relpath(c, racine), err))
            continue
        for nom, prot in trouves.items():
            if nom in std or nom in locaux or nom.startswith("_"):
                continue
            if nom in besoins:
                besoins[nom][0] += 1
                besoins[nom][1] = besoins[nom][1] and prot
            else:
                besoins[nom] = [1, prot]

    presents = []
    manquants = []
    optionnels = []
    for nom, (nb, prot) in besoins.items():
        try:
            dispo = importlib.util.find_spec(nom) is not None
        except (ImportError, ValueError, AttributeError):
            dispo = False
        if dispo:
            presents.append((nb, nom))
        elif prot:
            optionnels.append((nb, nom))
        else:
            manquants.append((nb, nom))

    presents.sort(reverse=True)
    manquants.sort(reverse=True)
    optionnels.sort(reverse=True)

    print("%d fichiers .py lus, %d paquets tiers references."
          % (len(fics), len(besoins)))
    print("")

    print("-" * 68)
    print("MANQUANTS -- import ferme, le module plantera")
    print("-" * 68)
    if not manquants:
        print("aucun.")
    else:
        print("%6s  %-24s %s" % ("usages", "import", "a installer"))
        for nb, nom in manquants:
            print("%6d  %-24s %s" % (nb, nom, PIP.get(nom, nom)))
    print("")

    print("-" * 68)
    print("MANQUANTS OPTIONNELS -- dans un try/except, degrade mais vivant")
    print("-" * 68)
    if not optionnels:
        print("aucun.")
    else:
        print("%6s  %-24s %s" % ("usages", "import", "a installer"))
        for nb, nom in optionnels:
            print("%6d  %-24s %s" % (nb, nom, PIP.get(nom, nom)))
    print("")

    print("-" * 68)
    print("PRESENTS (%d)" % len(presents))
    print("-" * 68)
    print("  ".join(n for _nb, n in presents) or "aucun.")
    print("")

    if illisibles:
        print("-" * 68)
        print("FICHIERS NON ANALYSES (%d)" % len(illisibles))
        print("-" * 68)
        for rel, err in illisibles[:40]:
            print("   %s" % rel)
            print("      %s" % err)
        if len(illisibles) > 40:
            print("   ... et %d autres" % (len(illisibles) - 40))
        print("")
        print("Une syntaxe refusee ici n est pas forcement une faute : ce")
        print("Python est en %s, le VPS tourne en 3.14."
              % sys.version.split()[0])
        print("")

    if manquants:
        print("=" * 68)
        print("A INSTALLER, en une commande :")
        print("")
        print("pip install " + " ".join(PIP.get(n, n) for _nb, n in manquants))
        print("=" * 68)
    else:
        print("=" * 68)
        print("Rien d obligatoire ne manque.")
        print("=" * 68)

    print("")
    print("Lecture seule : aucun module de la stack n a ete execute.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

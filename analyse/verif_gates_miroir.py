#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verif_gates_miroir.py -- le miroir subit-il des gates, oui ou non.

LA QUESTION
-----------
Les gates de la stack s installent en remplacant mt5.order_send. Un
monkey-patch ne vaut que dans le processus qui l a pose : le moteur les
installe chez lui, le miroir tourne dans un processus separe.

miroir_papers.py n importe aucun gate en direct. Mais il importe
churn_trade_logger et papers_moteur, qui importent a leur tour d autres
modules de la stack. Si l un d eux, a n importe quel etage, appelle
install() au chargement, le patch s applique aussi au miroir.

CE QUE FAIT CE SCRIPT
---------------------
Il remonte tout l arbre des imports depuis un module de depart, par
lecture `ast`. **Il n execute aucun module de la stack** -- c est la
seule facon sure d analyser du code qui, importe pour de vrai,
declencherait des connexions MT5 et des effets de bord.

Pour chaque module atteint il signale :
  - s il porte un nom de gate, ou s il contient `mt5.order_send =`
  - s il appelle install() **au niveau module**, donc au chargement

Un import de gate est inoffensif tant que install() n est pas appele.
C est l appel au niveau module qui compte, pas l import.

Chaque module signale est affiche avec la chaine d imports qui y mene,
pour qu on voie par ou ca passe.

USAGE
-----
    python verif_gates_miroir.py
    python verif_gates_miroir.py --depart trading_engine.py
    python verif_gates_miroir.py --racine D:\\autre\\chemin
"""

from __future__ import annotations

import argparse
import ast
import io
import os
import sys
from collections import deque

RACINE_DEFAUT = r"C:\SVPS\Scalp-EA-main"
DEPART_DEFAUT = "miroir_papers.py"


def lire(chemin):
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        return f.read()


def imports_de(arbre):
    """Noms de modules importes, tous niveaux d indentation confondus."""
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for a in noeud.names:
                noms.add(a.name.split(".")[0])
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level == 0 and noeud.module:
                noms.add(noeud.module.split(".")[0])
    return noms


def _appels(noeud):
    """Nom de la fonction appelee, pour un noeud Call. '' si indechiffrable."""
    f = noeud.func
    if isinstance(f, ast.Attribute):
        cible = f.value.id if isinstance(f.value, ast.Name) else "?"
        return "%s.%s" % (cible, f.attr)
    if isinstance(f, ast.Name):
        return f.id
    return ""


def installs_au_niveau_module(arbre):
    """Appels a install() executes au chargement du module.

    On ne descend pas dans les def/class : un install() dans une fonction
    ne se declenche que si quelqu un appelle cette fonction, ce qui n est
    pas la question ici.

    On regarde le corps du module, plus les corps de if/try/with/for, qui
    s executent bien au chargement.
    """
    trouves = []

    def parcourir(corps):
        for n in corps:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for sous in ast.walk(n):
                if isinstance(sous, ast.Call):
                    nom = _appels(sous)
                    if nom.endswith("install") or nom == "install":
                        trouves.append((getattr(sous, "lineno", 0), nom))
    parcourir(arbre.body)
    return trouves


def analyser(racine, depart):
    """Parcours en largeur de l arbre des imports. Renvoie un dict."""
    chemin_depart = os.path.join(racine, depart)
    if not os.path.isfile(chemin_depart):
        return None

    vus = {depart: None}          # module -> parent
    file = deque([depart])
    resultats = {}
    illisibles = []

    while file:
        nom_fichier = file.popleft()
        chemin = os.path.join(racine, nom_fichier)
        try:
            source = lire(chemin)
            arbre = ast.parse(source, nom_fichier)
        except Exception as e:
            illisibles.append((nom_fichier, str(e)[:60]))
            continue

        module = nom_fichier[:-3]
        resultats[module] = {
            "patche_order_send": "mt5.order_send =" in source,
            "nom_de_gate": module.endswith("_gate") or module.startswith("gate_"),
            "installs": installs_au_niveau_module(arbre),
        }

        for nom in sorted(imports_de(arbre)):
            candidat = nom + ".py"
            if candidat in vus:
                continue
            if os.path.isfile(os.path.join(racine, candidat)):
                vus[candidat] = nom_fichier
                file.append(candidat)

    return {"vus": vus, "resultats": resultats, "illisibles": illisibles}


def chaine(vus, nom_fichier):
    """Remonte la chaine d imports jusqu au depart."""
    morceaux = []
    courant = nom_fichier
    while courant is not None:
        morceaux.append(courant[:-3])
        courant = vus.get(courant)
    return " -> ".join(reversed(morceaux))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=RACINE_DEFAUT)
    ap.add_argument("--depart", default=DEPART_DEFAUT)
    args = ap.parse_args()

    print("=" * 70)
    print("verif_gates_miroir -- depart : %s" % args.depart)
    print("=" * 70)

    if not os.path.isdir(args.racine):
        print("racine introuvable : %s" % args.racine)
        return 2

    donnees = analyser(args.racine, args.depart)
    if donnees is None:
        print("%s introuvable dans %s" % (args.depart, args.racine))
        return 2

    vus = donnees["vus"]
    res = donnees["resultats"]
    print("modules de la stack atteints : %d" % len(res))
    if donnees["illisibles"]:
        print("illisibles (%d) :" % len(donnees["illisibles"]))
        for nom, err in donnees["illisibles"]:
            print("   %-34s %s" % (nom, err))

    patcheurs = sorted(m for m, d in res.items() if d["patche_order_send"])
    gates = sorted(m for m, d in res.items()
                   if d["nom_de_gate"] and not d["patche_order_send"])
    installeurs = sorted(m for m, d in res.items() if d["installs"])

    print("")
    print("-" * 70)
    print("1. Modules atteints qui remplacent mt5.order_send")
    print("-" * 70)
    if not patcheurs:
        print("   AUCUN.")
    for m in patcheurs:
        print("   %s" % m)
        print("      %s" % chaine(vus, m + ".py"))

    print("")
    print("-" * 70)
    print("2. Modules atteints portant un nom de gate (sans patch)")
    print("-" * 70)
    if not gates:
        print("   aucun.")
    for m in gates:
        print("   %-34s %s" % (m, chaine(vus, m + ".py")))

    print("")
    print("-" * 70)
    print("3. Appels a install() AU CHARGEMENT -- c est ce qui compte")
    print("-" * 70)
    if not installeurs:
        print("   AUCUN.")
    for m in installeurs:
        for ligne, nom in res[m]["installs"]:
            print("   %-30s ligne %-5d %s()" % (m, ligne, nom))
        print("      %s" % chaine(vus, m + ".py"))

    print("")
    print("=" * 70)
    if not patcheurs and not installeurs:
        print("VERDICT : aucun gate ne s installe dans ce processus.")
        print("Les ordres partent vers MT5 sans etre examines.")
    elif not installeurs:
        print("VERDICT : des modules capables de patcher sont importes,")
        print("mais aucun ne s installe au chargement. A confirmer en")
        print("cherchant qui appelle leur install() ailleurs.")
    else:
        print("VERDICT : au moins un gate s installe au chargement.")
        print("Le processus est donc filtre. Voir la section 3.")
    print("=" * 70)
    print("Lecture par ast uniquement -- aucun module de la stack n a ete")
    print("execute, aucune connexion MT5 ouverte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

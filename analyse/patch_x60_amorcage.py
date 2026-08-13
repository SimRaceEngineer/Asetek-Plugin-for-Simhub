# -*- coding: utf-8 -*-
"""
patch_x60_amorcage.py -- redemarrer l observateur sans inventer d entrees

  python patch_x60_amorcage.py --essai
  python patch_x60_amorcage.py

LE DEFAUT, CONSTATE LE 13/08 A 13:20

    x60_onset tient un dictionnaire `connus` des tickets deja vus. Il
    part VIDE a chaque demarrage :

        connus = {}
        ...
        if t not in connus:
            connus[t] = {...}
            if connus[t]["x60"]:
                ecrire({"quoi": "X60_ENTREE", ...})

    Donc au redemarrage, chaque position x60 DEJA OUVERTE est
    enregistree comme une nouvelle entree, horodatee a l instant du
    demarrage. Une entree qui n a jamais eu lieu.

    C est exactement l artefact du papier du 12/08 a 23:38:54 -- huit
    positions ouvertes a la meme seconde parce que `armes` partait
    vide -- corrige la, et jamais applique ici.

    Il s est produit le 13/08 vers 13:20, quand l observateur a ete
    relance apres le redemarrage du moteur.

CE QUE CA FAUSSE

    Les sections qui comptent les entrees x60 : AVEC OU CONTRE, QUI EST
    LA QUAND UN x60 ENTRE, PAR SEANCE, PAR HEURE. Une fausse entree
    apporte un plateau complet de tierces qui n accompagnaient rien.

    Sur huit a dix entrees reelles depuis le 12/08 au soir, deux ou
    trois fausses ne se noient pas : elles pesent un quart du total.

CE QUE LE PATCH FAIT

    Une passe d amorcage avant la boucle : les positions deja ouvertes
    entrent dans `connus` SANS qu aucun evenement soit ecrit. Elles ne
    viennent pas d ouvrir, et les compter comme telles fausserait tout.

    Elles restent suivies normalement -- pic, creux, cloture. Seule
    l entree, qu on n a pas vue, n est pas inventee.

    L amorcage AFFICHE combien de positions il enregistre et combien
    sont des x60. Un amorcage muet laisserait croire au demarrage
    suivant qu il ne s est rien passe.

CE QU IL FAUT FAIRE DES FAUSSES ENTREES DEJA ECRITES

    Ce patch empeche les prochaines, il n efface pas les precedentes.
    Celles du 13/08 vers 13:20 sont dans docs/x60_onset/events.jsonl et
    resteront dans les compteurs. Pour les sortir, meme methode que
    pour le papier : les archiver a cote plutot que les supprimer.

UNE ANCRE, verifiee unique. IDEMPOTENT. Sauvegarde horodatee.
ast.parse, puis controle sur l arbre que l amorcage est bien DANS
boucle() et AVANT le while -- pose apres, il ne servirait a rien et
compilerait tout aussi bien.

PREND EFFET AU PROCHAIN DEMARRAGE de l observateur.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "x60_onset.py"
MARQUEUR = "amorcage"

ANCRE = '''    connus = {}          # ticket -> {magic, actif, pic, creux, ouvert}
    prochaine_veille = 0.0
'''

NEUF = '''    connus = {}          # ticket -> {magic, actif, pic, creux, ouvert}
    # AMORCAGE. `connus` part vide, donc sans cette passe chaque
    # position x60 DEJA ouverte serait enregistree comme une nouvelle
    # entree, horodatee a l instant du demarrage -- une entree qui n a
    # jamais eu lieu. C est l artefact du papier du 12/08 a 23:38:54,
    # corrige la et jamais applique ici ; il s est reproduit le 13/08
    # vers 13:20 au redemarrage qui a suivi celui du moteur.
    # Les positions restent suivies normalement -- pic, creux, cloture.
    # Seule l entree, qu on n a pas vue, n est pas inventee.
    _amorce = mt5.positions_get() or ()
    for _p in _amorce:
        _l = float(_p.profit)
        connus[int(_p.ticket)] = {
            "magic": int(_p.magic), "actif": str(_p.symbol),
            "pic": _l, "creux": _l, "dernier": _l,
            "ouvert": datetime.fromtimestamp(_p.time).strftime(
                "%Y-%m-%dT%H:%M:%S"),
            "x60": est_x60(_p.magic)}
    _n60 = len([1 for _p in _amorce if est_x60(_p.magic)])
    print("amorcage : %d position(s) deja ouverte(s) enregistree(s),"
          " dont %d x%s." % (len(_amorce), _n60, SETUP))
    print("Aucun evenement n est ecrit pour elles : elles n ont pas")
    print("ouvert maintenant, et les compter ainsi fausserait les")
    print("sections qui denombrent les entrees.")
    print()
    prochaine_veille = 0.0
'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    n = src.count(ANCRE)
    if n != 1:
        print("KO : %d occurrence(s) de l ancre, il en faut 1." % n)
        print("Rien n a ete ecrit.")
        return 1

    neuf = src.replace(ANCRE, NEUF, 1)

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # Pose APRES le while, l amorcage compilerait aussi bien et ne
    # servirait a rien : les entrees fausses seraient deja ecrites.
    # On verifie donc sa place sur l arbre, pas seulement sa presence.
    ok = False
    for f in ast.walk(arbre):
        if not (isinstance(f, ast.FunctionDef) and f.name == "boucle"):
            continue
        for i, nd in enumerate(f.body):
            if isinstance(nd, ast.Assign) and "_amorce" in ast.dump(nd):
                reste = f.body[i + 1:]
                ok = any(isinstance(x, (ast.Try, ast.While)) for x in reste)
    if not ok:
        print("KO : l amorcage n est pas dans boucle() avant la boucle.")
        print("     Pose apres, il ne servirait a rien -- les fausses")
        print("     entrees seraient deja ecrites. Rien n a ete ecrit.")
        return 1
    print("Arbre verifie : l amorcage precede la boucle, dans boucle().")

    print()
    print("Au prochain demarrage, les positions deja ouvertes entreront")
    print("dans `connus` sans qu aucun X60_ENTREE soit ecrit pour elles.")
    print()
    print("Ce patch empeche les prochaines fausses entrees, il n efface")
    print("pas celles du 13/08 vers 13:20 : elles sont dans")
    print("docs/x60_onset/events.jsonl et restent dans les compteurs.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. PREND EFFET AU PROCHAIN DEMARRAGE de l observateur.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

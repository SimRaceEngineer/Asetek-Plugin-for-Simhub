# -*- coding: utf-8 -*-
"""
patch_papier_depuis.py -- exclure les artefacts de demarrage du rapport

  python patch_papier_depuis.py --essai
  python patch_papier_depuis.py

  puis :  python papier_tf.py --rapport --depuis 2026-08-13T00:00

CE QU IL CORRIGE, ET POURQUOI CA CHANGE LA CONCLUSION

    Le 12/08 a 23:38:54, huit cellules ont ouvert a la meme seconde :
    l artefact de demarrage, corrige depuis par patch_papier_amorcage.
    Elles portaient sur H1, M30 et M20.

    Releve du 13/08 09:56 : la ligne 23h du tableau horaire affiche
    8 entrees pour -260.26 EUR. Or M20, M30 et H1 totalisent -270.28 a
    elles trois. La quasi-totalite de leurs pertes EST cette fournee.

    Sans filtre, on lirait « les durees moyennes perdent » alors qu on
    mesure huit entrees correlees ouvertes ensemble au lancement, sur
    aucun signal. C est la difference entre un resultat et un artefact,
    et elle est ici de l ordre de 100 % du chiffre.

CE QU IL AJOUTE

    --depuis AAAA-MM-JJTHH:MM : le rapport ne compte que les entrees
    ouvertes A PARTIR de cet instant. Il ECRIT combien il a ecarte et
    a partir de quand -- un filtre muet serait pire que pas de filtre.

    Les positions encore ouvertes et les veilles ne sont pas filtrees :
    elles decrivent le present, pas l historique.

IL CORRIGE AUSSI trois %% qui s affichaient litteralement dans les
notes du rapport -- « 70 %% du volume ». Cosmetique, mais c est un
texte lu tous les jours.

QUATRE ANCRES, verifiees uniques. IDEMPOTENT. Sauvegarde horodatee.
ast.parse avant ecriture. Le rapport est une lecture : l observateur
qui tourne n a pas besoin d etre redemarre.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "papier_tf.py"
MARQUEUR = "--depuis"

RE_DEF = re.compile(r'^def rapport\(\):$', re.M)

RE_TETE = re.compile(
    r'^([ \t]*)ev = charger_trades\(\)\n'
    r'[ \t]*tr = \[e for e in ev if e\.get\("quoi"\) == "TRADE"\]\n'
    r'[ \t]*entrees = par_entree\(tr\)$', re.M)

RE_ARG = re.compile(
    r'^([ \t]*)p\.add_argument\("--pas", type=int, default=PAS\)$', re.M)

RE_APPEL = re.compile(r'^([ \t]*)for l in rapport\(\):$', re.M)

PC = (('L.append("  le 207 les 70 %% du volume coupes au premier break de la")',
       'L.append("  le 207 les 70 % du volume coupes au premier break de la")'),
      ('L.append("  production : sur H2 et H4 les 70 %% partiront tres tot, et")',
       'L.append("  production : sur H2 et H4 les 70 % partiront tres tot, et")'),
      ('L.append("  M2 coupe les 70 %% presque tout de suite, ce qui rabote la")',
       'L.append("  M2 coupe les 70 % presque tout de suite, ce qui rabote la")'))

TETE = '''@I@ev = charger_trades()
@I@tr = [e for e in ev if e.get("quoi") == "TRADE"]
@I@entrees = par_entree(tr)
@I@# Le filtre porte sur l heure d OUVERTURE, pas de cloture : une
@I@# entree du 12/08 fermee le 13 reste une entree du 12. Filtrer sur
@I@# la cloture laisserait passer les artefacts de demarrage, qui sont
@I@# precisement ce qu on veut ecarter.
@I@ecartees = 0
@I@if depuis:
@I@    avant = len(entrees)
@I@    entrees = [e for e in entrees if e["ouvert"] >= depuis]
@I@    ecartees = avant - len(entrees)
@I@    gardes = set(e["id"] for e in entrees)
@I@    tr = [e for e in tr
@I@          if (e.get("id") or "") in gardes or not e.get("id")]'''

NOTE = '''@I@if depuis:
@I@    L.append("")
@I@    L.append("  FILTRE : seules les entrees ouvertes a partir du %s"
@I@             % depuis.replace("T", " "))
@I@    L.append("  sont comptees. %d entree(s) anterieure(s) ecartee(s)."
@I@             % ecartees)
@I@    L.append("  Les positions encore ouvertes et la couverture ne sont")
@I@    L.append("  PAS filtrees : elles decrivent le present.")
'''


def pose(g, i):
    return g.replace("@I@", i)


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

    for nom, rx in (("def rapport()", RE_DEF),
                    ("le chargement du rapport", RE_TETE),
                    ("l argument --pas", RE_ARG),
                    ("l appel a rapport()", RE_APPEL)):
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1
    # Les %% sont une correction COSMETIQUE et deja faite dans certaines
    # copies. Zero occurrence n est pas une anomalie : on saute. Deux le
    # serait -- on refuse alors, parce qu on ne saurait pas laquelle.
    for avant, _apres in PC:
        if src.count(avant) > 1:
            print("KO : la note contenant %s apparait %d fois."
                  % (avant[12:40], src.count(avant)))
            print("Rien n a ete ecrit.")
            return 1
    deja = sum(1 for avant, _a in PC if src.count(avant) == 0)

    neuf = RE_DEF.sub("def rapport(depuis=None):", src, count=1)
    neuf = RE_TETE.sub(lambda m: pose(TETE, m.group(1)), neuf, count=1)
    neuf = RE_ARG.sub(
        lambda m: (m.group(0) + "\n" + m.group(1)
                   + 'p.add_argument("--depuis",\n' + m.group(1)
                   + '               help="AAAA-MM-JJTHH:MM -- ne compter'
                     ' que les entrees\\n"\n' + m.group(1)
                   + '                    "ouvertes a partir de la")'),
        neuf, count=1)
    neuf = RE_APPEL.sub(lambda m: m.group(1) + "for l in rapport(a.depuis):",
                        neuf, count=1)

    # La note du filtre, juste apres la ligne de couverture en tete.
    ancre = ('    L.append("du %s au %s" % (ev[0]["ts"][:16],'
             ' ev[-1]["ts"][:16]))')
    if neuf.count(ancre) != 1:
        print("KO : la ligne de periode n est pas unique. Rien n a ete ecrit.")
        return 1
    neuf = neuf.replace(ancre, ancre + "\n" + pose(NOTE, "    ").rstrip("\n"),
                        1)

    for avant, apres in PC:
        if avant in neuf:
            neuf = neuf.replace(avant, apres, 1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("--depuis AAAA-MM-JJTHH:MM ecarte les entrees ouvertes avant.")
    print("Le rapport ECRIT combien il en a ecarte : un filtre muet")
    print("serait pire que pas de filtre.")
    print()
    print("A utiliser tout de suite :")
    print("  python papier_tf.py --rapport --depuis 2026-08-13T00:00")
    print("pour sortir les huit entrees de 23:38:54, qui portent")
    print("l essentiel des pertes de M20, M30 et H1.")
    print()
    if deja == len(PC):
        print("Les %% litteraux etaient deja corriges dans cette copie.")
    else:
        print("Corrige aussi %d %% qui s affichaient litteralement."
              % (len(PC) - deja))

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. C est une lecture : rien a redemarrer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
patch_papier_jambes.py -- ne plus compter une position ouverte comme un trade

  python patch_papier_jambes.py --essai
  python patch_papier_jambes.py

LE DEFAUT, MESURE LE 13/08 A 11:20

    Le bras 207 sort en DEUX temps : 70 % du volume au premier break de
    la bougie M2, puis les 30 % restants au reverse. Les deux jambes
    portent le meme identifiant, et par_entree() les regroupe.

    Mais elle considere l entree comme close des qu une jambe existe.
    Une position dont les 70 % ont ete coupes et dont les 30 % courent
    encore etait donc comptee comme un trade TERMINE, avec pour seul
    resultat son gain partiel.

    Et ce gain est POSITIF PAR CONSTRUCTION : partiel() ne se declenche
    qu en profit. On enregistrait donc un gain garanti pour une position
    dont on ignorait l issue.

    Mesure : 37 entrees comptees, dont 9 dans ce cas, TOUTES du bras
    207 -- 207110, 207120, 207130, 207160, 207220, 207230, 207310,
    207320, 207330.

CE QUE CA FAUSSAIT, ET DE COMBIEN

    Le tableau « par duree et par bras » donnait le 207 gagnant sur les
    quatre durees observees :

        M10  206  7 entrees   +93.94        M10  207  9  +156.05
        M20  206  2           -60.99        M20  207  5   +32.71
        M30  206  3           -52.37        M30  207  6   +42.15
        H1   206  2           -71.77        H1   207  3    +9.32

    Les deux bras entrent sur EXACTEMENT le meme signal : leurs N
    doivent etre egaux. Les ecarts -- 2, 3, 3, 1 -- font 9, le compte
    exact des positions fantomes. Quatre victoires sur quatre, toutes
    fabriquees par le compteur.

CE QUE LE PATCH FAIT

    par_entree() ne rend plus que les entrees ayant une jambe de sortie
    AUTRE que PARTIEL70 -- c est-a-dire reellement fermees. Les autres
    sont ecartees et le rapport DIT combien : une correction silencieuse
    laisserait croire que les chiffres n ont pas bouge.

    Elles ne sont pas perdues : elles reapparaitront dans le rapport
    des que leurs 30 % se fermeront, avec leur resultat complet.

DEUX ANCRES, verifiees uniques. IDEMPOTENT. Sauvegarde horodatee.
ast.parse avant ecriture. C est une lecture : rien a redemarrer.
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
MARQUEUR = "partiels_ouverts"

RE_RETOUR = re.compile(
    r'^([ \t]*)if e\.get\("motif"\) != "PARTIEL70":\n'
    r'([ \t]*)d\["motif"\] = e\.get\("motif"\)\n'
    r'([ \t]*)return list\(g\.values\(\)\)$', re.M)

RE_TETE = re.compile(
    r'^([ \t]*)L\.append\("%d entrees papier fermees \(%d jambes\), %d'
    r' ouvertes, %\.1f h"\n'
    r'[ \t]*" d observation"\n'
    r'[ \t]*% \(len\(entrees\), len\(tr\), len\(ouvertes\),\n'
    r'[ \t]*len\(veilles\) \* VEILLE_MIN / 60\.0\)\)$', re.M)

RETOUR = '''@I@if e.get("motif") != "PARTIEL70":
@J@d["motif"] = e.get("motif")
@K@# Une entree dont SEULE la jambe PARTIEL70 existe n est PAS close :
@K@# le 207 a coupe 70 % en profit et les 30 % courent encore. La
@K@# compter enregistrerait un gain positif par construction --
@K@# partiel() ne se declenche qu en profit -- pour une position dont
@K@# on ignore l issue. Le 13/08 a 11:20 : 9 entrees dans ce cas,
@K@# toutes du bras 207, ce qui lui donnait 4 durees gagnantes sur 4.
@K@# Elles reviendront au rapport quand leurs 30 % se fermeront.
@K@return [d for d in g.values() if d["motif"] is not None]'''

TETE = '''@I@partiels_ouverts = len([d for d in par_entree_brut(tr)
@I@                        if d["motif"] is None])
@I@L.append("%d entrees papier fermees (%d jambes), %d ouvertes, %.1f h"
@I@         " d observation"
@I@         % (len(entrees), len(tr), len(ouvertes),
@I@            len(veilles) * VEILLE_MIN / 60.0))
@I@if partiels_ouverts:
@I@    L.append("%d entree(s) du bras 207 ecartee(s) : leurs 70 %% ont ete"
@I@             % partiels_ouverts)
@I@    L.append("coupes en profit mais les 30 %% courent encore. Les compter")
@I@    L.append("donnerait un gain positif par construction pour une position")
@I@    L.append("dont on ignore l issue. Elles reviendront a leur cloture.")'''

BRUT = '''def par_entree_brut(tr):
    """par_entree SANS le filtre des positions encore ouvertes.

    Sert uniquement a compter combien on ecarte, pour le dire dans le
    rapport. Un filtre silencieux laisserait croire que les chiffres
    n ont pas bouge."""
    g = {}
    for e in tr:
        i = e.get("id") or "%s@%s" % (e.get("k"), e.get("ouvert", e["ts"]))
        d = g.setdefault(i, {"motif": None})
        if e.get("motif") != "PARTIEL70":
            d["motif"] = e.get("motif")
    return list(g.values())


'''


def pose(g, i, j, k):
    return g.replace("@I@", i).replace("@J@", j).replace("@K@", k)


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

    for nom, rx in (("le retour de par_entree", RE_RETOUR),
                    ("la ligne de couverture", RE_TETE)):
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1

    m = RE_RETOUR.search(src)
    # group(3) est l indentation du `return`, au niveau de la FONCTION.
    # Lui passer group(1) -- celle du `if`, dans la boucle -- placerait le
    # return dans le for : il rendrait apres la premiere entree. Vu au
    # test fonctionnel, pas a la compilation : les deux versions compilent.
    neuf = (src[:m.start()]
            + pose(RETOUR, m.group(1), m.group(2), m.group(3))
            + src[m.end():])

    mt = RE_TETE.search(neuf)
    neuf = (neuf[:mt.start()] + pose(TETE, mt.group(1), "", "")
            + neuf[mt.end():])

    # par_entree_brut se pose juste avant par_entree.
    md = re.search(r'^def par_entree\(tr\):$', neuf, re.M)
    if not md:
        print("KO : def par_entree a disparu. Rien n a ete ecrit.")
        return 1
    neuf = neuf[:md.start()] + BRUT + neuf[md.start():]

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("par_entree n ecarte plus que les entrees reellement fermees.")
    print("Le rapport DIT combien il en ecarte : une correction muette")
    print("laisserait croire que les chiffres n ont pas bouge.")
    print()
    print("Attends-toi a voir le 207 perdre son avantage sur les quatre")
    print("durees -- il etait entierement porte par ces neuf gains")
    print("partiels, positifs par construction.")

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

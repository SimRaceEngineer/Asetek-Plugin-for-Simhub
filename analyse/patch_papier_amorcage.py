# -*- coding: utf-8 -*-
"""
patch_papier_amorcage.py -- ne plus ouvrir 36 positions au demarrage

  python patch_papier_amorcage.py --essai
  python patch_papier_amorcage.py

LE DEFAUT, VU EN DIRECT LE 12/08 A 23:38:54

    Huit cellules ont ouvert A LA MEME SECONDE, toutes SELL :

        206160 H1 US30      207160 H1 US30
        206230 M30 US500    207230 M30 US500
        206320 M20 US100    207320 M20 US100
        206330 M30 US100    207330 M30 US100

    Ce ne sont pas huit signaux. `armes` demarre vide, donc la premiere
    evaluation de chaque cellule prend l ignition EN COURS pour une
    ignition FRAICHE. Toutes les cellules alignees entrent ensemble, a
    l instant du lancement.

    ignition_trader a le meme comportement -- _armed y demarre vide
    aussi. Mais il redemarre rarement et son but est de trader. Ici le
    but est de MESURER six durees sur dix-huit jours, et chaque
    redemarrage injecterait une fournee de trades correles rattaches a
    aucun evenement de marche. Sur une etude, c est du bruit qu on
    fabrique soi-meme.

CE QUE LE PATCH FAIT

    Un tour d AMORCAGE avant la boucle : il lit chaque cellule, note sa
    direction d ignition courante et l horodatage de sa derniere barre
    close, et n ouvre RIEN. La premiere entree possible devient donc la
    premiere ignition qui arrive APRES le demarrage.

    Effet de bord voulu : redemarrer papier_tf devient gratuit. On peut
    le relancer autant qu on veut sans salir le journal.

CE QU IL NE CHANGE PAS

    Ni la regle d entree, ni les sorties, ni le 207, ni les horaires.
    Une seule chose : ce qui se passe pendant les vingt premieres
    secondes.

    Les 8 positions ouvertes le 12/08 a 23:38:54 restent ouvertes et
    seront gerees normalement. Elles resteront des artefacts de
    demarrage -- il faut s en souvenir en lisant le premier relevé, et
    c est la derniere fois.

IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
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
MARQUEUR = "amorcage"

RE_ANCRE = re.compile(
    r'^([ \t]*)armes = \{\}\n([ \t]*)derniere = \{\}\n'
    r'([ \t]*)prochaine_veille = 0\.0$', re.M)

BLOC = '''
%(i)s# AMORCAGE -- 12/08/2026, 23:38:54 : huit cellules avaient ouvert a
%(i)s# la meme seconde au lancement. `armes` demarre vide, donc la
%(i)s# premiere evaluation prend l ignition EN COURS pour une ignition
%(i)s# FRAICHE et toutes les cellules alignees entrent ensemble.
%(i)s# ignition_trader fait pareil, mais il redemarre rarement et son
%(i)s# but est de trader. Ici le but est de mesurer : on arme a vide,
%(i)s# la premiere entree possible est la premiere ignition d APRES le
%(i)s# demarrage. Relancer papier_tf devient gratuit.
%(i)sfor _c in grille:
%(i)s    _cel = cellule(_c["sym"], _c["tf"])
%(i)s    if _cel and _cel.get("ignition"):
%(i)s        armes[_c["k"]] = _cel.get("dir")
%(i)s    _r0 = mt5.copy_rates_from_pos(_c["sym"], _c["tf"], 0, 2)
%(i)s    if _r0 is not None and len(_r0) >= 2:
%(i)s        derniere[_c["k"]] = int(_r0[-2]["time"])
%(i)sprint("amorcage : %%d cellules armees sans entrer -- la premiere"
%(i)s      " entree sera la premiere ignition d apres maintenant."
%(i)s      %% len(grille))
%(i)sprint()
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

    n = len(RE_ANCRE.findall(src))
    if n != 1:
        print("KO : %d occurrence(s) de l initialisation de la boucle, il en"
              " faut 1." % n)
        print("Rien n a ete ecrit.")
        return 1

    m = RE_ANCRE.search(src)
    neuf = (src[:m.end()] + (BLOC % {"i": m.group(1)}).rstrip("\n")
            + src[m.end():])

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Un tour d amorcage est ajoute avant la boucle : il lit les 36")
    print("cellules, note leur direction et leur derniere barre, et")
    print("n ouvre rien. La premiere entree sera la premiere ignition")
    print("d apres le demarrage.")
    print()
    print("Les positions deja ouvertes ne sont pas touchees : elles")
    print("restent gerees normalement, et resteront des artefacts de")
    print("demarrage dans le premier releve.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Redemarre papier_tf.py pour que ca prenne effet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

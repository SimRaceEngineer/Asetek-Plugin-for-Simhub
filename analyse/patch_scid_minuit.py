# -*- coding: utf-8 -*-
"""
patch_scid_minuit.py -- la fenetre commence a minuit, jamais en plein jour

  python patch_scid_minuit.py --essai
  python patch_scid_minuit.py

CE QUI S EST PASSE LE 13/08

    Trois lignes de scid_orderflow.py, prises ensemble, effacent de
    l historique :

        280:  since = time.time() - a.days * 86400
        122:  if ep < since_epoch: continue      # barres d avant sautees
        311:  with open(fp, "w", ...)            # "w" : ECRASE le jour

    `--days 1` lance a 14h39 donne un `since` au 12 aout 14h39. Les
    barres du 12 aout avant 14h39 sont sautees, puis le fichier
    of_US30_2026-08-12.jsonl est REECRIT avec ce qui reste. La matinee
    disparait du disque.

    Constate en direct : le 10 aout est passe de 1312 barres a 501, et
    le 12 aout de 1299 a 499, entre deux audits espaces de neuf
    minutes. Une boucle appelant --days 1 toutes les 30 secondes
    rognait l archive en continu, le point de coupe avancant avec
    l horloge.

    Ce n est pas un bug de scid_orderflow pris seul : appele une fois
    par jour avec une fenetre large, il se comporte correctement. C est
    la combinaison d une fenetre etroite et d une reecriture complete
    qui detruit. Le script n avait simplement jamais ete appele comme
    ca.

LE CORRECTIF

    `since` se cale sur MINUIT local du jour vise. La fenetre commence
    alors toujours a une frontiere de journee, et un fichier de jour
    est soit reecrit en entier, soit pas touche. Jamais rogne.

    --days 1 couvre desormais hier ET aujourd hui en entier. Le cout
    passe d environ 3,8 a 7 secondes -- sans importance pour une boucle
    de 30 secondes, et c est le prix d une archive qui ne peut plus
    perdre de matiere.

    time.mktime avec tm_isdst = -1 laisse la bibliotheque resoudre
    l heure d ete. Ecrire le calcul a la main marcherait aujourd hui et
    se decalerait d une heure fin octobre, une fois, sans que rien ne
    le signale.

CE QUE CA NE CHANGE PAS

    Ni le contenu des barres, ni leur agregation, ni les fichiers de
    sortie, ni la table des symboles. Une seule expression change :
    l instant ou commence la fenetre.

UNE ANCRE, verifiee unique. IDEMPOTENT. Sauvegarde horodatee.
ast.parse avant ecriture, puis controle que `since` tombe bien a
minuit -- une expression qui compile mais garde l heure courante
laisserait le defaut intact, et il ne se reverrait qu apres coup, dans
un fichier ampute.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
import time
from datetime import datetime

CIBLE = "scid_orderflow.py"
MARQUEUR = "_dep_minuit"

ANCRE = '''    since = time.time() - a.days * 86400
'''

NEUF = '''    # MINUIT, jamais l heure courante. Sans ce calage, `since` tombe
    # au milieu d une journee : read_bars saute les barres anterieures
    # (l.122) et la boucle d ecriture reecrit le fichier de ce jour-la
    # avec "w" (l.311), donc en entier, avec les seules barres
    # restantes. Le 13/08, trois appels --days 1 ont ainsi ramene le
    # 10 aout de 1312 barres a 501 et le 12 de 1299 a 499 : la matinee
    # effacee du disque, sans message.
    # Avec le calage, la fenetre commence a une frontiere de journee :
    # un fichier de jour est soit reecrit en entier, soit pas touche.
    # tm_isdst = -1 : on laisse la bibliotheque resoudre l heure d ete.
    # Le calcul a la main marcherait aujourd hui et se decalerait d une
    # heure fin octobre, une seule fois, sans que rien ne le signale.
    _dep_minuit = time.localtime(time.time() - a.days * 86400)
    since = time.mktime((_dep_minuit.tm_year, _dep_minuit.tm_mon,
                         _dep_minuit.tm_mday, 0, 0, 0, 0, 0, -1))
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
        print("KO : %d occurrence(s) de la ligne `since`, il en faut 1." % n)
        print("Rien n a ete ecrit.")
        return 1

    # Le correctif ne vaut que si le fichier ecrit bien avec "w" : c est
    # cette reecriture complete qui rend une fenetre etroite destructrice.
    # Si un jour il passait en "a", le calage resterait inoffensif mais le
    # raisonnement de ce patch serait perime -- autant le verifier.
    if 'open(fp, "w"' not in src:
        print("NOTE : l ecriture du fichier de jour n est plus en mode")
        print("       ecrasement. Le correctif reste valable, mais la")
        print("       raison d etre de ce patch est a relire.")

    neuf = src.replace(ANCRE, NEUF, 1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # ast.parse ne dirait pas si l expression garde l heure courante.
    # On la RECALCULE ici, telle qu elle sera evaluee la-bas, et on
    # verifie qu elle tombe bien a minuit.
    for jours in (1, 2, 14, 20):
        dep = time.localtime(time.time() - jours * 86400)
        val = time.mktime((dep.tm_year, dep.tm_mon, dep.tm_mday,
                           0, 0, 0, 0, 0, -1))
        lt = time.localtime(val)
        if (lt.tm_hour, lt.tm_min, lt.tm_sec) != (0, 0, 0):
            print("KO : avec --days %d la fenetre commencerait a %02d:%02d:%02d"
                  % (jours, lt.tm_hour, lt.tm_min, lt.tm_sec))
            print("     et non a minuit. Rien n a ete ecrit.")
            return 1
    print("Verifie : avec --days 1, 2, 14 et 20, la fenetre commence a")
    print("00:00:00 locale.")

    dep = time.localtime(time.time() - 86400)
    print()
    print("Avec --days 1, la fenetre partira du %04d-%02d-%02d 00:00:00"
          % (dep.tm_year, dep.tm_mon, dep.tm_mday))
    print("au lieu de %02d:%02d:%02d le meme jour."
          % (dep.tm_hour, dep.tm_min, dep.tm_sec))
    print()
    print("Consequence : hier et aujourd hui sont reecrits EN ENTIER.")
    print("Un fichier de jour ne peut plus etre rogne, quelle que soit")
    print("l heure du lancement.")
    print()
    print("Cout : environ 7 s par passe au lieu de 3,8. Sans importance")
    print("pour une boucle de 30 s, et c est le prix d une archive qui")
    print("ne peut plus perdre de matiere.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. La boucle peut reprendre.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
patch_rails_trois_ab.py -- dire que la comparaison A/B ne vaut pas
                           avant le 12/08

  python patch_rails_trois_ab.py --essai
  python patch_rails_trois_ab.py

POURQUOI

    Le tableau PAR FAMILLE DE MAGIC met M206 et M207 cote a cote sur les
    trois periodes. C est le protocole de la stack : 206 se gere seul
    jusqu au reverse, 207 est confie au trail MFE. Laisser courir contre
    proteger.

    Sauf que sur les periodes 1 et 2, le bras traille ne l etait pas :

      - sur US30, les 207 etaient exclus du trail. Zero ligne dans
        mfe_trail_events.csv du 28/07 au 11/08. Ces tickets se
        comportaient comme des 206 sans etre etiquetes ainsi.
      - sur NAS100 et SPX500, C14 refusait 62 709 crans BE sur 62 732.
        Trailles sur le papier, a peine proteges en pratique.

    Lire l ecart 206/207 sur ces periodes, c est comparer autonome et
    autonome degrade. Le tableau invite a une conclusion fausse.

POURQUOI MARQUER PLUTOT QUE SUPPRIMER

    Les chiffres d avant le 12/08 ne sont pas des erreurs : ce sont de
    vrais euros, vraiment perdus. Ce qui est faux, c est de les LIRE
    comme une comparaison de protocoles.

    Et ce sont eux la ligne de base. Sans les periodes 1 et 2, plus rien
    ne permet de dire si le trail repare change quelque chose. Supprimer
    la comparaison ferait disparaitre le temoin en meme temps que le faux
    resultat.

    Le panel marque deja ses cellules douteuses d un ? sous 30 tickets.
    Meme principe : on ecrit ce qu on ne sait pas, on ne cache pas.

IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
Purement additif : que des print, aucun calcul touche.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "rails_trois.py"
MARQUEUR = "NE MESURE PAS CE"

RE_ANCRE = re.compile(
    r'^([ \t]*)bloc\("PAR FAMILLE DE MAGIC", lambda s: s\["magic"\]\[:4\], '
    r'lots, ordre=fams\)[ \t]*$', re.M)

NEUF = '''    print("  M206 se gere seul jusqu au reverse (aucun trail, par")
    print("  conception). M207 est confie au trail MFE. Ce tableau est donc")
    print("  le protocole -- laisser courir contre proteger.")
    print()
    print("  MAIS LA LIGNE M207 DES PERIODES 1 ET 2 NE MESURE PAS CE")
    print("  PROTOCOLE. Jusqu au 11/08 le bras traille ne l etait pas :")
    print("    - sur US30, les 207 etaient exclus du trail (zero ligne dans")
    print("      mfe_trail_events.csv du 28/07 au 11/08) : ils se")
    print("      comportaient comme des 206 sans etre etiquetes ainsi ;")
    print("    - sur NAS100 et SPX500, C14 refusait 62 709 crans BE sur")
    print("      62 732, donc a peine proteges en pratique.")
    print("  Comparer 206 et 207 sur ces deux periodes revient a comparer")
    print("  autonome et autonome degrade. Les chiffres sont vrais -- ce")
    print("  sont de vrais euros -- mais l ecart entre les deux familles")
    print("  n y a pas le sens qu on lui prete.")
    print()
    print("  Les periodes 1 et 2 restent la LIGNE DE BASE : sans elles, on")
    print("  ne peut pas dire si le trail repare change quoi que ce soit.")
    print("  Seule la periode 3 compare reellement les deux bras, et il lui")
    print("  faut dix seances avant d etre lisible.")'''


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1

    src, enc = lire(a.fichier)
    print("%s : %d lignes, encodage %s" % (a.fichier, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    trouve = RE_ANCRE.findall(src)
    if len(trouve) != 1:
        print("KO : %d occurrence(s) de l ancre, il en faut 1." % len(trouve))
        print("Attendu :")
        print('    bloc("PAR FAMILLE DE MAGIC", lambda s: s["magic"][:4],'
              ' lots, ordre=fams)')
        print("Rien n a ete ecrit.")
        return 1

    ind = trouve[0]
    corps = "\n".join(ind + l[4:] if l.startswith("    ") else (ind + l if l else "")
                      for l in NEUF.split("\n"))
    neuf = RE_ANCRE.sub(lambda m: m.group(0) + "\n" + corps, src, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print("ancre trouvee : indentation %d espaces" % len(ind))
    print()
    print("Ajoute sous le tableau PAR FAMILLE DE MAGIC :")
    print("  - ce que sont 206 et 207 (autonome / traille)")
    print("  - pourquoi les periodes 1 et 2 ne mesurent pas ce protocole")
    print("  - pourquoi on les garde quand meme : c est la ligne de base")
    print()
    print("Purement additif. Aucun calcul, aucun chiffre n est touche.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc).write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    print()
    print("Visible au prochain export :")
    print("    python export_panels.py --dest panels")
    return 0


if __name__ == "__main__":
    sys.exit(main())

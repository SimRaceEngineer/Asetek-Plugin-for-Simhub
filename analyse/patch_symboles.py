# -*- coding: utf-8 -*-
"""
patch_symboles.py -- les vrais noms MT5, et un actif muet qui se voit

  python patch_symboles.py --essai
  python patch_symboles.py

CE QUE LA MESURE A MONTRE

    diag_bougies, sur douze seances :

        US30    1381 bougies M1 par jour
        US500      0
        US100      0

    Les indices s appellent NAS100 et SPX500 dans MT5. La stack, elle,
    les nomme US100 et US500 dans ses tickets. Les deux vocabulaires ne
    se rencontraient nulle part.

CE QUE CA A COUTE, ET C EST LE PLUS GRAVE

    departage.py et signal_avance.py ont tourne sur US30 SEUL. Les
    colonnes SAR/h, les ratios d efficacite, les quartiles du 12/08 au
    soir : un actif sur trois. Et rien ne l a dit.

    serie_du_jour rendait une liste vide, la boucle passait a l actif
    suivant, le tableau sortait avec l air normal. C est la classe de
    bug qu on traque depuis le matin -- du code qui jette de la donnee
    en silence -- et cette fois elle etait dans mes scripts.

CE QUE FAIT CE PATCH, DANS CET ORDRE

    1. une table de correspondance SYMBOLES : US100 -> NAS100,
       US500 -> SPX500, US30 -> US30. Elle est modifiable en tete de
       fichier, et --symbole permet d en forcer une autre sans patcher.

    2. serie_du_jour PARLE quand elle ne rend rien. Une seule ligne par
       actif et par jour, sur stderr, impossible a rater :

           BOUGIES ABSENTES : US100 (NAS100) le 2026-08-12

       Elle est imprimee depuis la fonction elle-meme, donc tous les
       scripts qui l appellent en profitent -- departage, signal_avance,
       et ceux qui viendront -- sans qu il faille les patcher un par un.

    3. un compteur MUETS, lisible apres coup, pour qu un script puisse
       refuser de conclure s il lui manque un actif.

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

CIBLE = "departage.py"
MARQUEUR = "SYMBOLES"

RE_CONST = re.compile(
    r'^AF_DEPART, AF_PAS, AF_MAX = 0\.02, 0\.02, 0\.20$', re.M)

RE_TETE = re.compile(
    r'^def serie_du_jour\(actif, tf, jour\):$', re.M)

RE_APPEL = re.compile(
    r'^    d0 = datetime\.strptime\(jour, "%Y-%m-%d"\)\n'
    r'    r = mt5\.copy_rates_range\(actif, tf, d0, d0 \+ timedelta\(days=1\)\)\n'
    r'    if r is None or len\(r\) < MINI_BARRES:\n'
    r'        return \[\], None$', re.M)

CONST = '''AF_DEPART, AF_PAS, AF_MAX = 0.02, 0.02, 0.20

# La stack nomme ses indices US30 / US500 / US100 dans les tickets ;
# MT5 les appelle US30 / SPX500 / NAS100. Les deux vocabulaires ne se
# rencontraient nulle part, et copy_rates_range rendait zero bougie pour
# deux actifs sur trois -- en silence, pendant douze seances.
SYMBOLES = {"US100": "NAS100", "US500": "SPX500", "US30": "US30"}

# Ce qui n a rien rendu, pour qu un script puisse refuser de conclure.
MUETS = set()'''

APPEL = '''    sym = SYMBOLES.get(actif, actif)
    d0 = datetime.strptime(jour, "%Y-%m-%d")
    r = mt5.copy_rates_range(sym, tf, d0, d0 + timedelta(days=1))
    if r is None or len(r) < MINI_BARRES:
        # On le DIT. Un actif muet qui se contente de disparaitre du
        # tableau donne un resultat d apparence normale calcule sur ce
        # qui restait -- c est exactement ce qui vient d arriver.
        clef = (actif, sym, jour)
        if clef not in MUETS:
            MUETS.add(clef)
            try:
                sys.stderr.write("BOUGIES ABSENTES : %s (%s) le %s\\n"
                                 % (actif, sym, jour))
            except Exception:
                pass
        return [], None'''


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

    for nom, rx in (("la ligne des parametres SAR", RE_CONST),
                    ("l ouverture des bougies", RE_APPEL)):
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1
        print("  %-30s : %s"
              % (nom, rx.search(src).group(0).split("\n")[0].strip()[:56]))

    neuf = RE_CONST.sub(lambda m: CONST, src, count=1)
    neuf = RE_APPEL.sub(lambda m: APPEL, neuf, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Correspondance posee :")
    print("    US100 -> NAS100")
    print("    US500 -> SPX500")
    print("    US30  -> US30")
    print()
    print("Et un actif sans bougie ecrit desormais une ligne sur stderr :")
    print("    BOUGIES ABSENTES : US100 (NAS100) le 2026-08-12")
    print("Elle vient de serie_du_jour, donc signal_avance en profite")
    print("aussi, sans patch supplementaire.")
    print()
    print("A RELANCER APRES, car les resultats d hier portaient sur US30")
    print("seul :")
    print("    python signal_avance.py --depuis 2026-07-28")
    print("    python departage.py --depuis 2026-08-05")

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
    return 0


if __name__ == "__main__":
    sys.exit(main())

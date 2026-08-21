# -*- coding: utf-8 -*-
"""
patch_demarrage_miroir.py -- le miroir demarre avec la stack.

  python patch_demarrage_miroir.py --essai
  python patch_demarrage_miroir.py

POURQUOI ICI ET PAS AILLEURS

  demarrage_quotidien.cmd est appele par la tache planifiee
  \\TradingStack\\DemarrageQuotidien a 20:05. Son etape 1 appelle
  START_TRADING_STACK_V3.bat, qui TUE toutes les fenetres python --
  y compris celles qui ne sont dans aucune de ses listes. C est
  precisement pour ca que l etape 3 relance papier_tf, x60_onset,
  rafraichir_x60, panels_auto et rafraichir_orderflow.

  Le miroir a exactement le meme statut : V3 le tuera, donc il doit
  etre relance au meme endroit. L ajouter ailleurs -- une tache
  separee, un lancement a la main -- le ferait disparaitre a chaque
  redemarrage quotidien sans que rien ne le signale. C est ce qui
  s est passe aujourd hui.

CE QUE CA IMPLIQUE

  Le miroir partira ARME : des ordres reels, tous les jours, sans
  personne devant. Le compte est ThinkMarkets-Demo, et le plancher de
  niveau de marge a 300 % borne l exposition, mais il faut le savoir.
  Pour le rendre muet, remplacer --armer par --tourner dans la ligne
  ajoutee : il journalise alors tout sans rien envoyer.

  Il demarre a 20:05 alors que sa fenetre est 14:00-19:00. Il ecrira
  donc  hors fenetre  jusqu au lendemain 14h. Ce n est pas du bruit
  inutile : c est la preuve qu il est vivant, et le battement d une
  ligne par minute le confirme.

Le script verifie les trois ancres, garde une copie
demarrage_quotidien.cmd.avant-miroir, et n ecrit rien si l une manque.
Le fichier est lu et reecrit en latin-1, octet pour octet : un .cmd ne
doit pas changer d encodage sous pretexte qu on y ajoute une ligne.
"""
import argparse
import io
import os
import shutil
import sys

CIBLE = "demarrage_quotidien.cmd"
MARQUE = "miroir_papers.py"

PAIRES = [
    # 1. le lancement, dans la liste des observateurs
    ("@('-u','rafraichir_orderflow.py')))",
     "@('-u','rafraichir_orderflow.py'), @('-u','miroir_papers.py','--armer')))"),
    # 2. le controle de l etape 4 doit le compter
    ("'papier_tf^|x60_onset^|rafraichir_x60^|panels_auto'",
     "'papier_tf^|x60_onset^|rafraichir_x60^|panels_auto^|miroir_papers'"),
    ("('observateurs : ' + @($o).Count + ' / 4')",
     "('observateurs : ' + @($o).Count + ' / 5')"),
]

# 3. dire pourquoi, dans le fichier lui-meme. La fin de ligne est celle
# du fichier : un .cmd ne doit pas se retrouver avec deux conventions
# melangees sous pretexte qu on y ajoute un commentaire.
ANCRE3 = "REM --- 3. les observateurs, que V3 vient de tuer -----------------------"
NOTE3 = [
    "REM  miroir_papers en fait partie depuis le 21/08 : V3 le tue comme les",
    "REM  autres, et le 21/08 il a fallu le relancer a la main deux fois.",
    "REM  Il part ARME. Mettre --tourner a la place de --armer le rend muet.",
    "REM  Sa fenetre est 14:00-19:00 : de 20:05 a 14h il ecrira  hors",
    "REM  fenetre , ce qui prouve qu il tourne.",
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        print("Repertoire courant : %s" % os.getcwd())
        return 1
    s = io.open(CIBLE, encoding="latin-1", newline="").read()
    if MARQUE in s:
        print("Deja fait -- le miroir est dans le demarrage.")
        return 0

    fin = "\r\n" if "\r\n" in s else "\n"
    paires = list(PAIRES) + [(ANCRE3, ANCRE3 + fin + fin.join(NOTE3))]

    manque = [i for i, (av, _ap) in enumerate(paires, 1) if s.count(av) != 1]
    if manque:
        print("KO : ancre(s) %s introuvable(s) ou ambigue(s)."
              % ", ".join(str(i) for i in manque))
        print("RIEN n a ete ecrit.")
        return 1

    neuf = s
    for av, ap in paires:
        neuf = neuf.replace(av, ap, 1)

    if a.essai:
        print("PRET : %d -> %d octets, %d ancre(s) trouvee(s)."
              % (len(s.encode("latin-1")), len(neuf.encode("latin-1")),
                 len(paires)))
        print("Rien n est ecrit. Relance sans --essai.")
        return 0

    shutil.copy2(CIBLE, CIBLE + ".avant-miroir")
    io.open(CIBLE, "w", encoding="latin-1", newline="").write(neuf)
    print("ECRIT : %d -> %d octets." % (len(s.encode("latin-1")),
                                        len(neuf.encode("latin-1"))))
    print("Copie de secours : %s.avant-miroir" % CIBLE)
    print("")
    print("Le miroir demarrera avec la stack a 20:05, en fenetre cachee.")
    print("Ce soir, V3 le tuera puis l etape 3 le relancera : il n y aura")
    print("plus rien a faire a la main.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

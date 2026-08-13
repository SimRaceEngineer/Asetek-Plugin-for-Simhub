# -*- coding: utf-8 -*-
"""
patch_demarrage_orderflow.py -- la boucle orderflow dans le demarrage

  python patch_demarrage_orderflow.py --essai
  python patch_demarrage_orderflow.py

LE TROU

    demarrage_quotidien.cmd relance quatre observateurs apres le
    passage de START_TRADING_STACK_V3.bat, qui les tue tous a son
    etape 0 :

        papier_tf, x60_onset, rafraichir_x60, panels_auto

    rafraichir_orderflow.py n y est pas : il a ete ecrit apres. La
    tache \\TradingStack\\DemarrageQuotidien part ce soir a 20:05, V3
    tuera la boucle, et rien ne la relancera.

    L export orderflow s arreterait donc cette nuit. Sans message,
    sans erreur, sans fichier vide -- simplement un dossier qui cesse
    de bouger pendant que tout le reste continue. C est le mode de
    panne qui a coute le plus cher aujourd hui, et il aurait recommence
    cette nuit.

CE QUE LE PATCH FAIT

    Un cinquieme element dans la liste des processus a relancer. Rien
    d autre : ni l ordre des etapes, ni l appel a V3, ni les delais,
    ni le journal.

UNE ANCRE, verifiee unique. IDEMPOTENT. Sauvegarde horodatee.
Verification apres ecriture que les CINQ scripts sont bien nommes.
"""
import argparse
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "demarrage_quotidien.cmd"
MARQUEUR = "rafraichir_orderflow.py"

ANCRE = "@('-u','panels_auto.py','--dest','panels')"
NEUF = ("@('-u','panels_auto.py','--dest','panels'),"
        " @('-u','rafraichir_orderflow.py')")

ATTENDUS = ("papier_tf.py", "x60_onset.py", "rafraichir_x60.py",
            "panels_auto.py", "rafraichir_orderflow.py")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable." % a.fichier)
        print("     La tache planifiee pointe dessus : si le fichier")
        print("     n est pas la, elle echouera ce soir a 20:05.")
        return 1

    src = enc = None
    for e in ("cp1252", "utf-8", "utf-8-sig"):
        try:
            src = io.open(a.fichier, encoding=e, newline="").read()
            enc = e
            break
        except (UnicodeDecodeError, ValueError):
            continue
    if src is None:
        print("KO : encodage non reconnu.")
        return 1
    print("%s : %d lignes, encodage %s" % (a.fichier, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    n = src.count(ANCRE)
    if n != 1:
        print("KO : %d occurrence(s) de l ancre, il en faut 1." % n)
        print("Rien n a ete ecrit.")
        return 1

    neuf = src.replace(ANCRE, NEUF, 1)

    manquants = [s for s in ATTENDUS if s not in neuf]
    if manquants:
        print("KO : ces scripts ne sont pas nommes dans le fichier : %s"
              % ", ".join(manquants))
        print("Rien n a ete ecrit.")
        return 1
    print("Les cinq observateurs sont nommes : %s." % ", ".join(ATTENDUS))

    print()
    print("rafraichir_orderflow.py sera relance apres chaque passage de")
    print("V3, comme les quatre autres. Sans ca, l export orderflow")
    print("s arretait ce soir a 20:05 sans qu aucun message ne le dise.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc, newline="").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Prend effet au prochain passage de la tache, 20:05.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

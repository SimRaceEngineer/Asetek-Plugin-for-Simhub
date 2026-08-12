# -*- coding: utf-8 -*-
"""
patch_v3_wrappers.py -- V3 ne lance plus cinq fenetres, il appelle le superviseur

  python patch_v3_wrappers.py --essai
  python patch_v3_wrappers.py

CE QU IL CHANGE, ET C EST TOUT

    Dans START_TRADING_STACK_V3.bat, les cinq lignes qui ouvrent une
    fenetre chacune :

        start "Price Action Panel" /MIN cmd /c "%PROJ%run_panel_loop.bat"
        start "Latent Log"         /MIN cmd /c "%PROJ%run_latent_loop.bat"
        start "Orderflow Panel"    /MIN cmd /c "%PROJ%run_orderflow_loop.bat"
        start "Jauge H1"           /MIN cmd /c "%PROJ%run_jauge_loop.bat"
        start "Trade Monitor"      /MIN cmd /c "%PROJ%run_monitor_loop.bat"

    deviennent UNE ligne, cachee, qui lance Superviseur.ps1. Celui-ci
    demarre les memes cinq services -- avec les memes roles, les memes
    arguments, le meme PA_ROLE=panel -- en fenetres invisibles, et les
    surveille toutes les 20 secondes.

CE QU IL NE TOUCHE PAS

    Rien d autre. Ni le kill du debut, ni les terminaux MT5, ni le
    nettoyage des .dat, ni trading_engine, ni le copier FTMO, ni
    verify_stack. Ces lignes portent trois mois d incidents et chacune
    documente le sien.

POURQUOI CA REGLE AUSSI LES 23 ORDERFLOW

    La cause etait que V3 tue les fenetres « Trade Monitor » et
    « Administrateur*Price Action Panel » mais PAS « Orderflow Panel »,
    « Latent Log » ni « Jauge H1 » : ces wrappers survivaient, leur
    boucle relancait leur python, et V3 en ajoutait un a chaque passage.

    Sans wrapper, plus de fenetre a oublier. Et le superviseur ramene
    activement chaque service a UNE instance.

L ORDRE DES OPERATIONS COMPTE

    1. copier Superviseur.ps1 dans le dossier de la stack
    2. appliquer ce patch
    3. .\Superviseur.ps1 -Arreter    (ferme les wrappers d aujourd hui)
    4. .\Superviseur.ps1 -Go         (ou laisser le prochain V3 le faire)

    A faire A FROID, marches fermes. Pas a 22h un mardi avec des
    positions ouvertes.

ROLLBACK

    La sauvegarde horodatee est ecrite a cote. Pour revenir :
    copier START_TRADING_STACK_V3.bat.bak-<date> par-dessus.

IDEMPOTENT. Sauvegarde horodatee. Affiche le diff avant d ecrire.
"""
import argparse
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "START_TRADING_STACK_V3.bat"
MARQUEUR = "Superviseur.ps1"

# Les cinq lanceurs de wrapper, chacun sur sa ligne. On les reconnait par
# le nom du .bat appele -- le titre de fenetre, lui, a des variantes.
RE_WRAP = re.compile(
    r'^[ \t]*start "[^"]*" /MIN cmd /c "%PROJ%run_(panel|latent|orderflow'
    r'|jauge|monitor)_loop\.bat"[ \t]*\r?$', re.M | re.I)

NEUF = (
    'REM === 2026-08-12 : les cinq wrappers sont remplaces par UN superviseur.\n'
    'REM     Avant : cinq fenetres cmd, dont trois que le kill du debut de ce\n'
    'REM     fichier oubliait (Orderflow Panel, Latent Log, Jauge H1) -- elles\n'
    'REM     survivaient, leur boucle relancait leur python, et chaque passage\n'
    'REM     de V3 en ajoutait un. orderflow_panel.py etait monte a 23.\n'
    'REM     Maintenant : Superviseur.ps1 lance les MEMES services (memes\n'
    'REM     arguments, PA_ROLE=panel pour le panneau) en fenetres CACHEES,\n'
    'REM     les surveille toutes les 20 s et ramene chacun a UNE instance.\n'
    'REM     Journal : logs\\superviseur.log -- rollback : voir le .bak.\n'
    'start "" /MIN powershell -ExecutionPolicy Bypass -WindowStyle Hidden '
    '-File "%PROJ%Superviseur.ps1" -Go\n')


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    if not os.path.isfile("Superviseur.ps1"):
        print("KO : Superviseur.ps1 n est pas dans ce dossier.")
        print("Copie-le d abord : sans lui, le patch couperait les cinq")
        print("services sans rien mettre a la place.")
        return 1

    for enc in ("cp1252", "utf-8", "utf-8-sig"):
        try:
            src = io.open(a.fichier, encoding=enc).read()
            break
        except (UnicodeDecodeError, ValueError):
            src = None
    if src is None:
        print("KO : encodage non reconnu pour %s" % a.fichier)
        return 1
    print("%s : %d lignes, encodage %s" % (a.fichier, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    trouve = RE_WRAP.findall(src)
    if len(trouve) < 4:
        print("KO : %d ligne(s) de wrapper trouvee(s), il en faut au moins 4."
              % len(trouve))
        print("Le fichier n a pas la forme attendue. Rien n a ete ecrit.")
        return 1

    print()
    print("Lignes remplacees :")
    for m in RE_WRAP.finditer(src):
        print("  - %s" % m.group(0).strip())
    print()
    print("Par cette seule ligne, cachee :")
    print("  + start \"\" /MIN powershell ... -File \"%PROJ%Superviseur.ps1\" -Go")

    # La premiere occurrence devient le bloc neuf, les autres disparaissent.
    etat = {"n": 0}

    def rempl(m):
        etat["n"] += 1
        return NEUF.rstrip("\n") if etat["n"] == 1 else ""

    neuf = RE_WRAP.sub(rempl, src)
    neuf = re.sub(r"\r?\n\r?\n\r?\n+", "\n\n", neuf)

    reste = len(RE_WRAP.findall(neuf))
    if reste:
        print()
        print("KO : %d ligne(s) de wrapper subsistent apres substitution."
              % reste)
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("%d lignes remplacees par 1." % len(trouve))
    print("Les services lances restent EXACTEMENT les memes ; seul change")
    print("qui les lance et le fait qu ils n aient plus de fenetre.")
    print()
    print("A FAIRE A FROID, marches fermes. Ordre :")
    print("  1. .\\Superviseur.ps1 -Arreter")
    print("  2. .\\Superviseur.ps1 -Etat     (verifier que tout est arrete)")
    print("  3. .\\Superviseur.ps1 -Go")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc).write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Rollback : copier le .bak par-dessus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

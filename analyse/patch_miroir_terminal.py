#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_miroir_terminal.py -- le miroir choisit enfin son terminal

LE DEFAUT
    miroir_papers.py, ligne ~1099, appelle mt5.initialize() SANS chemin.
    MT5 lui donne alors le terminal par defaut de la machine. Depuis le
    redemarrage du 25/08 a 20:31, c est le terminal DEDIE -- celui du
    compte miroir. Le miroir y cherche les positions parentes du compte
    PRINCIPAL, ne les trouve evidemment jamais, et la ligne 943 conclut
    "position deja fermee, rien a miroiter". Une position reellement
    fermee et une position cherchee sur le mauvais compte rendent la
    meme liste vide : le journal ne peut pas les distinguer.

    Resultat : zero miroir depuis 20:31 hier. Les quatre dernieres
    executions du compte miroir datent du 25/08 a 19:40.

    pont_miroirs.py, lui, nomme ses deux terminaux (lignes 76-77) et
    refuse de demarrer sur le mauvais (179-180). Le miroir ne le fait
    pas. On lui donne la meme rigueur.

CE QUE FAIT CE PATCH
    Une seule ligne change : mt5.initialize() devient
    mt5.initialize(path=_TERM_MOTEUR). L indentation et la fin de ligne
    d origine sont conservees, le fichier est lu et reecrit en latin-1
    pour un aller-retour exact a l octet pres.

GARDE-FOU
    Si le chemin du terminal moteur n existe pas sur le disque, on
    n ecrit RIEN. Un initialize(path=...) sur un chemin faux peut tenter
    de LANCER un terminal, et on ne lance pas de terminal.

IDEMPOTENT : relance sans effet si la marque est deja la.
"""
import io
import os
import shutil
import sys
import time

CIBLE = "miroir_papers.py"
MOTEUR = (r"C:\Program Files\TF Global Markets MetaTrader 5 "
          r"Termina-LOCALSTACK1\terminal64.exe")
VIEUX = "mt5.initialize()"
MARQUE = "_TERM_MOTEUR"


def main():
    if not os.path.exists(CIBLE):
        print("ABANDON : %s introuvable dans %s" % (CIBLE, os.getcwd()))
        return 2

    if not os.path.exists(MOTEUR):
        print("ABANDON : le terminal moteur est introuvable")
        print("  attendu : %s" % MOTEUR)
        print("  on n ecrit rien : un chemin faux ferait tenter un lancement.")
        print("  terminaux visibles :")
        for base in (r"C:\Program Files", r"C:\Program Files (x86)"):
            if not os.path.isdir(base):
                continue
            for n in os.listdir(base):
                c = os.path.join(base, n, "terminal64.exe")
                if os.path.exists(c):
                    print("    %s" % c)
        return 2
    print("terminal moteur present : %s" % MOTEUR)

    with io.open(CIBLE, encoding="latin-1", newline="") as f:
        texte = f.read()
    if MARQUE in texte:
        print("DEJA PATCHE : la marque %s est presente. Rien a faire." % MARQUE)
        return 0

    lignes = texte.split("\n")
    vises = [i for i, l in enumerate(lignes) if VIEUX in l and "path=" not in l]
    if len(vises) != 1:
        print("ABANDON : %d ligne(s) '%s' au lieu d une seule."
              % (len(vises), VIEUX))
        for i in vises:
            print("  ligne %d : %s" % (i + 1, lignes[i].strip()))
        return 2

    i = vises[0]
    ligne = lignes[i]
    fin = "\r" if ligne.endswith("\r") else ""
    corps = ligne[:-1] if fin else ligne
    creux = corps[:len(corps) - len(corps.lstrip())]
    print("")
    print("ligne %d, avant :" % (i + 1))
    print("    %s" % corps.strip())

    bloc = [
        creux + "# 26/08 : initialize() sans chemin prenait le terminal PAR" + fin,
        creux + "# DEFAUT, qui est le terminal DEDIE depuis le redemarrage du" + fin,
        creux + "# 25/08. Le miroir y cherchait les positions parentes du" + fin,
        creux + "# compte principal, ne les trouvait jamais, et concluait" + fin,
        creux + "# \"position deja fermee\" pour chacune. Zero miroir de toute" + fin,
        creux + "# la journee. Le pont nomme ses terminaux ; le miroir aussi." + fin,
        creux + "_TERM_MOTEUR = r\"" + MOTEUR + "\"" + fin,
        corps.replace(VIEUX, "mt5.initialize(path=_TERM_MOTEUR)") + fin,
    ]
    lignes[i:i + 1] = bloc
    neuf = "\n".join(lignes)

    sauve = "%s.avant_terminal_%s" % (CIBLE, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(CIBLE, sauve)
    with io.open(CIBLE, "w", encoding="latin-1", newline="") as f:
        f.write(neuf)

    with io.open(CIBLE, encoding="latin-1", newline="") as f:
        relu = f.read()
    ok = (MARQUE in relu and "mt5.initialize(path=_TERM_MOTEUR)" in relu)
    print("apres :")
    print("    _TERM_MOTEUR = ...")
    print("    %s" % bloc[-1].strip())
    print("")
    print("sauvegarde : %s" % sauve)
    print("VERIFICATION : %s" % ("ok" if ok else "ECHEC -- restaurer la sauvegarde"))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())

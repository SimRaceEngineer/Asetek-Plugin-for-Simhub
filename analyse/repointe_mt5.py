# -*- coding: utf-8 -*-
"""
repointe_mt5.py -- fait pointer la stack vers la BONNE installation MetaTrader.

Sur msitrident2, deux installations coexistent :

  ...\\TF Global Markets MetaTrader 5 Terminal\\            -> compte 176309
  ...\\TF Global Markets MetaTrader 5 Termina-LOCALSTACKl\\ -> compte 178780

trading_engine.py cible la premiere, en dur. Il s est donc connecte a
176309, l a vu, et a refuse de tourner :

    !!! WRONG ACCOUNT #176309 -- expected Think #178780 !!!

Ce script remplace le premier chemin par le second. Rien d autre.

POURQUOI PAS RENOMMER LE DOSSIER

    MetaTrader range ses donnees dans %APPDATA%\\MetaQuotes\\Terminal\\<empreinte>,
    ou l empreinte derive du chemin d installation. Renommer le dossier
    change l empreinte : le terminal repart sur un profil vierge et perd
    le login enregistre de 178780 -- precisement ce qu on veut garder.

PRECISION DU MOTIF

    Le motif inclut la barre oblique finale. Sans elle, "MetaTrader 5
    Terminal" est aussi le prefixe de "Terminal02" et "Terminal03", et
    le remplacement les casserait tous les deux.

PAR DEFAUT IL NE MODIFIE RIEN. Il montre chaque ligne, avant et apres.
Il faut --appliquer, et il garde alors une copie .bak_mt5.

FILET DE SECURITE

    Si le nouveau chemin est faux, le moteur refusera de demarrer avec
    le meme message qu aujourd hui. On ne peut pas se tromper en silence.

Usage :
    python "G:\\Mon Drive\\ScalpEA\\repointe_mt5.py" C:\\SVPS\\Scalp-EA-main
    python "G:\\Mon Drive\\ScalpEA\\repointe_mt5.py" C:\\SVPS\\Scalp-EA-main --appliquer
"""

import os
import sys

ANCIEN = r"TF Global Markets MetaTrader 5 Terminal" + "\\"
NOUVEAU = r"TF Global Markets MetaTrader 5 Termina-LOCALSTACKl" + "\\"

DOSSIER_CIBLE = (r"C:\Program Files" "\\" +
                 r"TF Global Markets MetaTrader 5 Termina-LOCALSTACKl")

EXT = (".py", ".bat", ".cmd")
SUFFIXE = ".bak_mt5"
IGNORE_DIRS = ("claude_backup", "__pycache__", ".git", "_legacy")


def montre(b):
    return b.decode("utf-8", "replace").rstrip("\r\n")


def main():
    args = list(sys.argv[1:])
    appliquer = "--appliquer" in args
    args = [a for a in args if not a.startswith("--")]
    racine = os.path.abspath(args[0]) if args else os.getcwd()

    if not os.path.isdir(racine):
        print("Ce chemin n est pas un dossier : %s" % racine)
        return 1

    print("=" * 72)
    print("racine  : %s" % racine)
    print("ancien  : ...%s" % ANCIEN)
    print("nouveau : ...%s" % NOUVEAU)
    print("=" * 72)
    print("")

    # On verifie que la cible existe VRAIMENT avant de rediriger quoi que
    # ce soit vers elle. Rediriger vers un dossier absent transformerait
    # une erreur bruyante (mauvais compte) en panne muette.
    if os.path.isdir(DOSSIER_CIBLE):
        exe = os.path.join(DOSSIER_CIBLE, "terminal64.exe")
        if os.path.isfile(exe):
            print("Cible verifiee : terminal64.exe present.")
        else:
            print("ATTENTION : le dossier existe mais terminal64.exe est absent.")
            print("   %s" % exe)
            print("Rien ne sera ecrit.")
            return 1
    else:
        print("REFUS : le dossier cible n existe pas.")
        print("   %s" % DOSSIER_CIBLE)
        print("Verifiez le nom exact avec :  dir \"C:\\Program Files\\TF*\"")
        return 1
    print("")

    anc = ANCIEN.encode("utf-8")
    nou = NOUVEAU.encode("utf-8")

    fichiers = []
    for base, dirs, fics in os.walk(racine):
        dirs[:] = [d for d in dirs if d.lower() not in IGNORE_DIRS]
        for f in fics:
            if f.endswith(EXT) and not f.endswith(SUFFIXE):
                fichiers.append(os.path.join(base, f))

    a_changer = []
    for chemin in sorted(fichiers):
        try:
            with open(chemin, "rb") as fh:
                brut = fh.read()
        except OSError:
            continue
        if anc not in brut:
            continue
        lignes = brut.splitlines(True)
        modifs = []
        for i, l in enumerate(lignes, 1):
            if anc in l:
                modifs.append((i, l, l.replace(anc, nou)))
        if modifs:
            a_changer.append((chemin, lignes, modifs))

    total = sum(len(m) for _c, _l, m in a_changer)
    print("-" * 72)
    print("A REPOINTER : %d fichier(s), %d ligne(s)" % (len(a_changer), total))
    print("-" * 72)
    if not a_changer:
        print("Aucune occurrence. Soit c est deja fait, soit mauvaise racine.")
        return 0
    for chemin, _lignes, modifs in a_changer:
        print("")
        print("%s" % os.path.relpath(chemin, racine))
        for no, avant, apres in modifs:
            print("  %5d  -  %s" % (no, montre(avant)))
            print("         +  %s" % montre(apres))
    print("")

    if not appliquer:
        print("=" * 72)
        print("RIEN N A ETE ECRIT. C etait la simulation.")
        print("Relancez avec --appliquer.")
        print("=" * 72)
        return 0

    print("=" * 72)
    print("ECRITURE")
    print("=" * 72)
    faits = 0
    echecs = []
    for chemin, lignes, modifs in a_changer:
        neuves = list(lignes)
        for no, _avant, apres in modifs:
            neuves[no - 1] = apres
        bak = chemin + SUFFIXE
        try:
            if not os.path.exists(bak):
                with open(chemin, "rb") as fh:
                    orig = fh.read()
                with open(bak, "wb") as fh:
                    fh.write(orig)
            with open(chemin, "wb") as fh:
                fh.write(b"".join(neuves))
            faits += 1
            print("  %s" % os.path.relpath(chemin, racine))
        except OSError as e:
            echecs.append((os.path.relpath(chemin, racine), str(e)))

    print("")
    if echecs:
        print("%d ECHEC(S) :" % len(echecs))
        for n, e in echecs:
            print("   %s : %s" % (n, e))
    else:
        print("%d fichier(s) repointe(s), aucun echec." % faits)
    print("")
    print("Retour arriere : renommer chaque %s sur le fichier d origine."
          % SUFFIXE)
    print("=" * 72)
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())

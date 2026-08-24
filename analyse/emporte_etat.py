# -*- coding: utf-8 -*-
"""
emporte_etat.py -- copie docs\\ vers le Drive SANS les trois gros dossiers.

Pourquoi pas une liste de fichiers choisis : la liste des fichiers que la
stack relit au demarrage a ete etablie par grep sur les modules, et elle
est incomplete par construction (closer_last.json, account_state\\,
leg_state\\, checkpoints\\ ... sont absents du grep et pesent zero).
Emporter TOUT sauf ce qui est enorme coute 875 Mo et supprime le risque
de decouvrir un manquant au moment ou la stack refuse de demarrer.

Les trois exclus (buddha, lifecycle, gate_blocks) font a eux seuls 90 %
de docs et ne sont que de l accumulation : rien ne les relit au
demarrage. Ils restent sur le disque du VPS, qui persiste meme VPS
eteint.

PAR DEFAUT IL NE COPIE RIEN. Il compte, il mesure, il verifie la place,
et il s arrete. Il faut --copier pour qu il ecrive.

Il n efface jamais rien, ni a la source ni a la destination.

Usage :
    python "G:\\My Drive\\ScalpEA\\emporte_etat.py"
    python "G:\\My Drive\\ScalpEA\\emporte_etat.py" --copier

Options :
    --source CHEMIN   le dossier docs (sinon il le cherche)
    --dest CHEMIN     la destination (defaut G:\\My Drive\\etat_stack_2408)
    --avec-logs       emporte aussi logs\\ (2913 Mo -- verifiez la place)
"""

import os
import shutil
import sys

MO = 1024.0 * 1024.0

# Les trois dossiers d accumulation. Mesures le 24/08 : 5944,7 + 1053,9
# + 766,2 Mo, soit 90 % de docs.
EXCLUS = ("buddha", "lifecycle", "gate_blocks")

DEST_DEFAUT = os.path.join("G:\\", "My Drive", "etat_stack_2408")


def trouve_docs(donne):
    if donne:
        return os.path.abspath(donne)
    cwd = os.getcwd()
    if os.path.basename(cwd).lower() == "docs":
        return cwd
    essais = [
        os.path.join(cwd, "docs"),
        os.path.join(os.path.expanduser("~"), "Downloads",
                     "Scalp-EA-main", "Scalp-EA-main", "docs"),
    ]
    for e in essais:
        if os.path.isdir(e):
            return e
    print("Dossier docs introuvable. Essaye :")
    print("   %s  (repertoire courant)" % cwd)
    for e in essais:
        print("   %s" % e)
    print("")
    print("Relancez avec --source CHEMIN.")
    return None


def recense(racine, exclus):
    """Liste (chemin_relatif, octets) sous racine, sans les dossiers exclus.

    Les fichiers dont la taille est illisible sont comptes a part et non
    silencieusement sautes : un total faux sans le dire serait pire que
    pas de total.
    """
    items = []
    rates = []
    exclus_bas = set(x.lower() for x in exclus)
    for base, dirs, fics in os.walk(racine):
        if os.path.normpath(base) == os.path.normpath(racine):
            dirs[:] = [d for d in dirs if d.lower() not in exclus_bas]
        for f in fics:
            plein = os.path.join(base, f)
            rel = os.path.relpath(plein, racine)
            try:
                items.append((rel, os.path.getsize(plein)))
            except OSError:
                rates.append(rel)
    return items, rates


def deja_bon(src, dst):
    """Vrai si dst existe deja avec la meme taille et une date >= src.

    Sert a rendre le script relancable : une copie interrompue reprend
    sans tout refaire. La date n est comparee qu a 2 secondes pres, la
    resolution de FAT et de certains systemes de fichiers reseau.
    """
    try:
        a = os.stat(src)
        b = os.stat(dst)
    except OSError:
        return False
    if a.st_size != b.st_size:
        return False
    return b.st_mtime >= a.st_mtime - 2


def copie(racine, dest, items):
    faits = 0
    sautes = 0
    echecs = []
    octets = 0
    for i, (rel, taille) in enumerate(items, 1):
        src = os.path.join(racine, rel)
        dst = os.path.join(dest, rel)
        if deja_bon(src, dst):
            sautes += 1
            continue
        try:
            d = os.path.dirname(dst)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            shutil.copy2(src, dst)
            faits += 1
            octets += taille
        except (OSError, IOError) as e:
            echecs.append((rel, str(e)))
        if i % 100 == 0 or i == len(items):
            print("   %d / %d   (%d copies, %d deja bons, %d echecs)"
                  % (i, len(items), faits, sautes, len(echecs)))
    return faits, sautes, echecs, octets


def bloc(titre, racine, dest, exclus):
    print("=" * 64)
    print(titre)
    print("=" * 64)
    print("source      : %s" % racine)
    print("destination : %s" % dest)
    if exclus:
        print("exclus      : %s" % ", ".join(exclus))
    print("")
    items, rates = recense(racine, exclus)
    total = sum(t for _r, t in items)
    print("%d fichiers, %.1f Mo" % (len(items), total / MO))
    if rates:
        print("ATTENTION : %d fichiers illisibles, non comptes :" % len(rates))
        for r in rates[:10]:
            print("   %s" % r)
        if len(rates) > 10:
            print("   ... et %d autres" % (len(rates) - 10))
    return items, total


def main():
    args = sys.argv[1:]
    copier = "--copier" in args
    avec_logs = "--avec-logs" in args

    def opt(nom):
        if nom in args:
            i = args.index(nom)
            if i + 1 < len(args):
                return args[i + 1]
            print("L option %s attend un chemin." % nom)
            sys.exit(1)
        return None

    docs = trouve_docs(opt("--source"))
    if docs is None:
        return 1
    if not os.path.isdir(docs):
        print("Ce chemin n est pas un dossier : %s" % docs)
        return 1

    dest_racine = opt("--dest") or DEST_DEFAUT

    lots = [("DOCS", docs, os.path.join(dest_racine, "docs"), EXCLUS)]
    if avec_logs:
        logs = os.path.join(os.path.dirname(docs), "logs")
        if os.path.isdir(logs):
            lots.append(("LOGS", logs, os.path.join(dest_racine, "logs"), ()))
        else:
            print("--avec-logs demande mais %s n existe pas." % logs)
            print("")

    plan = []
    total_general = 0
    for titre, src, dst, exc in lots:
        items, total = bloc(titre, src, dst, exc)
        plan.append((titre, src, dst, items))
        total_general += total
        print("")

    # La place. Sans cette verification on remplit le Drive a ras bord
    # et la synchro casse au milieu, ce qui est arrive une fois deja.
    # Sur Windows on interroge la racine du lecteur (G:\). Ailleurs,
    # ou si la destination n a pas de lettre, on interroge le premier
    # dossier existant en remontant : disk_usage refuse un chemin absent.
    abs_dest = os.path.abspath(dest_racine)
    lecteur = os.path.splitdrive(abs_dest)[0]
    if lecteur:
        lecteur += os.sep
    else:
        lecteur = abs_dest
        while lecteur and not os.path.isdir(lecteur):
            parent = os.path.dirname(lecteur)
            if parent == lecteur:
                break
            lecteur = parent
    try:
        libre = shutil.disk_usage(lecteur).free
    except OSError:
        libre = None

    print("=" * 64)
    print("PLACE")
    print("=" * 64)
    print("a ecrire : %.1f Mo" % (total_general / MO))
    if libre is None:
        print("libre    : illisible sur %s" % lecteur)
        print("Je ne peux pas garantir que ca tient. Verifiez a la main.")
    else:
        print("libre    : %.1f Mo sur %s" % (libre / MO, lecteur))
        marge = libre - total_general
        if marge < 0:
            print("")
            print("CA NE TIENT PAS. Il manque %.1f Mo." % (-marge / MO))
            print("Liberez de la place avant, ou utilisez --dest.")
            return 1
        if marge < 500 * MO:
            print("")
            print("Marge faible : %.1f Mo une fois la copie faite."
                  % (marge / MO))
    print("")

    if not copier:
        print("=" * 64)
        print("RIEN N A ETE COPIE. C etait la simulation.")
        print("Relancez avec --copier pour ecrire pour de vrai.")
        print("=" * 64)
        return 0

    print("=" * 64)
    print("COPIE REELLE")
    print("=" * 64)
    total_echecs = []
    for titre, src, dst, items in plan:
        print("")
        print("-- %s --" % titre)
        if not os.path.isdir(dst):
            os.makedirs(dst)
        faits, sautes, echecs, octets = copie(src, dst, items)
        print("   %d copies (%.1f Mo), %d deja bons, %d echecs"
              % (faits, octets / MO, sautes, len(echecs)))
        total_echecs.extend(echecs)

    print("")
    print("=" * 64)
    if total_echecs:
        print("%d ECHECS. Ils sont listes ci-dessous." % len(total_echecs))
        for rel, msg in total_echecs[:30]:
            print("   %s" % rel)
            print("      %s" % msg)
        if len(total_echecs) > 30:
            print("   ... et %d autres" % (len(total_echecs) - 30))
        print("")
        print("Relancez la meme commande : les fichiers deja copies")
        print("seront sautes, seuls les rates seront retentes.")
    else:
        print("Aucun echec.")
    print("")
    print("Rien n a ete efface, ni a la source ni a la destination.")
    print("=" * 64)
    return 1 if total_echecs else 0


if __name__ == "__main__":
    sys.exit(main())

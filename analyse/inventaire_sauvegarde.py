# -*- coding: utf-8 -*-
r"""
inventaire_sauvegarde.py -- ce qu il y a vraiment a sauvegarder

  python inventaire_sauvegarde.py
  python inventaire_sauvegarde.py --racine "D:\autre"

LECTEUR SEUL. N ECRIT RIEN, NE COPIE RIEN, NE SUPPRIME RIEN.

POURQUOI UN SCRIPT ET PAS UNE LIGNE POWERSHELL

    Deux tentatives en ligne de commande ont ete corrompues en route :
    les tirets bas de $_.Name manges par l italique, puis [int](...)
    avale comme un lien. Le canal fichier, lui, n a jamais echoue.

POURQUOI L INVENTAIRE PASSE AVANT LE TRANSFERT

    80 Go annonces. Sur un stack de trading, la masse est presque
    toujours dans trois choses -- historique, journaux, donnees tick
    brutes -- dont une partie se regenere. Sauvegarder 80 Go quand 20
    suffisent, ce n est pas de la prudence : c est un transfert qui
    echoue en route et qu on ne refait pas.

    Le script marque donc ce qui est REGENERABLE : __pycache__, .git,
    node_modules, les caches. Il ne supprime rien et ne decide rien --
    il montre, tu tranches.

CE QU IL DONNE

    Par racine : chaque dossier de premier niveau avec sa taille, son
    nombre de fichiers et sa date de derniere modification. Un dossier
    volumineux et fige depuis six mois ne se traite pas comme un
    dossier volumineux qui bouge tous les jours -- le premier se
    transfere une fois, le second veut de l incrementiel.

    Puis les plus gros fichiers isoles, et une estimation de duree de
    transfert a plusieurs debits, pour que le choix entre scp, une
    archive en volumes et robocopy repose sur un ordre de grandeur.
"""
import argparse
import os
import sys
import time

RACINES = [
    r"C:\Users\Administrator\Downloads\Scalp-EA-main\Scalp-EA-main",
    r"C:\Users\Administrator\Documents\Abaure",
]

# Ce qui se reconstruit tout seul, ou se re-clone. Marque, jamais touche.
REGENERABLE = ("__pycache__", ".git", "node_modules", ".venv", "venv",
               "site-packages", ".mypy_cache", ".pytest_cache", "dist",
               "build", ".ipynb_checkpoints")

DEBITS = ((2, "2 Mo/s   liaison modeste"),
          (10, "10 Mo/s  correcte"),
          (40, "40 Mo/s  tres bonne"))


def humain(o):
    for unite, seuil in (("To", 1024 ** 4), ("Go", 1024 ** 3),
                         ("Mo", 1024 ** 2), ("ko", 1024)):
        if o >= seuil:
            return "%.1f %s" % (o / float(seuil), unite)
    return "%d o" % o


def duree(octets, mo_par_s):
    s = octets / float(mo_par_s * 1024 * 1024)
    if s < 90:
        return "%d s" % s
    if s < 5400:
        return "%d min" % (s / 60)
    return "%.1f h" % (s / 3600.0)


def pese(chemin, gros, plafond=12):
    """(octets, fichiers, mtime le plus recent). Ne leve jamais."""
    total, n, recent = 0, 0, 0
    for dossier, sous, fichiers in os.walk(chemin, onerror=lambda e: None):
        for f in fichiers:
            c = os.path.join(dossier, f)
            try:
                st = os.stat(c)
            except OSError:
                continue
            total += st.st_size
            n += 1
            if st.st_mtime > recent:
                recent = st.st_mtime
            if st.st_size > 50 * 1024 * 1024:
                gros.append((st.st_size, c))
                if len(gros) > 400:
                    gros.sort(reverse=True)
                    del gros[plafond * 4:]
    return total, n, recent


def quand(t):
    return time.strftime("%Y-%m-%d", time.localtime(t)) if t else "-"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", action="append", default=None)
    p.add_argument("--gros", type=int, default=12)
    a = p.parse_args()

    L = []
    add = L.append
    add("=" * 92)
    add("INVENTAIRE AVANT SAUVEGARDE")
    add("=" * 92)
    add("")
    add("  Lecteur seul. Rien n est copie, rien n est efface.")
    add("")

    gros = []
    grand_total = 0
    for racine in (a.racine or RACINES):
        if not os.path.isdir(racine):
            add("  INTROUVABLE : %s" % racine)
            add("")
            continue
        add("=" * 92)
        add(racine)
        add("=" * 92)
        add("  %-34s %10s %9s %12s  %s"
            % ("dossier", "taille", "fichiers", "modifie", ""))
        add("  " + "-" * 88)
        lignes, total_r, n_r = [], 0, 0
        try:
            entrees = sorted(os.listdir(racine))
        except OSError as e:
            add("  illisible : %s" % e)
            add("")
            continue
        lache_o, lache_n = 0, 0
        for nom in entrees:
            c = os.path.join(racine, nom)
            if os.path.isdir(c):
                o, n, t = pese(c, gros, a.gros)
                lignes.append((o, nom, n, t))
                total_r += o
                n_r += n
            else:
                try:
                    st = os.stat(c)
                    lache_o += st.st_size
                    lache_n += 1
                except OSError:
                    pass
        for o, nom, n, t in sorted(lignes, reverse=True):
            marque = ""
            if nom in REGENERABLE:
                marque = "  <- regenerable"
            add("  %-34s %10s %9d %12s%s"
                % (nom[:34], humain(o), n, quand(t), marque))
        if lache_n:
            add("  %-34s %10s %9d %12s"
                % ("(fichiers a la racine)", humain(lache_o), lache_n, "-"))
            total_r += lache_o
            n_r += lache_n
        add("  " + "-" * 88)
        add("  %-34s %10s %9d" % ("TOTAL", humain(total_r), n_r))
        recup = sum(o for o, nom, _n, _t in lignes if nom in REGENERABLE)
        if recup:
            add("  %-34s %10s   (a exclure, se reconstruit)"
                % ("dont regenerable", humain(recup)))
        add("")
        grand_total += total_r

    add("=" * 92)
    add("LES PLUS GROS FICHIERS")
    add("=" * 92)
    gros.sort(reverse=True)
    if not gros:
        add("  Aucun fichier au-dessus de 50 Mo.")
    for o, c in gros[:a.gros]:
        add("  %10s  %s" % (humain(o), c[-76:]))
    add("")

    add("=" * 92)
    add("COMBIEN DE TEMPS POUR TOUT TRANSFERER")
    add("=" * 92)
    add("  total : %s" % humain(grand_total))
    add("")
    for mo, quoi in DEBITS:
        add("  %-28s %s" % (quoi, duree(grand_total, mo)))
    add("")
    add("  Au-dela d une heure, un transfert d un seul tenant finit par")
    add("  etre coupe. C est ce chiffre qui decide entre scp -- sans")
    add("  reprise -- et une methode redemarrable.")
    add("")
    add("=" * 92)
    add("  Ce script n a rien copie, rien efface, rien envoye.")
    add("=" * 92)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())

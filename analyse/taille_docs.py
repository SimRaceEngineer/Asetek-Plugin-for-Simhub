# -*- coding: utf-8 -*-
"""
taille_docs.py -- mesure ce que pesent docs\ et logs\ de la stack.

LECTURE SEULE. N ouvre aucun fichier, n en ecrit aucun, ne supprime rien.
Il ne fait que demander sa taille a chaque fichier via os.stat.

But : separer ce qui est PETIT et VITAL (l etat que la stack relit au
demarrage) de ce qui est GROS et ARCHIVABLE (l historique). Sans cette
mesure on ne sait pas quoi faire passer par le Drive et quoi laisser
sur le disque du VPS.

Usage :
    python "G:\\My Drive\\ScalpEA\\taille_docs.py"
    python "G:\\My Drive\\ScalpEA\\taille_docs.py" C:\\un\\autre\\chemin

Sans argument il cherche le dossier docs dans cet ordre :
    1. le repertoire courant, s il s appelle deja docs
    2. docs sous le repertoire courant
    3. ~\\Downloads\\Scalp-EA-main\\Scalp-EA-main\\docs
S il ne trouve rien il dit ce qu il a essaye au lieu de planter.
"""

import os
import sys

MO = 1024.0 * 1024.0

# Les fichiers que la stack relit au demarrage. Repris des chemins
# reellement presents dans le code (grep sur les modules), pas devines.
ETAT_VIVANT = (
    "rails_trades/tickets_rails.jsonl",
    "x60_onset/events.jsonl",
    "jauge_h1.json",
    "jauge_h1.csv",
    "papier_tf/trades.jsonl",
    "papier_tf/etat.json",
    "papers_live/trades.jsonl",
    "ignition_trader/decisions.jsonl",
    "repl_ops.jsonl",
    "miroir_papers.csv",
)


def poids(chemin):
    """Somme des tailles sous chemin. Retourne (octets, nb_fichiers).

    Les erreurs par fichier (permission, lien casse, fichier efface
    pendant le parcours) sont comptees a part plutot qu ignorees en
    silence : un total faux sans le dire serait pire que pas de total.
    """
    total = 0
    nb = 0
    rates = 0
    for base, _dirs, fics in os.walk(chemin):
        for f in fics:
            try:
                total += os.path.getsize(os.path.join(base, f))
                nb += 1
            except OSError:
                rates += 1
    return total, nb, rates


def trouve_docs(argv):
    if len(argv) > 1:
        return os.path.abspath(argv[1])
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
    print("Relancez en donnant le chemin en argument.")
    return None


def main():
    docs = trouve_docs(sys.argv)
    if docs is None:
        return 1
    if not os.path.isdir(docs):
        print("Ce chemin n est pas un dossier : %s" % docs)
        return 1

    print("=" * 64)
    print("docs = %s" % docs)
    print("=" * 64)
    print("")

    sous = []
    racine_fics = []
    for nom in sorted(os.listdir(docs)):
        p = os.path.join(docs, nom)
        if os.path.isdir(p):
            o, n, r = poids(p)
            sous.append((o, n, r, nom))
        elif os.path.isfile(p):
            try:
                racine_fics.append((os.path.getsize(p), nom))
            except OSError:
                pass

    sous.sort(reverse=True)
    racine_fics.sort(reverse=True)

    tot_o = sum(s[0] for s in sous) + sum(f[0] for f in racine_fics)
    tot_n = sum(s[1] for s in sous) + len(racine_fics)
    tot_r = sum(s[2] for s in sous)

    print("SOUS-DOSSIERS, du plus lourd au plus leger")
    print("-" * 64)
    print("%10s %9s  %s" % ("Mo", "fichiers", "nom"))
    print("-" * 64)
    vitaux = set(c.split("/")[0] for c in ETAT_VIVANT if "/" in c)
    for o, n, r, nom in sous:
        marque = " <-- etat vivant" if nom in vitaux else ""
        print("%10.1f %9d  %s%s" % (o / MO, n, nom, marque))
    print("-" * 64)

    if racine_fics:
        print("")
        print("FICHIERS A LA RACINE DE docs (20 plus gros sur %d)"
              % len(racine_fics))
        print("-" * 64)
        for o, nom in racine_fics[:20]:
            print("%10.1f  %s" % (o / MO, nom))
        print("-" * 64)

    print("")
    print("TOTAL docs : %.1f Mo, %d fichiers" % (tot_o / MO, tot_n))
    if tot_r:
        print("ATTENTION : %d fichiers n ont pas pu etre mesures." % tot_r)
        print("Le total ci-dessus est donc un PLANCHER, pas la verite.")

    # Le voisin logs, s il existe : meme question, mais lui n est
    # jamais necessaire au demarrage.
    logs = os.path.join(os.path.dirname(docs), "logs")
    if os.path.isdir(logs):
        o, n, r = poids(logs)
        print("")
        print("TOTAL logs : %.1f Mo, %d fichiers   (diagnostic, "
              "pas necessaire au demarrage)" % (o / MO, n))

    # Etat vivant : les fichiers que la stack relit vraiment.
    print("")
    print("=" * 64)
    print("ETAT VIVANT -- ce qu il faut emporter pour redemarrer")
    print("=" * 64)
    print("%10s  %s" % ("Mo", "fichier"))
    print("-" * 64)
    somme = 0
    manquants = []
    for rel in ETAT_VIVANT:
        p = os.path.join(docs, *rel.split("/"))
        if os.path.isfile(p):
            try:
                t = os.path.getsize(p)
            except OSError:
                manquants.append(rel + "  (illisible)")
                continue
            somme += t
            print("%10.2f  %s" % (t / MO, rel))
        else:
            manquants.append(rel)
    print("-" * 64)
    print("%10.2f  TOTAL a emporter" % (somme / MO))
    if manquants:
        print("")
        print("Absents (normal si le module n a jamais tourne) :")
        for m in manquants:
            print("   %s" % m)
    print("")
    print("=" * 64)
    print("Lecture seule. Aucun fichier ouvert, ecrit ou supprime.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())

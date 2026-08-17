# -*- coding: utf-8 -*-
r"""
patch_raccord.py -- un raccord n est pas une echeance

  python patch_raccord.py

LE PIEGE

    contrat_continu.py charge les fichiers dont le symbole commence par
    la racine demandee :

        sym = nom[3:-4]
        if racine and not sym.upper().startswith(racine.upper()):
            continue

    Avec --racine MES, cela prend of_MESM26-CME.csv, of_MESU26-CME.csv
    ... et of_MES-continu.csv, qui commence lui aussi par MES.

    Le raccord contient TOUTES les barres des deux echeances. Il domine
    donc le volume tous les jours, sans exception. Le "nouveau" fichier
    produit n est plus qu une copie de l ancien, avec une colonne
    `contrat` qui vaut "MES-continu" partout.

    Rien ne plante. Mais ensuite ecarte_doublons() cherche, dans la
    colonne `contrat`, des noms d echeances a exclure ; il n y trouve
    que "MES-continu", qui est le fichier lui-meme. Il n exclut plus
    rien. MESM26 et MESU26 reviennent dans le rapport, les memes barres
    sont a nouveau comptees trois fois, et la correction de la matinee
    est perdue SANS UN MESSAGE.

    C est la deuxieme fois aujourd hui qu un fichier produit par la
    chaine est relu par la chaine comme une donnee d entree.

LE CORRECTIF

    On reconnait un raccord a ce qu il DECLARE, pas a son nom : il
    porte une colonne `contrat`. L en-tete est lu, le fichier est
    ignore, et la raison est affichee.

    Lire le nom aurait marche aujourd hui et casse le jour ou le
    fichier s appellera autrement.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import io
import os
import shutil
import sys

CIBLE = "contrat_continu.py"
MARQUE = "il porte une colonne"

A1 = '''        sym = nom[3:-4]
        if racine and not sym.upper().startswith(racine.upper()):
            continue
        lignes = []
        with io.open(os.path.join(dossier, nom), encoding="utf-8",
                     errors="replace") as f:
            for r in csv.DictReader(f, delimiter=";"):
'''
B1 = '''        sym = nom[3:-4]
        if racine and not sym.upper().startswith(racine.upper()):
            continue
        # UN RACCORD N EST PAS UNE ECHEANCE.
        #
        # `of_MES-continu.csv` commence par MES : avec --racine MES il
        # serait charge comme une troisieme echeance. Comme il contient
        # toutes les barres des deux autres, il dominerait le volume
        # tous les jours et le nouveau raccord ne serait qu une copie
        # de l ancien -- dont la colonne `contrat` ne nommerait plus
        # aucune echeance a ecarter en aval.
        #
        # On le reconnait a ce qu il DECLARE : il porte une colonne
        # `contrat`. Lu dans l en-tete, pas devine dans le nom -- un
        # nom marche aujourd hui et casse le jour ou il change.
        chemin = os.path.join(dossier, nom)
        with io.open(chemin, encoding="utf-8", errors="replace") as f:
            tete = f.readline()
        if "contrat" in [c.strip() for c in tete.strip().split(";")]:
            print("  %s ignore : il porte une colonne `contrat`, c est"
                  % nom)
            print("     un raccord deja construit, pas une echeance.")
            continue
        lignes = []
        with io.open(chemin, encoding="utf-8",
                     errors="replace") as f:
            for r in csv.DictReader(f, delimiter=";"):
'''

REMPLACEMENTS = [
    ("exclusion des raccords dans charge()", A1, B1),
]


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        return 1
    src = io.open(CIBLE, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique. Rien n a ete touche.")
        return 0

    manque = []
    for nom, a, _ in REMPLACEMENTS:
        n = src.count(a)
        if n != 1:
            manque.append((nom, n))
    if manque:
        print("KO : ancres introuvables ou ambigues, rien n a ete ecrit.")
        for nom, n in manque:
            print("  %-46s %d occurrence(s), attendu 1" % (nom, n))
        print()
        print("Ton contrat_continu.py a deja diverge du mien une fois")
        print("(regle de persistance, colonne `roulement`). Colle-moi la")
        print("fonction charge() et je reancre.")
        return 1

    out = src
    for nom, a, b in REMPLACEMENTS:
        out = out.replace(a, b, 1)

    try:
        compile(out, CIBLE, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (ligne %s : %s)."
              % (e.lineno, e.msg))
        print("Rien n a ete ecrit. L original est intact.")
        return 1

    sauv = CIBLE + ".avant_raccord"
    if not os.path.isfile(sauv):
        shutil.copy2(CIBLE, sauv)
    io.open(CIBLE, "w", encoding="utf-8", newline="").write(out)

    print("%s : %d lignes -> %d lignes, %d remplacement."
          % (CIBLE, len(src.splitlines()), len(out.splitlines()),
             len(REMPLACEMENTS)))
    print("sauvegarde : %s" % sauv)
    print()
    print("Verification : le tableau des echeances ne doit PAS contenir")
    print("de ligne `MES-continu`. S il en contient une, l ancien")
    print("raccord a ete relu et le resultat est a jeter.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

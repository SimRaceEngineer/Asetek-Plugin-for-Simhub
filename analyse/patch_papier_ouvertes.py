# -*- coding: utf-8 -*-
"""
patch_papier_ouvertes.py -- une heure a zero n est pas une heure vide

  python patch_papier_ouvertes.py --essai
  python patch_papier_ouvertes.py

LE DEFAUT, ET IL VIENT DU PATCH PRECEDENT

    patch_papier_jambes a fait le bon choix : par_entree ne rend plus
    que les entrees reellement fermees. Mais les tableaux qui lisent
    `entrees` n ont pas ete prevenus, et ils affichent toujours cette
    colonne sous le nom « entrees ».

    Resultat, le 13/08 a 11:40 :

        heure    observe  entrees
        05h         1.0h        0     <- 4 cellules ouvertes a 05:00
        06h         1.0h        0     <- 4 cellules ouvertes a 06:00
        07h         1.0h        0     <- 2 cellules ouvertes a 07:00

    Zero entree en face d une heure pleine d observation, c est la
    lecture que le panneau declare lui-meme comme la seule fiable :
    « les lignes a 0 entree ET plusieurs heures d observation sont les
    vraies : la, on sait qu il ne s est rien passe. » Ici c est faux.
    Dix positions se sont ouvertes dans ce creneau et courent encore.

    Le meme piege vaut pour SEANCE CONTRE HORS SEANCE : 26 positions
    en cours, aucune dans les colonnes.

    C est exactement la faute que ce fichier passe son temps a
    denoncer -- confondre « rien ne s est passe » et « on ne sait pas
    encore » -- et je l ai introduite en corrigeant l autre.

CE QUE LE PATCH FAIT

    1. Une colonne « ouvertes » dans le tableau horaire, et l heure
       s affiche meme si elle n a que des positions en cours.
    2. Une ligne sous SEANCE / HORS SEANCE disant combien de positions
       courent de chaque cote, et qu elles ne sont dans aucune colonne.
    3. Corrige « 30 %% » affiche litteralement ligne 123 du panneau :
       la chaine n a pas d operateur de format, le doublement est donc
       inutile. Troisieme fois que cette faute passe ici.

    Aucune valeur n est recalculee. Les EUR, WR, PF ne bougent pas :
    on ajoute ce qui manquait pour les lire.

QUATRE ANCRES, verifiees uniques. IDEMPOTENT. Sauvegarde horodatee.
ast.parse avant ecriture. C est une lecture : rien a redemarrer.

EXIGE patch_papier_jambes -- l ancre du 3 en vient. S il n est pas
applique, ce patch s arrete sans rien ecrire et le dit.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "papier_tf.py"
MARQUEUR = "ov.get(k, 0)"

# --- 1. le compte des positions en cours, par heure d ouverture -----------
A1 = '''    oh, eh, ph = defaultdict(int), defaultdict(int), defaultdict(list)
    for e in veilles:
        oh[e["ts"][11:13]] += 1
'''
N1 = '''    oh, eh, ph = defaultdict(int), defaultdict(int), defaultdict(list)
    for e in veilles:
        oh[e["ts"][11:13]] += 1
    # Les positions ENCORE OUVERTES ne sont dans aucune des deux boucles
    # ci-dessous : depuis le correctif des jambes, `entrees` ne contient
    # que des entrees dont l issue est connue. Sans cette troisieme
    # colonne, une heure ou six cellules se sont ouvertes et courent
    # encore s affiche a zero avec une heure d observation pleine --
    # c est-a-dire comme une absence de signal, la lecture exactement
    # inverse de la verite.
    ov = defaultdict(int)
    for p in ouvertes.values():
        ov[(p.get("ts") or "")[11:13]] += 1
'''

# --- 2. l en-tete du tableau horaire --------------------------------------
A2 = '''        L.append("%-7s %8s %8s %11s %10s   %s"
                 % ("heure", "observe", "entrees", "EUR", "EUR/trade",
                    "profil"))
'''
N2 = '''        L.append("%-7s %8s %8s %9s %11s %10s   %s"
                 % ("heure", "observe", "fermees", "ouvertes", "EUR",
                    "EUR/trade", "profil"))
'''

# --- 3. la ligne sautee, et la ligne affichee -----------------------------
A3 = '''            if not (oh.get(k) or eh.get(k)):
'''
N3 = '''            if not (oh.get(k) or eh.get(k) or ov.get(k)):
'''

A4 = '''            L.append("%-7s %7.1fh %8d %s   %s"
                     % (k + "h", oh.get(k, 0) * VEILLE_MIN / 60.0,
                        eh.get(k, 0), ch, prof))
    L.append("")
'''
N4 = '''            L.append("%-7s %7.1fh %8d %9d %s   %s"
                     % (k + "h", oh.get(k, 0) * VEILLE_MIN / 60.0,
                        eh.get(k, 0), ov.get(k, 0), ch, prof))
        L.append("-" * LARG)
        L.append("  'fermees' = entrees dont l issue est connue."
                 " 'ouvertes' = encore")
        L.append("  en cours, resultat inconnu. Une heure a 0 fermee et 6")
        L.append("  ouvertes n est pas une heure sans signal : c est une")
        L.append("  heure dont on ne sait pas encore le resultat.")
    L.append("")
'''

# --- 5. la meme reserve sous SEANCE / HORS SEANCE -------------------------
A5 = '''    L.append("  Une colonne vide en face d une couverture nulle ne dit rien.")
'''
N5 = '''    ouv_cr = defaultdict(int)
    for p in ouvertes.values():
        ouv_cr[p.get("creneau", "?")] += 1
    if ouv_cr:
        L.append("  encore ouvertes, dans AUCUNE colonne ci-dessus : %s."
                 % ", ".join("%s %d" % (c, ouv_cr[c]) for c in sorted(ouv_cr)))
    L.append("  Une colonne vide en face d une couverture nulle ne dit rien.")
'''

# --- 6. le %% affiche litteralement ---------------------------------------
A6 = '''"coupes en profit mais les 30 %% courent encore. Les compter"'''
N6 = '''"coupes en profit mais les 30 % courent encore. Les compter"'''

REMPLACEMENTS = [
    ("le compte des positions en cours", A1, N1),
    ("l en-tete du tableau horaire", A2, N2),
    ("la condition de saut d une heure", A3, N3),
    ("la ligne du tableau horaire", A4, N4),
    ("la reserve sous SEANCE / HORS", A5, N5),
    ("le 30 %% affiche litteralement", A6, N6),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    if "partiels_ouverts" not in src:
        print("KO : patch_papier_jambes n est pas applique sur ce fichier.")
        print("     Ce patch corrige une consequence du sien et reprend une")
        print("     de ses lignes comme ancre. Applique-le d abord.")
        print("Rien n a ete ecrit.")
        return 1

    for nom, anc, _n in REMPLACEMENTS:
        c = src.count(anc)
        if c != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (c, nom))
            print("Rien n a ete ecrit.")
            return 1
    print("Six ancres, chacune unique.")

    neuf = src
    for _nom, anc, nou in REMPLACEMENTS:
        neuf = neuf.replace(anc, nou, 1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # Le controle syntaxique ne verrait pas une colonne posee au mauvais
    # niveau d indentation : les deux versions compilent. On verifie donc
    # que les trois lignes ajoutees au tableau horaire sont bien dans le
    # `else` du tableau et pas dans la boucle `for h in range(24)`, ce qui
    # les repeterait a chaque heure.
    m = re.search(r'^( +)L\.append\("  \'fermees\' = entrees', neuf, re.M)
    if not m or len(m.group(1)) != 8:
        print("KO : la note du tableau horaire est au niveau %s, il faut 8"
              % (len(m.group(1)) if m else "?"))
        print("     A 12 elle serait dans la boucle et se repeterait a")
        print("     chaque heure. Rien n a ete ecrit.")
        return 1

    print()
    print("Le tableau horaire gagne une colonne 'ouvertes', et une heure")
    print("qui n a que des positions en cours cesse de s afficher comme")
    print("une heure sans signal.")
    print()
    print("SEANCE / HORS SEANCE dit desormais combien de positions courent")
    print("de chaque cote, et qu elles ne sont dans aucune colonne.")
    print()
    print("Aucun EUR, WR ou PF n est recalcule : on ajoute ce qui manquait")
    print("pour les lire, on ne touche a aucun chiffre.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. C est une lecture : rien a redemarrer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

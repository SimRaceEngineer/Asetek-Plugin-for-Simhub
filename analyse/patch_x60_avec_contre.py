# -*- coding: utf-8 -*-
"""
patch_x60_avec_contre.py -- les tierces qui vont CONTRE un x60

  python patch_x60_avec_contre.py --essai
  python patch_x60_avec_contre.py

LA QUESTION

    « Ce matin dans l historique, les SELL contre les x60 perdent
    alors que les BUY qui accompagnent passent. On log les contraires
    aux directions x ? »

    Oui. Depuis le premier evenement du 12/08 a 22:53, chaque
    X60_ENTREE porte son propre `sens`, et son `plateau` porte pour
    CHAQUE tierce son magic, son actif, son sens, son latent et son
    ticket. La donnee est complete et n a jamais ete lue : le rapport
    n affiche que « presences » et « latent », sans jamais comparer
    les deux directions.

    Ce patch ne collecte rien de neuf. Il lit ce qui dort deja dans le
    journal, donc il repond retroactivement, sur tous les evenements
    depuis le debut.

CE QU IL AJOUTE -- UNE SECTION

    Pour chaque tierce presente a l entree d un x60 : AVEC ou CONTRE
    sa direction, et le resultat des deux camps.

    MEME ACTIF et AUTRE ACTIF sont separes, et c est le point qui
    compte. Sur le meme actif, « contre » est une position opposee au
    sens strict. Sur un autre indice, ce n est qu une correlation --
    US30 et US100 montent souvent ensemble, mais pas toujours. Les
    melanger repondrait a une troisieme question, ni l une ni l autre.

    Deux colonnes de resultat, qui ne disent pas la meme chose :

      latent moyen   le P&L de la tierce a l INSTANT ou le x60 entre
      final moyen    son dernier latent observe, donc son issue

    Une tierce peut etre en perte a l entree du x60 et finir gagnante.
    C est meme exactement l hypothese a tester.

LA RESERVE QUI COMPTE

    Le gel V2 porte deja une mesure de la meme famille, et elle va
    dans l AUTRE sens (v10_contre_cycle_m1) :

        M1 BEAR vente AVEC   193 -> -20,89
        M1 BEAR achat CONTRE 120 -> +11,31
        M1 BULL achat AVEC   254 ->  +3,39
        M1 BULL vente CONTRE  95 -> +15,43

    Ce n est pas la meme reference -- la, c est le cycle M1 ; ici,
    c est la direction d un x60 -- donc il n y a pas contradiction
    formelle. Mais si les deux lectures portent sur les memes tickets
    et se contredisent, l une des deux est fausse, et la section le
    rappelle a l ecran plutot que dans ce fichier que personne ne
    relira.

    Et les effectifs : 8 entrees x60 au 13/08 midi. Cette section
    DECRIT, elle ne conclut pas, tant que le compte n a pas grandi.

UNE ANCRE, verifiee unique. IDEMPOTENT. Sauvegarde horodatee.
ast.parse avant ecriture. C est une lecture : rien a redemarrer,
le --rapport suivant l affiche.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "x60_onset.py"
MARQUEUR = "AVEC OU CONTRE LA DIRECTION"

ANCRE = '''    # --------------------------------- garder ou fermer avec le x60
'''

NEUF = '''    # ------------------------------- avec ou contre la direction du x60
    L.append("=" * LARG)
    L.append("  AVEC OU CONTRE LA DIRECTION DU x%s" % SETUP)
    L.append("=" * LARG)
    # Le sens de chaque tierce dort dans le plateau de chaque X60_ENTREE
    # depuis le premier evenement. Il n avait jamais ete lu.
    # MEME ACTIF et AUTRE ACTIF sont separes : sur le meme actif,
    # "contre" est une position opposee au sens strict ; sur un autre
    # indice ce n est qu une correlation. Les melanger repondrait a une
    # troisieme question, ni l une ni l autre.
    ac = defaultdict(lambda: {"n": 0, "lat": [], "fin": []})
    for e in entrees:
        sx = e.get("sens")
        if not sx:
            continue
        for a in e.get("plateau", []):
            if a["x60"]:
                continue
            k = ("meme actif" if a["actif"] == e.get("actif")
                 else "autre actif",
                 "AVEC" if a["sens"] == sx else "CONTRE")
            ac[k]["n"] += 1
            ac[k]["lat"].append(a["latent"])
            fin = (clotures.get(a["ticket"]) or {}).get("final")
            if fin is not None:
                ac[k]["fin"].append(fin)
    if not ac:
        L.append("  Aucune tierce enregistree a l entree d un x%s." % SETUP)
    else:
        L.append("%-13s %-8s %10s %14s %8s %13s"
                 % ("actif", "sens", "presences", "latent moyen",
                    "connus", "final moyen"))
        L.append("-" * LARG)
        for k in sorted(ac):
            c = ac[k]
            _nl, _sl, ml, _r1, _p1, _s1 = ratios(c["lat"])
            nf, _sf, mf, _r2, _p2, _s2 = ratios(c["fin"])
            L.append("%-13s %-8s %10d %14.2f %8d %13s"
                     % (k[0], k[1], c["n"], ml, nf,
                        ("%.2f" % mf) if nf else "-"))
        L.append("-" * LARG)
        L.append("  'latent moyen' = le P&L de la tierce a l INSTANT ou le")
        L.append("  x%s entre. 'final moyen' = son dernier latent observe,"
                 % SETUP)
        L.append("  donc son issue, a %d secondes pres. Les deux ne disent"
                 % PAS)
        L.append("  pas la meme chose : une tierce peut etre en perte a")
        L.append("  l entree du x%s et finir gagnante." % SETUP)
        L.append("  Un meme ticket present a DEUX entrees x%s compte deux"
                 % SETUP)
        L.append("  fois : ce sont des presences, pas des tickets uniques,")
        L.append("  et 'final moyen' est donc pondere par la presence.")
        L.append("")
        L.append("  RESERVE : le gel V2 (v10_contre_cycle_m1) a mesure")
        L.append("  l effet INVERSE sur le cycle M1 -- entrer CONTRE valait")
        L.append("  +11,31 et +15,43, entrer AVEC -20,89 et +3,39. Ce n est")
        L.append("  pas la meme reference, donc pas une contradiction")
        L.append("  formelle. Mais si les deux portent sur les memes")
        L.append("  tickets et se contredisent, une des deux est fausse.")
    L.append("")

    # --------------------------------- garder ou fermer avec le x60
'''


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

    n = src.count(ANCRE)
    if n != 1:
        print("KO : %d occurrence(s) de l ancre, il en faut 1." % n)
        print("Rien n a ete ecrit.")
        return 1

    neuf = src.replace(ANCRE, NEUF, 1)

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # ast.parse ne verrait pas la section posee dans une fonction voisine,
    # ou apres le `return` de rapport() : les deux compilent. On verifie
    # donc sur l arbre qu elle est bien DANS rapport(), et qu elle vient
    # AVANT la section "GARDER, OU TOUT FERMER".
    dedans = apres = False
    for f in ast.walk(arbre):
        if not (isinstance(f, ast.FunctionDef) and f.name == "rapport"):
            continue
        d = ast.dump(f)
        dedans = MARQUEUR in d
        if dedans:
            apres = (d.index(MARQUEUR) < d.index("GARDER, OU TOUT FERMER"))
    if not dedans:
        print("KO : la section n est pas dans rapport(). Rien n a ete ecrit.")
        return 1
    if not apres:
        print("KO : la section est posee APRES 'GARDER OU TOUT FERMER'.")
        print("     Rien n a ete ecrit.")
        return 1
    print("Section verifiee sur l arbre : dans rapport(), au bon endroit.")

    print()
    print("Nouvelle section : AVEC OU CONTRE LA DIRECTION DU x60.")
    print("Elle ne collecte rien -- elle lit le sens des tierces, deja")
    print("enregistre dans chaque plateau depuis le 12/08 22:53. Elle")
    print("repond donc retroactivement, sur tous les evenements.")
    print()
    print("MEME ACTIF et AUTRE ACTIF restent separes : sur le meme actif")
    print("'contre' est une position opposee ; sur un autre indice ce")
    print("n est qu une correlation.")
    print()
    print("8 entrees x60 au 13/08 midi : la section DECRIT, elle ne")
    print("conclut pas. Elle porte la reserve du gel V2 a l ecran.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Le prochain --rapport l affiche.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

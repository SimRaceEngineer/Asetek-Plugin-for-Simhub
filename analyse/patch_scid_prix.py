# -*- coding: utf-8 -*-
"""
patch_scid_prix.py -- ecrire les prix que l export calcule deja

  python patch_scid_prix.py --essai
  python patch_scid_prix.py

CE QU ON A CONSTATE LE 13/08

    Une barre de C:\\OrderflowExport ne porte AUCUN prix :

        ts, epoch_utc, asset, src, delta, cum_delta, vol,
        range_ticks, close_pos, er, net, gross, events

    Ni close, ni high, ni low. Il y a `range_ticks` (l amplitude) et
    `close_pos` (la position de la cloture dedans, 0 = bas, 1 = haut),
    mais sans point d ancrage aucun niveau ne se reconstitue.

    Or read_bars les tient depuis toujours (l.129-137) :

        bars[key] = {"h": h, "l": l, "c": c, "v": vol, ...}
        ...
        if h > b["h"]: b["h"] = h
        if l < b["l"]: b["l"] = l
        b["c"] = c            # derniere transaction de la minute

    Et _detect les recoit (l.235) : `_detect(..., b["h"], b["l"], ...)`.
    Les prix sont calcules, tenus a jour, utilises -- et jetes au
    moment d ecrire. Ce patch les ecrit. Rien de plus.

CE QUE CA DEBLOQUE, ET CE QUE CA NE DEBLOQUE PAS

    Ce que ca debloque : une serie de prix cote FUTURE, minute par
    minute, sur tout l historique. On peut mesurer un mouvement entre
    deux barres, situer une cloture dans son amplitude avec un niveau
    reel, et croiser l orderflow a une trajectoire de prix.

    Ce que ca NE debloque PAS, et c est important : les prix ecrits
    sont ceux du FUTURE (YM, MES), alors que les tickets sont des CFD
    (US30, US500). Entre les deux il y a une base, et des tailles de
    tick differentes. SOUSTRAIRE `_close_barre` d un prix d entree
    MT5 donnerait la base, pas le cout du retard.

    Le cout du retard reste donc mesurable seulement en DIFFERENCE
    INTERNE au future -- cloture de la barre contenante contre cloture
    de la precedente, par exemple -- ou apres avoir estime la base.
    C est une mesure de plus, pas la mesure finale.

    Dit autrement : ce patch enleve un obstacle, il n en enleve pas
    deux. Le second est le differe de 10 min du flux.

RATTRAPAGE RETROACTIF -- ET LA PRECAUTION QUI VA AVEC

    scid_orderflow relit les ticks `.scid`, qui remontent loin. Un
    passage large REGENERE l historique avec les nouveaux champs :

        python scid_orderflow.py --days 65

    ATTENTION : la boucle rafraichir_orderflow appelle scid_orderflow
    toutes les 30 s sur les MEMES fichiers, et l ecriture n est pas
    atomique. Deux passes qui se croisent laissent un .jsonl tronque
    -- et un .jsonl tronque ressemble a un .jsonl. ARRETER LA BOUCLE
    avant un rattrapage, la relancer apres.

UNE ANCRE, verifiee unique. IDEMPOTENT. Sauvegarde horodatee.
ast.parse avant ecriture. Puis trois controles que la seule syntaxe ne
donnerait pas : que read_bars tient bien `c`, `h` et `l` (sinon on
ecrirait des champs vides), que les treize champs d origine sont
toujours la exactement une fois chacun, et que les trois nouveaux
atterrissent dans la fonction qui construit l enregistrement.

L export ne passe aucun ordre. Il ecrit un seul dossier.
"""
import argparse
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "scid_orderflow.py"
MARQUEUR = '"close": round(b["c"]'

ANCRE = '''            "vol": int(b["v"]),
            "range_ticks": round(rng, 2),
            "close_pos": round(close_pos, 3),
'''

NEUF = '''            "vol": int(b["v"]),
            "range_ticks": round(rng, 2),
            "close_pos": round(close_pos, 3),
            # LES PRIX, absents jusqu au 13/08 -- et pourtant calcules
            # depuis toujours : read_bars tient b["c"] (derniere
            # transaction de la minute), b["h"] et b["l"], et _detect
            # les recoit plus haut. Seul l enregistrement ne les
            # portait pas, si bien qu aucune mesure ne pouvait situer
            # une barre a un NIVEAU. close_pos ne suffit pas : c est
            # une position DANS l amplitude, sans point d ancrage.
            # Ce sont les prix du FUTURE (YM, MES), pas du CFD trade.
            # Les soustraire d un prix d entree MT5 donnerait la base
            # entre les deux instruments, pas le cout d un retard.
            "close": round(b["c"], 5),
            "high": round(b["h"], 5),
            "low": round(b["l"], 5),
'''

# Les champs d origine, chacun exactement une fois. Si l un d eux
# changeait, un panneau changerait de chiffres sans qu on l ait
# demande -- on ajoute des colonnes, on n en corrige aucune.
ORIGINE = ('"ts":', '"epoch_utc":', '"asset":', '"src":', '"delta":',
           '"cum_delta":', '"vol":', '"range_ticks":', '"close_pos":',
           '"er":', '"net":', '"gross":', '"events":')


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
        print("     Attendu le bloc vol / range_ticks / close_pos de")
        print("     l enregistrement ecrit, indente a 12 espaces.")
        print("Rien n a ete ecrit.")
        return 1

    # Ecrire b["c"] n a de sens que si read_bars le tient. S il ne le
    # tenait pas, le patch produirait trois champs toujours vides --
    # ce qui ressemble a des donnees.
    for expr, quoi in (('"c": c', "la cloture a la creation de la barre"),
                       ('b["c"] = c', "sa mise a jour a chaque tick"),
                       ('b["h"] = h', "le plus haut"),
                       ('b["l"] = l', "le plus bas")):
        if expr not in src:
            print("KO : %s introuvable (%s)." % (expr, quoi))
            print("     read_bars ne tient pas ce prix : le champ serait")
            print("     vide. Rien n a ete ecrit.")
            return 1
    print("read_bars tient bien c, h et l -- les champs auront un contenu.")

    neuf = src.replace(ANCRE, NEUF, 1)

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    for champ in ORIGINE:
        if src.count(champ) != neuf.count(champ):
            print("KO : %s n apparait plus le meme nombre de fois." % champ)
            print("Rien n a ete ecrit.")
            return 1
    print("Les treize champs d origine sont intacts.")

    ok = False
    for f in ast.walk(arbre):
        if not isinstance(f, ast.FunctionDef):
            continue
        d = ast.dump(f)
        if "close_pos" in d and "'close'" in d and "'high'" in d:
            ok = True
            print("Arbre verifie : close, high et low sont dans %s(),"
                  " avec close_pos." % f.name)
            break
    if not ok:
        print("KO : les nouveaux champs ne sont pas dans la fonction qui")
        print("     construit l enregistrement. Rien n a ete ecrit.")
        return 1

    print()
    print("Trois champs ajoutes, aucun modifie : close, high, low.")
    print()
    print("Les barres ecrites A PARTIR DE MAINTENANT les porteront. Pour")
    print("l historique deja sur le disque, il faut un rattrapage :")
    print()
    print("  1. arreter la boucle rafraichir_orderflow")
    print("  2. python scid_orderflow.py --days 65")
    print("  3. la relancer")
    print()
    print("L ordre compte. Deux processus qui reecrivent les memes")
    print("fichiers sans ecriture atomique laissent un .jsonl tronque,")
    print("et un .jsonl tronque ressemble a un .jsonl.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. La prochaine passe de la boucle ecrira les prix.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

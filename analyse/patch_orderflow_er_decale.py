# -*- coding: utf-8 -*-
"""
patch_orderflow_er_decale.py -- l ER de la barre CLOSE, a cote de l autre

  python patch_orderflow_er_decale.py --essai
  python patch_orderflow_er_decale.py

CE QU ON A DECOUVERT LE 13/08

    orderflow_join apparie chaque trade a sa barre Ninja ainsi :

        e      = _epoch(t.get("entry_ts"))
        minute = int(e // BAR_SEC) * BAR_SEC
        bar    = of_idx.get((t.get("asset"), minute))

    L arrondi va vers le BAS : la barre retenue est celle qui CONTIENT
    l entree. Elle se referme apres. Un trade entre a 10:00:15 est donc
    apparie a la barre 10:00-10:01, dont l Efficiency Ratio ne sera
    connu qu a 10:01.

    Consequence : les chiffres du gel V9 -- US30 CARNAGE +1,57 (59),
    MOU -14,59 (47), CORRECT +11,97 (48), PROPRE +20,43 (24) -- ne
    sont pas reproductibles par une regle live. Ils DECRIVENT ce qui
    s est passe pendant le trade ; ils ne pouvaient pas etre lus au
    moment de decider.

CE QUE CA N INTERDIT PAS

    Deux regles restent implementables, et ce patch sert a les mesurer
    toutes les deux :

      A. LA BARRE PRECEDENTE. Son ER est connu a l instant t, sans
         attendre. Elle decrit le passe immediat, pas le mouvement
         qu on prend.

      B. ATTENDRE LA CLOTURE. Le signal s allume, on laisse la barre en
         cours se fermer, on lit son ER, on entre. C est l ER de la
         BONNE barre -- celle qui caracterise le mouvement -- au prix
         d un retard de 0 a 60 s, 30 en moyenne. Ce retard a un cout en
         prix d entree, et ce cout se mesure : c est _close_barre.

    B est la plus interessante des deux SI le cout du retard est
    petit. C est tout l objet de la mesure.

CE QUE LE PATCH AJOUTE -- TROIS CHAMPS, RIEN D AUTRE

      _er_prec        l ER de la barre precedente, close avant l entree
      _er_band_prec   sa bande
      _close_barre    la cloture de la barre contenante (cout du retard)

    _er et _er_band ne sont NI modifies NI remplaces. Tout ce qui les
    lit aujourd hui -- panneaux, gels, etudes -- continue de rendre
    exactement les memes chiffres. On ajoute une colonne, on n en
    corrige aucune : les mesures passees restent comparables.

    Les trois champs existent TOUJOURS, meme quand la barre manque.
    Un champ present valant None se lit ; un champ absent leve une
    KeyError trois semaines plus tard dans un panneau.

UNE ANCRE, verifiee unique. IDEMPOTENT. Sauvegarde horodatee.
ast.parse avant ecriture, puis controle sur l arbre que les nouveaux
champs sont poses dans la MEME fonction que _er_band -- ailleurs, ils
compileraient sans jamais etre calcules.

C est une jointure de lecture : aucun ordre, rien a redemarrer. Les
consommateurs relisent a chaque appel.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "orderflow_join.py"
MARQUEUR = "_er_band_prec"

ANCRE = '''            if bar:
                evs = bar.get("events") or []
                d["_of"] = bar
                d["_er"] = bar.get("er")
                d["_er_band"] = er_band(bar.get("er"))
'''

NEUF = '''            if bar:
                evs = bar.get("events") or []
                d["_of"] = bar
                d["_er"] = bar.get("er")
                d["_er_band"] = er_band(bar.get("er"))
                # LA BARRE PRECEDENTE, close AVANT l entree.
                # `bar` ci-dessus est la barre qui CONTIENT l entree :
                # int(e // BAR_SEC) arrondit vers le bas, donc elle se
                # referme apres, et son ER n est pas connu au moment de
                # decider. Celui-ci l est. Les deux coexistent : _er_band
                # pour relire l historique tel qu il a ete mesure,
                # _er_band_prec pour ce qui aurait pu etre decide.
                _bp = of_idx.get((t.get("asset"), minute - BAR_SEC))
                d["_er_prec"] = _bp.get("er") if _bp else None
                d["_er_band_prec"] = er_band(_bp.get("er") if _bp else None)
                # La cloture de la barre contenante : le prix qu on
                # paierait en attendant sa fermeture pour lire son ER.
                # L ecart avec l entree reelle est le COUT DU RETARD, et
                # il decide a lui seul si cette regle-la vaut la peine.
                d["_close_barre"] = bar.get("close")
'''

# Les trois champs doivent exister meme sans barre : un champ absent
# leve une KeyError plus tard, un champ a None se lit.
ANCRE2 = '''            else:
                d["_of"] = None
                d["_er"] = None
'''
NEUF2 = '''            else:
                d["_of"] = None
                d["_er"] = None
                d["_er_prec"] = None
                d["_er_band_prec"] = "?"
                d["_close_barre"] = None
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

    for nom, anc in (("le bloc `if bar:`", ANCRE),
                     ("le bloc `else:` correspondant", ANCRE2)):
        c = src.count(anc)
        if c != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (c, nom))
            print("Rien n a ete ecrit.")
            return 1
    print("Deux ancres, chacune unique.")

    neuf = src.replace(ANCRE, NEUF, 1).replace(ANCRE2, NEUF2, 1)

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # Poses dans une autre fonction, les trois champs compileraient sans
    # jamais etre calcules. On verifie qu ils sont dans la MEME fonction
    # que _er_band, et que minute et of_idx y sont aussi.
    ok = False
    for f in ast.walk(arbre):
        if not isinstance(f, ast.FunctionDef):
            continue
        d = ast.dump(f)
        if '_er_band' in d and '_er_band_prec' in d:
            ok = ("of_idx" in d and "minute" in d and "BAR_SEC" in d)
            if ok:
                print("Arbre verifie : les trois champs sont dans %s(),"
                      " avec of_idx, minute et BAR_SEC." % f.name)
            break
    if not ok:
        print("KO : les nouveaux champs ne sont pas dans la fonction qui")
        print("     calcule _er_band, ou of_idx/minute/BAR_SEC n y sont")
        print("     pas. Ils compileraient sans etre calcules.")
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("Trois champs ajoutes, aucun modifie :")
    print("  _er_prec        ER de la barre PRECEDENTE, close avant l entree")
    print("  _er_band_prec   sa bande")
    print("  _close_barre    cloture de la barre contenante = cout du retard")
    print()
    print("_er et _er_band restent intacts. Les panneaux, les gels et les")
    print("etudes rendent exactement les memes chiffres qu avant : on")
    print("ajoute une colonne, on n en corrige aucune.")
    print()
    print("Ensuite : python er_decale.py")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. C est une jointure de lecture : rien a redemarrer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
